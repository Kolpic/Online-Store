const pool = require('./db');

// sub_system -> site, back office ; log_type -> event, error
async function logEvent(user_email, exception_type, message, sub_system, log_type) {
    let clientForExcaptionLog = await pool.connect();
    await clientForExcaptionLog.query('BEGIN');

    console.log("Logged event -> " + message);
    await clientForExcaptionLog.query(`INSERT INTO exception_logs (user_email, exception_type, message, sub_system, log_type) VALUES ($1, $2, $3, $4, $5)`, 
        [user_email, exception_type, message, sub_system, log_type]);

    await clientForExcaptionLog.query('COMMIT');
    clientForExcaptionLog.release();
}

module.exports = { logEvent };