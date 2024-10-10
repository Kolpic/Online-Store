const crypto = require('crypto');
const pool = require('./db');
const errors = require('./error_codes');
const sessions = require('./sessions');
const mailer = require('./mailer');
const express = require('express');
const { AssertUser, AssertDev, WrongUserInputException } = require('./exceptions');
const front_office = require('./front_office')
const bcrypt = require('bcrypt');
const router = express.Router();

console.log("Pool imported in main.js:");  

const urlToFunctionMapFrontOffice = {
    GET: {
        '/registration': getRegistrationHandler,
        '/refresh_captcha': getRefreshCaptchaHandler,
        '/home': getHomeHandler,
        '/header': getHeaderHandler,
        '/logout': getLogoutHandler,
        '/profile': getProfileHandler,
        '/verify': getVerificationHandler,
        '/cart': getCartHandler,
    },
    POST: {
        '/registration': postRegistrationHandler,
        '/login': postLoginHandler,
        '/updateCartQuantity': postUpdateCarQuantityHandler,
        '/addToCart': postAddToCart,
        '/removeFromCart': postRemoveFromCart,
    }
};

function mapUrlToFunction(req) {
    const methodMap = urlToFunctionMapFrontOffice[req.method];

    console.log("req.path");
    console.log(req.path);

    let basePathSplitted = req.path.split('/');
    let basePath = basePathSplitted[1];
    let page = basePathSplitted[2] || 1;

    req.params.page = page

    if (basePath) {
        let matchedHandler = methodMap[`/${basePath}`];
        console.log(matchedHandler)

        if (matchedHandler) {
            return matchedHandler;
        }
    }
    // return methodMap[req.path];
}

