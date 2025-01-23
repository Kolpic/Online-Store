const { Client } = require('pg');
const config = require('./config');
const { logEvent, logException } = require('./logger');
const { TemporaryException, TemporaryError } = require('./exceptions');

const dbConfig = {
    user: config.user,
    host: config.host,
    database: config.database,
    password: config.password,
    port: 5432,
};

const AUDIT_LOG_EMAIL_USER_EMTY_STRING = "";
const AUDIT_LOG_SUB_SYSTEM_TYPE = "script update promotions";
const AUDIT_LOG_EXCEPTION_TYPE_EMPTY_STRING = "";
const AUDIT_LOG_MESSAGE = "Promotions status check run sucessfully";
const AUDIT_SUB_SYSTEM_BACK_OFFICE = "script_for_updating_promotion_status";
const AUDIT_LOG_TYPE_EVENT = "event";

async function updatePromotionStatus() {
    const client = new Client(dbConfig);

    try {
        await client.connect();

        const updateQuery = `
            UPDATE promotions 
            SET is_active = false 
            WHERE end_date < CURRENT_TIMESTAMP AND is_active = true
        `;

        const result = await client.query(updateQuery);

        console.log(`Updated ${result.rowCount} expired promotions`);
        await logEvent(AUDIT_LOG_EMAIL_USER_EMTY_STRING, AUDIT_LOG_EXCEPTION_TYPE_EMPTY_STRING, AUDIT_LOG_MESSAGE, AUDIT_SUB_SYSTEM_BACK_OFFICE, AUDIT_LOG_TYPE_EVENT);
    } catch (error) {
        console.error('Error updating promotion status:', error);
        await logException(AUDIT_LOG_SUB_SYSTEM_TYPE, "TemporaryException", error.message, AUDIT_SUB_SYSTEM_BACK_OFFICE);
    } finally {
        await client.end();
    }
}

updatePromotionStatus();