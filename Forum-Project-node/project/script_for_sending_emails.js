const config = require('./config');

const { Client } = require('pg');
const nodemailer = require('nodemailer');

const MAX_RETRIES = 5;
const RETRY_DELAYS = [
    5 * 60 * 1000,    // 5 minutes
    15 * 60 * 1000,   // 15 minutes
    30 * 60 * 1000,   // 30 minutes
    60 * 60 * 1000,   // 1 hour
    120 * 60 * 1000   // 2 hours
];

const dbConfig = {
    user: config.user,
    host: config.host,
    database: config.database,
    password: config.password,
    port: 5432,
};

const transporter = nodemailer.createTransport({
    host: 'localhost',
    port: 1025,
    auth: null
});

function determineErrorStatus(error) {
    const errorMessage = error.message.toLowerCase();
    
    if (errorMessage.includes('connection')) {
        return 'failed_connection';
    } else if (errorMessage.includes('invalid email') || errorMessage.includes('no recipients')) {
        return 'failed_invalid_email';
    } else if (errorMessage.includes('authentication')) {
        return 'failed_auth';
    } else if (errorMessage.includes('rate limit') || errorMessage.includes('too many requests')) {
        return 'failed_rate_limit';
    } else if (errorMessage.includes('server')) {
        return 'failed_server';
    }
    
    return 'failed_unknown';
}

function calculateNextRetry(retries) {
    if (retries >= RETRY_DELAYS.length) {
        return null;
    }
    return new Date(Date.now() + RETRY_DELAYS[retries]);
}

async function updateEmailStatus(client, id, status, error = null, retries = null) {
    const nextRetry = calculateNextRetry(retries || 0);
    
    await client.query(
        `UPDATE email_queue 
         SET status = $1,
             retries = COALESCE($2, retries),
             last_attempt = CURRENT_TIMESTAMP,
             error_message = $3,
             next_retry = $4
         WHERE id = $5`,
        [status, retries, error?.message, nextRetry, id]
    );
}

async function sendPendingEmails() {
    const client = new Client(dbConfig);

    try {
        await client.connect();

        const res = await client.query(
            `
            SELECT 
                id, 
                data, 
                retries 
            FROM email_queue 
            WHERE status != 'sent' 
                AND status != 'terminated'
                AND (next_retry IS NULL OR next_retry <= CURRENT_TIMESTAMP)
                AND retries < $1
            `,[MAX_RETRIES]
        );

        const emails = res.rows;

        for (const email of emails) {
            const { id, data, retries } = email;
            const { from, to, subject, html } = data;

            await updateEmailStatus(client, id, 'processing', null, retries);

            try {
                await transporter.sendMail({ from, to, subject, html });

                await updateEmailStatus(client, id, 'sent', null, retries + 1);

                console.log(`Email sent to ${to} successfully.`);

            } catch (error) {
                console.error(`Failed to send email to ${to}:`, error);

                const newStatus = retries + 1 >= MAX_RETRIES ? 'terminated' : determineErrorStatus(error);
                await updateEmailStatus(client, id, newStatus, error, retries + 1);
            }
        }
    } catch (error) {
        // AUDIT LOGGER
        console.error("Error processing email queue:", error);
    } finally {
        await client.end();
    }
}
sendPendingEmails();