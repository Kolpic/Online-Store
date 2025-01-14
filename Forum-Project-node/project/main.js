const crypto = require('crypto');
const pool = require('./db');
const errors = require('./error_codes');
const sessions = require('./sessions');
const mailer = require('./mailer');
const express = require('express');
const { AssertUser, AssertDev, WrongUserInputException, DevException, PeerException, TemporaryException } = require('./exceptions');
const front_office = require('./front_office')
const bcrypt = require('bcryptjs');
const router = express.Router();
const backOfficeService = require('./backOfficeService');
const paypal = require('./paypal');
const { PayPal, Bobi} = require('./paymentProviders');

console.log("Pool imported in main.js:");

const SESSION_ID = "front_office_session_id";

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
        '/order': getOrderHandler,
        '/complete_order': getPaypalCompleteOrder,
        '/cancel_order': getPaypalCancelOrder,
    },
    POST: {
        '/registration': postRegistrationHandler,
        '/login': postLoginHandler,
        '/updateCartQuantity': postUpdateCarQuantityHandler,
        '/addToCart': postAddToCart,
        '/removeFromCart': postRemoveFromCart,
        '/cart': postCartHandler,
        '/finish_payment': postPaymentHandler,
        '/profile': postProfileHandler,
        // '/paypalme': postPaypalHandler,
        '/payment': postPaymentHandlerDef,
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
        console.log(error, "error");

        let sessionId = req.cookies[SESSION_ID];
        let userDataSession = await sessions.getCurrentUser(sessionId, client);
        let userData;

        if (userDataSession == null) {
            userData = "Guest";
        } else {
            userData = userDataSession.userRow.data;
        }

        await logException(userData, error.name, error.message, "site");

        await client.query('ROLLBACK');

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

    await logEvent(email, "", "User just registered in site");

    const bodyTemplateRow = await client.query(`SELECT body FROM email_template WHERE name = $1`, ["Verification Email"]);
    const body = bodyTemplateRow.rows[0];

    const emailData = await backOfficeService.mapEmailData(client, email, "Verification Email", body, user);

    await client.query(`INSERT INTO email_queue (name, data, status) VALUES ($1, $2, $3)`,
        [
            'Verification Email', 
            JSON.stringify(emailData),
            'pending'
        ]);

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

    let user = await sessions.getCurrentUser(sessionId, client);
    await logEvent(user.userRow.data, "", "User logged in site");

    res.cookie(SESSION_ID, sessionId, {
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
    let sessionId = req.cookies[SESSION_ID]
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

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

    res.json({userInformation});
}

async function getHomeHandler(req, res, next, client) {
    let result = await client.query(`SELECT DISTINCT(name) FROM categories`);

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

    console.log("priceMin", priceMin, "Number(priceMin) > 0", Number(priceMin) > 0, "priceMin !== null", priceMin !== null);

    AssertUser(sortOrder != "asc" || sortOrder != "desc", "Invalid sort order", errors.INVALID_SORT_ORDER);

    if (priceMin !== null) {
        AssertUser(Number(priceMin) > 0, "Price min can't be negative", errors.NEGATIVE_MIN_PRICE_ERROR);
    }
    if (priceMax !== null) {
        AssertUser(Number(priceMax) > 0, "Price max can't be negative", errors.NEGATIVE_MAX_PRICE_ERROR);
    }

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
    sessionId = req.cookies[SESSION_ID]
    authenticatedUser = await sessions.getCurrentUser(sessionId, client)

    await client.query(`DELETE FROM custom_sessions WHERE session_id = $1`,[authenticatedUser['userRow']['session_id']]);

    await logEvent(authenticatedUser.userRow.data, "", "User logged out from the site");

    res.cookie(SESSION_ID, "", {
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
    sessionId = req.cookies[SESSION_ID];
    authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    let profileData = await front_office.getProfileData(authenticatedUser, client);

    res.json({
        profileData,
    });
}

async function getCartHandler(req, res, next, client) {
    let sessionId = req.cookies[SESSION_ID] || null;
    let sessionIdUnauthenticatedUser = req.cookies['session_id_unauthenticated_user'] || null;

    AssertDev(sessionId != null && sessionIdUnauthenticatedUser == null || sessionId == null && sessionIdUnauthenticatedUser != null || sessionId == null && sessionIdUnauthenticatedUser == null, "We can't have two of the sessions");

    let cartData = null;
    if (sessionId != null) {
        console.log("Entered in normal session cart.html");
        let authenticatedUser = await sessions.getCurrentUser(sessionId, client);
        cartData = await front_office.prepareCartData(authenticatedUser, client);
    } else {
        console.log("Entered in anonymn session cart.html");
        cartData = await front_office.prepareCartData(sessionIdUnauthenticatedUser, client);
    }

    let promotion = await front_office.getPromotionForTheCurrentTime(client);

    return res.json({
        cartData,
        promotion
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
    let sessionId = req.cookies[SESSION_ID];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    let productId = req.body.productId;
    let quantity = req.body.quantity;

    let responseMessage = null;
    let newCartCount = null;

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

            responseMessage = await front_office.addToCart(sessionId, productId, quantity, authenticatedUser, client);
            newCartCount = await front_office.getCartItemsCount(client, sessionId);

            res.cookie('session_id_unauthenticated_user', sessionId, {
              httpOnly: true,
              sameSite: 'Lax',
            });

        // We already have anonymn session
        } else {
            console.log("sessionId IN already made anonymn session");
            responseMessage = await front_office.addToCart(sessionIdUnauthenticatedUser, productId, quantity, authenticatedUser, client);
            newCartCount = await front_office.getCartItemsCount(client, sessionIdUnauthenticatedUser);
        }
    // We have logged user
    } else {
        let userId = authenticatedUser['userRow']['user_id'];

        responseMessage = await front_office.addToCart(userId, productId, quantity, authenticatedUser, client);
        newCartCount = await front_office.getCartItemsCount(client, userId);
    }

    res.json({
      success: true,
      message: responseMessage,
      newCartCount: newCartCount,
    });

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

async function postCartHandler(req, res, next, client) {
    let sessionId = req.cookies[SESSION_ID];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    AssertUser(authenticatedUser != null, "You have to be logged in to make a purchase", errors.NOT_LOGGED_USER_FOR_MAKEING_ORDER)

    let { first_name, last_name, email, address, country_code, phone, town, discount_percentage } = req.body;

    console.log("discount_percentage", discount_percentage);

    const deliveryInformation = {
        first_name,
        last_name,
        email,
        phone,
        country_code,
        address,
        town,
        discount_percentage
    };

    let responsePostCart = await front_office.cart(deliveryInformation, authenticatedUser, client);

    console.log("responsePostCart", responsePostCart);

    const bodyTemplateRow = await client.query(`SELECT body FROM email_template WHERE name = $1`, ["Purchase Email"]);
    const body = bodyTemplateRow.rows[0];

    let mappingObj = {
        discount_percentage
    }

    const emailData = await backOfficeService.mapEmailData(client, email, "Purchase Email", body, responsePostCart, mappingObj);

    await client.query(`INSERT INTO email_queue (name, data, status) VALUES ($1, $2, $3)`,
        [
            'Purchase Email', 
            JSON.stringify(emailData),
            'pending'
        ]);

    return res.json({
        success: true,
        responsePostCart,
    });
}

async function getOrderHandler(req, res, next, client) {
    let sessionId = req.cookies[SESSION_ID];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    AssertUser(authenticatedUser != null, "You have to be logged in to make a purchase", errors.NOT_LOGGED_USER_FOR_MAKEING_PURCHASE);

    let order_id = req.query.order_id;

    let responseGetOrder = await front_office.getOrder(order_id, client);

    return res.json({
        success: true,
        responseGetOrder,
    });
}

async function postPaymentHandlerDef(req, res, next, client) {
    let sessionId = req.cookies[SESSION_ID];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    AssertUser(authenticatedUser != null, "You have to be logged in to make a purchase", errors.NOT_LOGGED_USER_FOR_MAKEING_PURCHASE);

    const { payment_method, order_id, payment_amount,token } = req.body;

    console.log("Entered in postPaymentHandler ->", "payment_method", payment_method, "order_id", order_id, "payment_amount", payment_amount, "token",token)

    const paymentFactory = {
        paypal: PayPal,
        bobi: Bobi
    };

    const PaymentClass = paymentFactory[payment_method];

    AssertUser(PaymentClass, `Unsupported payment method: ${payment_method}`, errors.INVALID_PAYMENT_METHOD);

    const paymentProvider = new PaymentClass({ order_id, client });

    let response = await paymentProvider.executePayment(order_id, payment_amount);

    if (PaymentClass instanceof Bobi) {
        await paymentProvider.postPaymentProcessing(order_id, response, authenticatedUser);
    }

    return res.json({ success: true, message: response.message, approvalUrl: response.approvalUrl });
}


async function postPaypalHandler(req, res, next, client) { // postPaypalHandler -> paymentSecondStep ? ili drugo ime abstractno ne konretno
    let sessionId = req.cookies[SESSION_ID];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    AssertUser(authenticatedUser != null, "You have to be logged in to make a purchase", errors.NOT_LOGGED_USER_FOR_MAKEING_PURCHASE);

    let orderId = req.body.order_id;
    console.log("orderId", orderId);

    const url = await paypal.createOrder(orderId, client);
    console.log("url", url);

    // res.redirect(url);
    return res.json ({
        success: true,
        redirectUrl: url
    });
}

async function getPaypalCompleteOrder(req, res, next, client) {
    let sessionId = req.cookies[SESSION_ID];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    AssertUser(authenticatedUser != null, "You have to be logged in to make a purchase", errors.NOT_LOGGED_USER_FOR_MAKEING_PURCHASE);

    const orderId = req.query.order_id;
    const token = req.query.token;

    await paypal.capturePayment(token);
    await client.query(`UPDATE orders SET status = 'Paid' WHERE order_id = $1`, [orderId]);

    let response = {};

    let order = await client.query(`SELECT * FROM orders WHERE order_id = $1`, [orderId]);
    let orderRow = order.rows;

    response.orderRow = orderRow;
    console.log("response", response);

    let orderItems = await client.query(`SELECT 
                                            order_items.id, 
                                            order_items.order_id, 
                                            order_items.product_id, 
                                            order_items.quantity          AS cart_quantity, 
                                            order_items.price, 
                                            order_items.vat,
                                            products.name                 AS name,
                                            currencies.symbol             AS symbol
                                    FROM order_items
                                        JOIN products   ON products.id          = order_items.product_id
                                        JOIN currencies ON products.currency_id = currencies.id
                                    WHERE order_id = $1
                                    `,[orderId]);

    let orderItemsRows = orderItems.rows;
    response.cart_items = orderItemsRows;
    console.log("response", response);

    shippingDetailsRow = await client.query(`
                                            SELECT 
                                                shipping_id, 
                                                order_id,
                                                email,
                                                first_name,
                                                last_name,
                                                town,
                                                phone,
                                                address,
                                                country_code_id, 
                                                code 
                                            FROM shipping_details 
                                                JOIN country_codes ON country_code_id = country_codes.id 
                                            WHERE shipping_details.order_id = $1
                                            `, [orderId]);

    console.log("shippingDetailsRow.rows[0]", shippingDetailsRow.rows[0]);
    
    response.shipping_details = shippingDetailsRow.rows;

    const bodyTemplateRow = await client.query(`SELECT body FROM email_template WHERE name = $1`, ["Payment Email"]);
    const body = bodyTemplateRow.rows[0];

    const userRow = await client.query(`SELECT * FROM users WHERE email = $1`, [authenticatedUser.userRow.data]);
    const user = userRow.rows[0];
    AssertDev(userRow.rows.length == 1, "Expect one on user");

    response.user_first_name = user.first_name;
    response.user_last_name = user.last_name;

    let total = 0;
    let totalWithVat = 0;

    orderItemsRows.forEach(row => {
        console.log("row");
        console.log(row);
        total += parseInt(row.cart_quantity) * parseFloat(row.price);
        totalWithVat += parseInt(row.cart_quantity) * parseFloat(row.price) + (parseFloat((row.vat / 100)) * (parseInt(row.cart_quantity) * parseFloat(row.price)));
    })
    let totalWithVatToFixed = totalWithVat.toFixed(2);
    
    response.total_sum = total;
    response.total_sum_with_vat = totalWithVatToFixed;
    response.vat_in_persent = 20;

    const emailData = await backOfficeService.mapEmailData(client, authenticatedUser.userRow.data, "Payment Email", body, response, orderRow[0]);

    await client.query(`INSERT INTO email_queue (name, data, status) VALUES ($1, $2, $3)`,
    [
    'Payment Email', 
    JSON.stringify(emailData),
    'pending'
    ]);

    res.send(`
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Payment Successful</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f8f9fa;
                }
                .message-box {
                    text-align: center;
                    background: #fff;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
                }
                h1 {
                    color: #28a745;
                    margin-bottom: 10px;
                }
                p {
                    color: #6c757d;
                    margin-bottom: 20px;
                }
            </style>
        </head>
        <body>
            <div class="message-box">
                <h1>Payment Successful!</h1>
                <p>Course purchased successfully.</p>
                <p>Redirecting to the homepage...</p>
            </div>
            <script>
                setTimeout(function() {
                    window.location.href = '/home.html';
                }, 3000);
            </script>
        </body>
        </html>
    `);
}

async function getPaypalCancelOrder(req, res, next, client) {
    res.redirect('/home.html');
}

async function postPaymentHandler(req, res, next, client) {
    let sessionId = req.cookies[SESSION_ID];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    AssertUser(authenticatedUser != null, "You have to be logged in to make a purchase", errors.NOT_LOGGED_USER_FOR_MAKEING_PURCHASE);

    let orderId = req.body.order_id;
    let paymentAmount = req.body.payment_amount;

    let response = await front_office.payOrder(orderId, paymentAmount, client);

    console.log("response in postPaymentHandler", response);

    shippingDetailsRow = await client.query(`
                                            SELECT 
                                                shipping_id, 
                                                order_id,
                                                email,
                                                first_name,
                                                last_name,
                                                town,
                                                phone,
                                                address,
                                                country_code_id, 
                                                code 
                                            FROM shipping_details 
                                                JOIN country_codes ON country_code_id = country_codes.id 
                                            WHERE shipping_details.order_id = $1
                                            `, [orderId]);

    console.log("shippingDetailsRow.rows[0]", shippingDetailsRow.rows[0]);

    response.shipping_details = shippingDetailsRow.rows;

    const bodyTemplateRow = await client.query(`SELECT body FROM email_template WHERE name = $1`, ["Payment Email"]);
    const body = bodyTemplateRow.rows[0];

    const userRow = await client.query(`SELECT * FROM users WHERE email = $1`, [authenticatedUser.userRow.data]);
    const user = userRow.rows[0];
    AssertDev(userRow.rows.length == 1, "Expect one on user");

    response.user_first_name = user.first_name;
    response.user_last_name = user.last_name;

    const emailData = await backOfficeService.mapEmailData(client, authenticatedUser.userRow.data, "Payment Email", body, response);

    await client.query(`INSERT INTO email_queue (name, data, status) VALUES ($1, $2, $3)`,
        [
            'Payment Email', 
            JSON.stringify(emailData),
            'pending'
        ]);

    return res.json({
        success: true,
        message: response.message,
    });
}

async function postProfileHandler(req, res, next, client) {
    let sessionId = req.cookies[SESSION_ID];
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    AssertUser(authenticatedUser != null, "You have to be logged in to edit your profile", errors.NOT_LOGGED_USER_FOR_MAKEING_PROFILE_CHANGES);

    const userDetails = {
        firstName: req.body.first_name,
        lastName: req.body.last_name,
        email: req.body.email,
        oldPassword: req.body.old_password,
        newPassword: req.body.new_password,
        address: req.body.address,
        phone: req.body.phone,
        countryCode: req.body.country_code
    };

    let result = await front_office.postProfile(userDetails, authenticatedUser, client);

    await logEvent(authenticatedUser.userRow.data, "", "User " + authenticatedUser.userRow.data + " " +  result.message)

    return res.json({
        success: true,
        message: result.message,
    });
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
        [user_email, exception_type, message, subSystem, auditType,"error"]);

    await clientForExcaptionLog.query('COMMIT');
    clientForExcaptionLog.release();
}

async function logEvent(user_email, exception_type, message) {
    let clientForExcaptionLog = await pool.connect();
    await clientForExcaptionLog.query('BEGIN');

    console.log("Logged event -> " + message);
    await clientForExcaptionLog.query(`INSERT INTO exception_logs (user_email, exception_type, message, sub_system, log_type) VALUES ($1, $2, $3, $4, $5)`, 
        [user_email, exception_type, message, "site", "event"]);

    await clientForExcaptionLog.query('COMMIT');
    clientForExcaptionLog.release();
}

process.on('uncaughtException', async (error) => {
    console.error("error in uncaughtException");
    console.error(error);
    try {
        await logException("Guest", error.name, error.message, "site");
    } catch (loggingError) {
        console.error("Error while logging uncaught exception:", loggingError);
    }
});

process.on('unhandledRejection', async (error) => {
    console.error("error in unhandledRejection --");
    console.error(error);
    try {
        await logException("Guest", error.name || "Error", error.message || reason, "site");
    } catch (loggingError) {
        console.error("Error while logging unhandled rejection:", loggingError);
    }
});

module.exports = {
    router,
    getRegistrationHandler,
    postRegistrationHandler,
    getRefreshCaptchaHandler,
};