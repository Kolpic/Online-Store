const crypto = require('crypto');
const pool = require('./db');
const express = require('express');
const utils = require('./utils');
const front_office = require('./front_office')
const { WrongUserInputException } = require('./exceptions')

const router = express.Router();

console.log("Pool imported in main.js:");  

const urlToFunctionMapFrontOffice = {
    GET: {
        '/registration': getRegistrationHandler,
    },
    POST: {
        '/registration': postRegistrationHandler,
    }
};

function mapUrlToFunction(req) {
    const methodMap = urlToFunctionMapFrontOffice[req.method];
    if (methodMap) {
        return methodMap[req.path];
    } else {
        utils.AssertUser(false, "Invalid url")
    };
}

router.use(async (req, res, next) => {
	console.log("Pool inside router.use in main.js:");

	let client;
	try {
		client = await pool.connect();
		await client.query('BEGIN');
        let handler = mapUrlToFunction(req);
        await handler(req, res, next, client);
        await client.query('COMMIT');
	} catch (error) {
		await client.query('ROLLBACK');
        if (error instanceof WrongUserInputException) {
            return res.status(400).json({error: error.message});
        } else {
            return res.status(500).json({error: 'Internal Server Error'});
        }

	} finally {
        if (client) {
            client.release();
        }
    }
});

async function getRegistrationHandler(req, res, next, client) {
	let user_ip = req.ip;

	let firstCaptchaNumber = Math.floor(Math.random() * 101);
    let secondCaptchaNumber = Math.floor(Math.random() * 101);

    let preparedData = await front_office.prepareRegistrationData(client=client, firstCaptchaNumber=firstCaptchaNumber, secondCaptchaNumber=secondCaptchaNumber);
    return res.json({
        country_codes: preparedData.country_codes,
        captcha: {
            first: preparedData.first_captcha_number,
            second: preparedData.second_captcha_number
        },
        captcha_id: preparedData.captcha_id
    });
};

async function postRegistrationHandler(req, res, next, client) {
    const user_ip = req.ip;
    const { first_name, last_name, email, password, confirm_password, address, country_code, phone, gender, captcha, captcha_id } = req.body;

    const hashed_password = await utils.hashPassword(password);
    const verification_code = crypto.randomBytes(24).toString('hex');

    await front_office.registration(client, {
            first_name, last_name, email, password, confirm_password, 
            phone, gender, captcha_id, captcha, user_ip, 
            hashed_password, verification_code, country_code, address
        });

    return res.status(201).json({ 
        message: "User registered successfully. Please verify your email to complete the registration.", 
        redirect_url: '/verify.html'
    });
}

module.exports = {
    router,
    getRegistrationHandler,
    postRegistrationHandler,
};