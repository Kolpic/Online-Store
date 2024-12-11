const config = require('./config');

const { Client } = require('pg');
const nodemailer = require('nodemailer');

const dbConfig = {
    user: config.user,
    host: config.host,
    database: config.database,
    password: config.password,
    port: 5432,
};

// Email transporter using MailHog
const transporter = nodemailer.createTransport({
    host: 'localhost',
    port: 1025,
    auth: null
});

async function sendPendingEmails() {
    const client = new Client(dbConfig);

    try {
        await client.connect();

        const res = await client.query(
            `SELECT id, data 
             FROM email_queue 
             WHERE status = 'pending'`
        );

        const emails = res.rows;

        for (const email of emails) {
            const { id, data } = email;
            const { from, to, subject, html } = data;

            try {
                await transporter.sendMail({ from, to, subject, html });

                await client.query(
                    `UPDATE email_queue 
                     SET status = 'sent', retries = retries + 1 
                     WHERE id = $1`,
                    [id]
                );

                console.log(`Email sent to ${to} successfully.`);
            } catch (error) {
                console.error(`Failed to send email to ${to}:`, error);

                await client.query(
                    `UPDATE email_queue 
                     SET status = 'failed', retries = retries + 1 
                     WHERE id = $1`,
                    [id]
                );
            }
        }
    } catch (error) {
        console.error("Error processing email queue:", error);
    } finally {
        await client.end();
    }
}
sendPendingEmails();