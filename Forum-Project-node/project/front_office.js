const utils = require('./utils');
const pool = require('./db');

async function prepareRegistrationData(client, firstCaptchaNumber, secondCaptchaNumber) {
    let result = await client.query(
        "INSERT INTO captcha (first_number, second_number, result) VALUES ($1, $2, $3) RETURNING id, result",
        [firstCaptchaNumber, secondCaptchaNumber, firstCaptchaNumber + secondCaptchaNumber]
    );

    let captchaRow = result.rows[0];

    let countryCodesResult = await client.query("SELECT id, name, code FROM country_codes");
    let countryCodes = countryCodesResult.rows;

    let prepared_data =  {
        first_captcha_number: firstCaptchaNumber,
        second_captcha_number: secondCaptchaNumber,
        captcha_id: captchaRow.id,
        country_codes: countryCodes
    };

    return prepared_data;
}

async function registration(client, {first_name, last_name, email, password, confirm_password, 
    phone, gender, captcha_id, captcha, user_ip, 
    hashed_password, verification_code, country_code, address
    }) {

    const captcha_settings_row = await client.query("SELECT * FROM captcha_settings");

    const attemptsResult = await client.query("SELECT * FROM captcha_attempts WHERE ip_address = $1", [user_ip]);

    const userRes = await client.query("SELECT * FROM users WHERE email = $1", [email]);
    const userRow = userRes.rows[0];

    utils.AssertUser(!userRow, "There is already registration with this email");

    const regexPhone = /^\d{7,15}$/;

    utils.AssertUser(password.length >= 7 && password.length <= 20, "Password must be between 7 and 20 characters");
    utils.AssertUser(password === confirm_password, "Password and Confirm Password fields are different");
    utils.AssertUser(regexPhone.test(phone), "Phone number format is not valid. The number should be between 7 and 15 digits");
    utils.AssertUser(gender === 'male' || gender === 'female' || gender === 'other', "Gender must be Male or Female or Prefer not to say");
    utils.AssertUser(first_name.length >= 3 && first_name.length <= 50, "First name must be between 3 and 50 characters");
    utils.AssertUser(last_name.length >= 3 && last_name.length <= 50, "Last name must be between 3 and 50 characters");
    
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b/i;
    utils.AssertUser(emailRegex.test(email), "Email is not valid");

    let attemptRecord = undefined
    if (attemptsResult.rows.length > 0) {
        attemptRecord = attemptsResult.rows[0]['attempts'];
    } else {
        attemptRecord = 0;
    }

    let attempts = 0;
    const maxAttempts = parseInt(captcha_settings_row.rows[0]['value']);
    const timeoutMinutes = parseInt(captcha_settings_row.rows[1]['value']);

    if (attemptRecord > 0) {
        attempts_db = attemptsResult.rows[0]['attempts'];
        last_attempt_time = attemptsResult.rows[0]['last_attempt_time'];

        attempts = attempts_db;

        const timeSinceLastAttempt = new Date() - new Date(last_attempt_time);
        const timeoutMs = timeoutMinutes * 60 * 1000;

        utils.AssertUser(!(attempts >= maxAttempts && timeSinceLastAttempt < timeoutMs), `You typed wrong captcha several times, now you have timeout ${timeoutMinutes} minutes`);

        if (timeSinceLastAttempt >= timeoutMs) {
            attempts = 0;
        }
    }

    const captchaRes = await client.query("SELECT result FROM captcha WHERE id = $1", [captcha_id]);
    const expectedCaptcha = captchaRes.rows[0].result;

    if (parseInt(captcha) !== expectedCaptcha) {
        let clientForCaptcha = await pool.connect();

        const newAttempts = attempts + 1;

        if (attemptRecord > 0) {
            await client.query("UPDATE captcha_attempts SET attempts = $1, last_attempt_time = CURRENT_TIMESTAMP WHERE id = $2", [newAttempts, attemptsResult.rows[0]['id']]);
        } else {
            await client.query("INSERT INTO captcha_attempts (ip_address, last_attempt_time, attempts) VALUES ($1, CURRENT_TIMESTAMP, $2)", [user_ip, newAttempts]);
        }

        await client.query('COMMIT');

        utils.AssertUser(false, "Invalid CAPTCHA. Please try again");
    } else {
        if (attemptRecord > 0) {
            await client.query("DELETE FROM captcha_attempts WHERE id = $1", [attemptRecord.id]);
        }
    }

    await client.query('COMMIT');

    const countryCodeRes = await client.query("SELECT * FROM country_codes WHERE code = $1", [country_code]);
    const countryCodeRow = countryCodeRes.rows[0];
    const countryCodeId = countryCodeRow.id;

    await client.query(`
        INSERT INTO users 
            (first_name, last_name, email, password, verification_code, address, gender, phone, country_code_id) 
        VALUES 
            ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        `, 
        [first_name, last_name, email, hashed_password, verification_code, address, gender, phone, countryCodeId]
    );
}

module.exports = {
    prepareRegistrationData,
    registration,
}