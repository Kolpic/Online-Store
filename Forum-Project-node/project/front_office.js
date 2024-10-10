const { AssertUser, AssertDev } = require('./exceptions');
const errors = require('./error_codes');
const pool = require('./db');
const bcrypt = require('bcrypt');

async function prepareRegistrationData(client, firstCaptchaNumber, secondCaptchaNumber) {

    AssertDev(firstCaptchaNumber !== "", "First captcha number is empty")
    AssertDev(secondCaptchaNumber !== "", "Second captcha number is empty")

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

async function registration(client, user) {
    const {
        first_name, last_name, email, password, confirm_password,
        phone, gender, captcha_id, captcha, user_ip,
        hashed_password, verification_code, country_code, address
    } = user;

    AssertDev(first_name !== "", "First name is empty")
    AssertDev(last_name !== "", "Last name is empty")
    AssertDev(email !== "", "Email is empty")
    AssertDev(password !== "", "Password is empty")
    AssertDev(confirm_password !== "", "Confirm password is empty")
    AssertDev(phone !== "", "Phone is empty")
    AssertDev(captcha_id !== "", "Captcha Id is empty")
    AssertDev(captcha !== "", "Captcha is empty")
    AssertDev(user_ip !== "", "User ip is empty")
    AssertDev(hashed_password !== "", "Hashed password is empty")
    AssertDev(verification_code !== "", "Verification code is empty")
    AssertDev(country_code !== "", "Country code is empty")

    const captcha_settings_row = await client.query("SELECT * FROM captcha_settings");

    const attemptsResult = await client.query("SELECT * FROM captcha_attempts WHERE ip_address = $1", [user_ip]);

    const userRes = await client.query("SELECT * FROM users WHERE email = $1", [email]);
    const userRow = userRes.rows[0];

    AssertUser(!userRow, "There is already registration with this email", errors.REGISTERED_EMAIL_ERROR_CODE);

    const regexPhone = /^\d{7,15}$/;

    AssertUser(password.length >= 7 && password.length <= 20, "Password must be between 7 and 20 characters", errors.PASSWORD_LENGTH_ERROR_CODE);
    AssertUser(password === confirm_password, "Password and Confirm Password fields are different", errors.PASSWORD_MATCH_ERROR_CODE);
    AssertUser(regexPhone.test(phone), "Phone number format is not valid. The number should be between 7 and 15 digits", errors.PHONE_FORMAT_ERROR_CODE);
    AssertUser(gender === 'male' || gender === 'female' || gender === 'other' || gender === '', "Gender must be empty or Male or Female or Prefer not to say", errors.GENDER_ERROR_CODE);
    AssertUser(first_name.length >= 3 && first_name.length <= 50, "First name must be between 3 and 50 characters", errors.NAME_LENGTH_ERROR_CODE);
    AssertUser(last_name.length >= 3 && last_name.length <= 50, "Last name must be between 3 and 50 characters", errors.NAME_LENGTH_ERROR_CODE);
    
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b/i;
    AssertUser(emailRegex.test(email), "Email is not valid", errors.INVALID_EMAIL_ERROR_CODE);

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

        AssertUser(!(attempts >= maxAttempts && timeSinceLastAttempt < timeoutMs), `You typed wrong captcha several times, now you have timeout ${timeoutMinutes} minutes`, errors.CAPTCHA_TIMEOUT_ERROR_CODE);

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

        AssertUser(false, "Invalid CAPTCHA. Please try again", errors.CAPTCHA_ERROR_CODE);
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

async function refreshCaptcha(client, firstNumber, secondNumber) {

    AssertDev(firstNumber !== "", "First captcha number is empty")
    AssertDev(secondNumber !== "", "Second captcha number is empty")

    let result = await client.query(`
        INSERT INTO captcha
            (first_number, second_number, result) 
        VALUES 
            ($1, $2, $3) 
        RETURNING id
        `, 
        [firstNumber, secondNumber, firstNumber + secondNumber]
    );

    let newCaptchaId = result.rows[0].id;

    let preparedData =  {
        newCaptchaId: newCaptchaId,
    };

    return preparedData
}

async function verify(verification_code, client) {
    if (!verification_code) {
        return response = {success: false, message: "No verification token provided"};
    }

    const result = await client.query("SELECT * FROM users WHERE verification_code = $1", [verification_code]);

    if (result.rows.length === 0) {
        return response = {success: false, message: "No verification token provided"};
    }

    await client.query("UPDATE users SET verification_status = true WHERE verification_code = $1", [verification_code]);

    return response = {success: true, message: "Email verified successfully. You can now log in."};
}

async function login(client, email, password) {
    AssertDev(email !== "", "Email is empty");
    AssertDev(password !== "", "Password is empty");

    let userData = await client.query(`SELECT * FROM users WHERE email = $1`, [email]);
    let userRow = userData.rows[0]

    AssertUser(userRow !== undefined, "There is no registration with this mail", errors.ALREADY_REGISTERED_EMAIL);
    AssertUser(await bcrypt.compare(password, userRow['password']), "Invalid email or password")
    AssertUser(userRow['verification_status'], "Your account is not verified or has been deleted", errors.NOT_VERIFIED_ACCOUNT)

    return userRow;
}

async function prepareHomeData(client, filters) {
    let { sortBy, sortOrder, productsPerPage, offset, productName, productCategory, priceMin, priceMax } = filters;

    AssertUser(productsPerPage < 50, "You can view 50 products max", errors.TOO_MANY_REQUESTED_PRODUCTS);

    let paramaterCounter = 1; 
    const queryParams = [];
    const filterConditions = [
        { value: productName, condition: `products.name ILIKE $`, pattern: `%${productName}%` },
        { value: productCategory, condition: `products.category ILIKE $`, pattern: `%${productCategory}%` },
        { value: priceMin, condition: `price >= $`, pattern: priceMin },
        { value: priceMax, condition: `price <= $`, pattern: priceMax }
    ];

    let whereClauses = filterConditions.reduce((clauses, filter) => {
        if (filter.value != null) {

            clauses.push(`${filter.condition}${paramaterCounter}`);
            queryParams.push(filter.pattern);
            paramaterCounter++;
        }
        return clauses;
    }, []);

    let whereClause = whereClauses.length > 0 ? `WHERE ${whereClauses.join(' AND ')}` : '';

    let productQuery = `
        SELECT 
            products.id, 
            products.name, 
            products.price, 
            products.quantity, 
            products.category,
            products.image_path, 
            currencies.symbol, 
            settings.vat 
        FROM products
            JOIN currencies ON products.currency_id = currencies.id
            JOIN settings ON products.vat_id = settings.id
        ${whereClause}
        ORDER BY ${sortBy} ${sortOrder}
        LIMIT $${paramaterCounter} OFFSET $${paramaterCounter + 1};
    `;

    queryParams.push(productsPerPage, offset);
    
    let productsResult = await client.query(productQuery, queryParams);

    let countQuery = `SELECT COUNT(*) FROM products ${whereClause};`;
    let countResult = await client.query(countQuery, queryParams.slice(0, -2));

    let totalProducts = parseInt(countResult.rows[0].count);
    let totalPages = Math.ceil(totalProducts / productsPerPage);

    return {
        products: productsResult.rows,
        totalPages
    };
}

async function getCartItemsCount(client, userId) {
    query = `
            SELECT 
                products.name, 
                products.price, 
                cart_items.quantity, 
                products.id 
            FROM carts 
                JOIN cart_items  ON carts.cart_id         = cart_items.cart_id 
                JOIN products    ON cart_items.product_id = products.id 
            WHERE
    `

    if (typeof userId === 'string') {
        query += 'carts.session_id = $1';
    } else {
        query += 'carts.user_id = $1';
    }

    let result = await client.query(query, [userId]);
    let items = result.rows;

    AssertDev(items.length <= 1000, 'Fetched too many rows in getCartItemsCount function');

    return items.length;
}

async function getProfileData(authenticatedUser, client) {
    let userData = await client.query(`SELECT * FROM users WHERE email = $1`, [authenticatedUser['userRow']['data']]);
    let userDataResult = userData.rows;
    let countryCodes = await client.query(`SELECT * FROM country_codes`);
    let countryCodesData = countryCodes.rows;

    return {
        userDataResult,
        countryCodesData
    }
}

async function prepareCartData(authenticatedUser, client) {
    let countryCodes = await client.query(`SELECT * FROM country_codes`);
    let vat = await client.query(`SELECT vat FROM settings`);

    let cartItems = null;
    let totalSum = 0;
    let totalSumWithVat = 0;
    let firstName = "";
    let lastName = "";

    if (typeof authenticatedUser === 'string') {
        cartItems = await getCart(authenticatedUser, client);
    } else {
        let userData = await client.query(`SELECT * FROM users WHERE email = $1`, [authenticatedUser['userRow']['data']]);

        let userId = userData.rows[0]['id'];

        cartItems = await getCart(userId, client);

        firstName = userData.rows['first_name'];
        lastName = userData.rows['last_name'];
    }

    cartItems.forEach((item) => {
        let vatFloat = (parseFloat(item['vat'] / 100));               // 20 / 100 = 0,2
        let itemsSumWithoutVat = item['price'] * item['quantity'];    // 47,90 * 1 = 47,90
        totalSum += itemsSumWithoutVat;                               // sum 
        let vat = itemsSumWithoutVat * vatFloat;                      // 47,90 * 0,2 = 9,58
        totalSumWithVat += itemsSumWithoutVat + vat;                  // 47,90 + 9,58 = 57,48
    });

    let dataToReturn = {
        cartItems,
        totalSumWithVat,
        totalSum,
        countryCodes: countryCodes.rows,
        firstName,
        lastName,
        vatInPersent: vat.rows[0].vat,
    }

    return dataToReturn;
}

async function getCart(userId, client) {
    query = `
            SELECT 
                products.name, 
                products.price, 
                cart_items.quantity, 
                products.id,
                currencies.symbol,
                settings.vat
            FROM carts 
                JOIN cart_items  ON carts.cart_id         = cart_items.cart_id 
                JOIN products    ON cart_items.product_id = products.id
                JOIN currencies  ON products.currency_id  = currencies.id
                JOIN settings    ON products.vat_id       = settings.id
            WHERE
    `
    if (typeof userId === 'string') {
        query += 'carts.session_id = $1';
    } else {
        query += 'carts.user_id = $1';
    }

    let items = await client.query(query, [userId]);

    let itemsData = items.rows;

    AssertDev(itemsData.length <= 1000, "Fetched too many rows in viewCart function");

    return itemsData;
}

async function updateCartQuantity (itemId, quantity, client) {
    AssertDev(itemId !== undefined, "itemId is undefined in postUpdateCarQuantityHandler");
    AssertDev(quantity !== undefined, "quantity is undefined in postUpdateCarQuantityHandler");

    AssertUser(quantity > 0, "You can't enter quantity zero or below", errors.INVALID_PRODUCT_QUANTITY);

    let result = await client.query(`SELECT price, settings.vat FROM products JOIN settings ON products.vat_id=settings.id WHERE products.id = $1`, [itemId]);

    let price = parseFloat(result.rows[0].price);
    let vatRate = result.rows[0].vat;

    // let newTotal = price * vatRate;
    let vatAmount = price * (vatRate / 100);
    let totalWithVAT = (price + vatAmount) * quantity;

    await client.query(`UPDATE cart_items SET quantity = $1 WHERE product_id = $2`, [quantity, itemId]);

    return {
        newTotal: totalWithVAT,
        vatVate: vatRate, 
        pricePerItem: price,
    };
}

async function uuidv4() {
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
    (+c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> +c / 4).toString(16)
  );
}

async function addToCart(userId, productId, quantity, authenticatedUser, client) {
    let vatRow = await client.query(`SELECT vat FROM settings`);
    let vat = vatRow.rows[0].vat;

    let cartId = null;
    // Not logged user -> anonymn session
    if (authenticatedUser === null) {
        console.log("Not logged user -> anonymn session");

        let cart = await client.query(`SELECT * FROM carts WHERE session_id = $1`, [userId]);
        let cartRow = cart.rows;

        // let userId = null;
        // Check if we have cart with anonymn session
        if (cartRow.length == 0) {
            console.log("ENTERED inserted new cart with anonym sesession");

            let result = await client.query(`INSERT INTO carts(session_id) VALUES ($1) RETURNING cart_id`, [userId]);
            cartId = result.rows[0].cart_id;
        } else {
            console.log("ENTERED already present cart");

            cartId = cartRow[0].cart_id;
        }

    // Loged user -> normal session
    } else {
        console.log("Loged user -> normal session");

        let cart = await client.query(`SELECT * FROM carts WHERE user_id = $1`, [userId]);
        let cartRow = cart.rows;

        // Not present cart, we have to make one
        if (cartRow.length == 0) {
            console.log("ENTERED CREATING CART FOR AUTH USER");

            cartId = await client.query(`INSERT INTO carts(user_id) VALUES ($1) RETURNING cart_id`, [userId]);

        // Present cart, we insert in it 
        } else {
            console.log("ENTERED ALREADY CREATED CART FOR AUTH USER");

            cartId = cartRow[0].cart_id;
        }
    }

    let cartItems = await client.query(`SELECT * FROM cart_items WHERE cart_id = $1 AND product_id = $2`, [cartId, productId]);
    let cartItemsRow = cartItems.rows;

    let cartItemsId = null;
    if (cartItemsRow.length > 0) {
        cartItemsId = cartItemsRow[0].id
    }

    // Check if we have same items in the cart
    // When we don't have we make, we insert
    if (cartItemsRow.length == 0) {
        console.log("ENTERED cart_items to INSERT the item");

        await client.query(`INSERT INTO cart_items (cart_id, product_id, quantity, vat) VALUES ($1, $2, $3, $4)`, [cartId, productId, quantity, vat]);

        return "You successfully added item."

    // When we have the same item, we update cart_items
    } else {
        console.log("ENTERED cart_items to UPDATE the itemS");

        await client.query(`UPDATE cart_items SET quantity = quantity + $1 WHERE id = $2`, [quantity, cartItemsId]);

        return "You successfully added same item, quantity was increased.";
    }
}

async function removeFromCart(productId, client){
    await client.query(`DELETE FROM cart_items where product_id = $1`, [productId])
    return "You successfully deleted item."
}

async function mergeCart(userId, sessionIdUnauthenticatedUser, client) {
    let cart = await client.query(`SELECT * FROM carts WHERE session_id = $1`, [sessionIdUnauthenticatedUser]);

    let cartRow = cart.rows;
    let cartId = cartRow[0].cart_id;

    await client.query(`UPDATE carts SET user_id = $1, session_id = null WHERE cart_id = $2 and session_id = $3`, [userId, cartId, sessionIdUnauthenticatedUser]);
}

module.exports = {
    prepareRegistrationData,
    registration,
    refreshCaptcha,
    verify,
    login,
    prepareHomeData,
    getCartItemsCount,
    getProfileData,
    prepareCartData,
    getCart,
    updateCartQuantity,
    uuidv4,
    addToCart,
    removeFromCart,
    mergeCart,
}