const pool = require('./db');
const express = require('express');
const utils = require('./utils');
// const { AssertDev, AssertUser, AsserPeer } = require('./utils');
// const { WrongUserInputException, DevException, PeerException } = require('./exceptions');
const front_office = require('./front_office')

const router = express.Router();

console.log("Pool imported in main.js:");  

const urlToFunctionMapFrontOffice = {
    '/registration': registrationHandler,
    // '/refresh_captcha': refreshCaptchaHandler,
    // '/verify': verifyHandler,
    // '/login': loginHandler,
    // '/home': homeHandler,
    // '/logout': logoutHandler,
};

function mapFunction(url, isBackOffice = false) {
	const map = isBackOffice ? urlToFunctionMapBackOffice : urlToFunctionMapFrontOffice;
    return map[url];
}


function mapUrlToFunction(req) {
    return urlToFunctionMapFrontOffice[req.path];
}

router.use(async (req, res, next) => {
	console.log("Pool inside router.use in main.js:");

	let client;
	try {
		client = await pool.connect();

		console.log("ENTERED IN TRY CATCH");

		await client.query('BEGIN');

		// const sessionID = req.cookies['session_id'];
        // let authenticatedUser = await getCurrentUser(sessionID);
        
        // let isBackOffice = false;
        // const handler = mapFunction(req.path, isBackOffice);

        let handler = mapUrlToFunction(req);

        utils.AssertUser(handler, "Invalid url");

        await handler(req, res, next, client);

        await client.query('COMMIT');

	} catch (error) {

		console.error(`Error processing request for ${req.path}:`, error);
		res.status(500).send('Internal Server Error');

		await client.query('ROLLBACK');

	} finally {
        client.release();
    }
});

async function registrationHandler(req, res, next, client) {
	let user_ip = req.ip;

	if (req.method == 'GET') {
		let firstCaptchaNumber = Math.floor(Math.random() * 101);
        let secondCaptchaNumber = Math.floor(Math.random() * 101);

        let preparedData = await front_office.prepareRegistrationData(client=client, firstCaptchaNumber=firstCaptchaNumber, secondCaptchaNumber=secondCaptchaNumber);

        return res.render('registration', {
            country_codes: preparedData.country_codes,
            // recovery_data: "",
            captcha: {
                first: preparedData.first_captcha_number,
                second: preparedData.second_captcha_number
            },
            captcha_id: preparedData.captcha_id
        });

	} else if (req.method == 'POST') {

	} else {
		utils.AssertUser(false, "Invalid method");
	}
};

module.exports = router;