router.use(async (req, res, next) => {
	console.log("Pool inside router.use in main.js:");

	let client;
    let cookieObj = {};

	try {
        let cookieString = req.headers.cookie;

        if (cookieString) {
            // Split cookie into individual key-value pairs
            cookieString.split(';').forEach(cookie => {
                let [name, value] = cookie.split('=');
                name = name.trim();
                cookieObj[name] = value;
            });
        }

        // Assign the parsed cookie object to req.cookies
        req.cookies = cookieObj

		client = await pool.connect();

		await client.query('BEGIN');

        let handler = mapUrlToFunction(req);

        AssertUser(handler != undefined, "Invalid url", errors.INVALID_URL)

        if (typeof handler === 'function') {
            await handler(req, res, next, client);
        } else {
            return;
        }

        await client.query('COMMIT');
	} catch (error) {
		await client.query('ROLLBACK');
        console.log(error, "error")
        if (error instanceof WrongUserInputException) {
            return res.status(400).json({
                error_message: error.message, 
                error_code: error.errorCode
            });
        } else {
            return res.status(500).json({error_message: 'Internal Server Error'});
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

    const saltRounds = 10;

    const hashed_password = await bcrypt.hash(password, saltRounds);
    const verification_code = crypto.randomBytes(24).toString('hex');

    const user = {
        first_name,
        last_name,
        email,
        password,
        confirm_password,
        phone,
        gender,
        captcha_id,
        captcha,
        user_ip,
        hashed_password,
        verification_code,
        country_code,
        address
    };

    await front_office.registration(client, user);

    let resultEmail = await mailer.sendEmail(email, verification_code);

    return res.status(201).json({
        success: true,
        message: "User registered successfully. Please verify your email to complete the registration.",
        email: email, 
    });
}

async function getRefreshCaptchaHandler(req, res, next, client) {

    let firstNumber = Math.floor(Math.random() * 101);
    let secondNumber = Math.floor(Math.random() * 101);

    let preparedData = await front_office.refreshCaptcha(client, firstNumber, secondNumber);

    return res.json({
        'first': firstNumber,
        'second': secondNumber,
        'captcha_id': preparedData.newCaptchaId
    });
}

async function getVerificationHandler(req, res, next, client) {
    const { token } = req.query;

    verification_code = token;

    let result = await front_office.verify(verification_code, client);

    let status = result.success == true ? 200 : 400;

    return res.status(status).json({
        success: result.success,
        message: result.message,
    });
}

async function postLoginHandler(req, res, next, client) {
    let email = req.body.email;
    let password = req.body.password;

    let userData = await front_office.login(client, email, password);
    let sessionId = await sessions.createSession(email, true, client);

    let responseMessage = 'You logged in successfully';
    let redirectUrl = '/home.html';

    if (req.cookies != undefined) {
        let sessionIdUnauthenticatedUser = req.cookies['session_id_unauthenticated_user'];

        if (userData && sessionIdUnauthenticatedUser != undefined) {
            userId = userData['id'];
            await front_office.mergeCart(userId, sessionIdUnauthenticatedUser, client);
            responseMessage = 'You logged in successfully, these are the items you selected before you logged in.';
            redirectUrl = '/cart.html';
            res.clearCookie('session_id_unauthenticated_user');
        }
    }

    res.cookie('session_id', sessionId, {
      httpOnly: true,
      sameSite: 'Lax',
    });

    res.json({
      success: true,
      message: responseMessage,
      redirectUrl: redirectUrl,
    });
}

async function getHeaderHandler(req, res, next, client) {
    sessionId = req.cookies['session_id']
    authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    let userInformation = {
        firstName: "",
        lastName: "",
        email: "",
        categories: null,
        cartCount: 0
    };

    let result = await client.query(`SELECT DISTINCT(category) FROM products`);

    if (authenticatedUser === null) {
        let sessionIdUnauthenticatedUser = req.cookies['session_id_unauthenticated_user'];

        userInformation.categories = result.rows.map(row => row.category);

        userInformation.cartCount = await front_office.getCartItemsCount(client, sessionIdUnauthenticatedUser);
    } else {
        email = authenticatedUser['userRow']['data']
        query = `SELECT * FROM users WHERE email = $1`

        let userResult = await client.query(query, [email]);

        userInformation.categories = result.rows.map(row => row.category);

        let userId = userResult.rows[0].id;

        userInformation.firstName = userResult.rows[0].first_name;
        userInformation.lastName = userResult.rows[0].last_name;
        userInformation.email = email;
        userInformation.cartCount = await front_office.getCartItemsCount(client, userId);

    }

    console.log("userInformation");
    console.log(userInformation);

    res.json({userInformation});
}

async function getHomeHandler(req, res, next, client) {
    let result = await client.query(`SELECT DISTINCT(category) FROM products`);

    categories = result.rows.map(row => row.category);

    let page = parseInt(req.params.page) || 1;

    let sortBy = req.query.sort || "id";
    let sortOrder = req.query.order || "asc";
    let productsPerPage = req.query.products_per_page || 10;
    let offset = (page - 1) * productsPerPage;

    let productName = req.query.product_name || null;
    let productCategory = req.query.category || null;
    let priceMin = req.query.price_min || null;
    let priceMax = req.query.price_max || null;

    let productsData = await front_office.prepareHomeData(client, {sortBy, sortOrder, productsPerPage, page, offset, productName, productCategory, priceMin, priceMax})

    res.json({
        products: productsData.products,
        productsPerPage,
        page,
        totalPages: productsData.totalPages,
        sortBy,
        sortOrder,
        productName,
        productCategory,
        categories
    });
}

async function getLogoutHandler(req, res, next, client) {
    sessionId = req.cookies['session_id']
    authenticatedUser = await sessions.getCurrentUser(sessionId, client)

    await client.query(`DELETE FROM custom_sessions WHERE session_id = $1`,[authenticatedUser['userRow']['session_id']]);

    res.cookie('session_id', "", {
      httpOnly: true,
      sameSite: 'Lax',
    });

    res.json({
      success: true,
      message: "Successfully logged out",
      redirectUrl: "/login.html",
    });
}

async function getProfileHandler(req, res, next, client) {
    sessionId = req.cookies['session_id'];
    authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    let profileData = await front_office.getProfileData(authenticatedUser, client);

    res.json({
        profileData,
    });
}

async function getCartHandler(req, res, next, client) {
    let sessionId = req.cookies['session_id'] || null;
    let sessionIdUnauthenticatedUser = req.cookies['session_id_unauthenticated_user'] || null;
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    console.log("sessionId");
    console.log(sessionId);

    console.log("authenticatedUser");
    console.log(authenticatedUser);

    console.log("sessionIdUnauthenticatedUser");
    console.log(sessionIdUnauthenticatedUser);

    let cartData = null;
    if (sessionId === null && authenticatedUser === null) {
        console.log("Entered in anonymn session cart.html");
        cartData = await front_office.prepareCartData(sessionIdUnauthenticatedUser, client);
    } else {
        console.log("Entered in normal session cart.html");
        cartData = await front_office.prepareCartData(authenticatedUser, client);
    }

    console.log(cartData);

    res.json({
        cartData,
    })
}

async function postUpdateCarQuantityHandler(req, res, next, client) {
    let itemId = req.body.itemId;
    let quantity = parseInt(req.body.quantity);

    let resultUpdate = await front_office.updateCartQuantity(itemId, quantity, client);

    return res.json({
        success: true,
        new_total: resultUpdate.newTotal,
        vat_rate: resultUpdate.vatRate, 
        price_per_item: resultUpdate.pricePerItem,
        quantity: quantity,
        item_id: itemId
    });
}

async function postAddToCart(req, res, next, client) {
    let sessionId = req.cookies['session_id'];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    console.log("authenticatedUser");
    console.log(authenticatedUser);

    let productId = req.body.productId;
    let quantity = req.body.quantity;

    // We don't have logged user
    if (authenticatedUser === null) {
        let sessionIdUnauthenticatedUser = req.cookies['session_id_unauthenticated_user'] || null;

        console.log("sessionIdUnauthenticatedUser");
        console.log(sessionIdUnauthenticatedUser);

        // Make anonymn session
        if (sessionIdUnauthenticatedUser === null) {
            let sessionId = await front_office.uuidv4();

            console.log("sessionId IN Make anonymn session");
            console.log(sessionId);

            let responseMessage = await front_office.addToCart(sessionId, productId, quantity, authenticatedUser, client);
            let newCartCount = await front_office.getCartItemsCount(client, sessionId);

            res.cookie('session_id_unauthenticated_user', sessionId, {
              httpOnly: true,
              sameSite: 'Lax',
            });

            res.json({
              success: true,
              message: responseMessage,
              newCartCount: newCartCount,
            });
        // We already have anonymn session
        } else {
            console.log("sessionId IN already made anonymn session");
            let responseMessage = await front_office.addToCart(sessionIdUnauthenticatedUser, productId, quantity, authenticatedUser, client);
            let newCartCount = await front_office.getCartItemsCount(client, sessionIdUnauthenticatedUser);

            res.json({
              success: true,
              message: responseMessage,
              newCartCount: newCartCount,
            });
        }
    // We have logged user
    } else {
        let userId = authenticatedUser['userRow']['user_id'];

        let responseMessage = await front_office.addToCart(userId, productId, quantity, authenticatedUser, client);
        let newCartCount = await front_office.getCartItemsCount(client, userId);

        res.json({
          success: true,
          message: responseMessage,
          newCartCount: newCartCount,
        });
    }

    return res;
}

async function postRemoveFromCart(req, res, next, client) {
    let productId = req.body.itemId;

    let result = await front_office.removeFromCart(productId, client);

    return res.json({
        success: true,
        message: result,
    });
}

module.exports = {
    router,
    getRegistrationHandler,
    postRegistrationHandler,
    getRefreshCaptchaHandler,
};