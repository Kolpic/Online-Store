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

async function logException(user_email, exception_type, message, subSystem) {
    let clientForExcaptionLog = await pool.connect();

    let auditType = "";

    console.log("exception_type", exception_type);

    if (exception_type === "WrongUserInputException") {
        auditType = "ASSERT_USER";
    } else if (exception_type === "DevException") {
        auditType = "ASSERT_DEV";
    } else if (exception_type === "PeerException") {
        auditType = "ASSERT_PEER";
    } else if (exception_type === "TemporaryException") {
        auditType = "TEMPORARY";
    } else {
        auditType = "ASSERT_DEV";
    }

    console.log("LOGGING EXCEPTION -> user_email " + user_email + " exception_type -> " + exception_type + " message -> " + message + " subSystem -> " + subSystem + " audit type -> " + auditType);

    await clientForExcaptionLog.query('BEGIN');

    await clientForExcaptionLog.query(`INSERT INTO exception_logs (user_email, exception_type, message, sub_system, audit_type, log_type) VALUES ($1, $2, $3, $4, $5, $6)`, 
        [user_email, exception_type, message, subSystem, auditType, "error"]);

    await clientForExcaptionLog.query('COMMIT');
    clientForExcaptionLog.release();
}

module.exports = { logEvent, logException };