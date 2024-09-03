// Prepare registration data
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


module.exports = {
    prepareRegistrationData,
    registration,
}