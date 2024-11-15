const { AssertUser, AssertDev } = require('./exceptions');
const errors = require('./error_codes');
const pool = require('./db');
const bcrypt = require('bcryptjs');

const Ajv = require('ajv');
const ajv = new Ajv();
// require('ajv-formats')(ajv); 
const userDetailsSchema = require('./schemas/profile.json');

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
            WHERE carts.session_id = $1
    `
    let items = await client.query(query, [authenticatedUser]);

    cartItems = items.rows;

    AssertDev(cartItems.length <= 1000, "Fetched too many rows in viewCart function");
    } else {
        console.log("prepareCartData IN NORMAL SESSION");
        let userData = await client.query(`SELECT * FROM users WHERE email = $1`, [authenticatedUser['userRow']['data']]);

        let userId = userData.rows[0]['id'];

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
            WHERE carts.user_id = $1
        `
        let items = await client.query(query, [userId]);

        cartItems = items.rows;

        AssertDev(cartItems.length <= 1000, "Fetched too many rows in viewCart function");

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
        
        console.log("cartRow");
        console.log(cartRow);

        AssertDev(cartRow.length <= 1, "Bug, can't have more than one cart");

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

        console.log("cartRow");
        console.log(cartRow);

        AssertDev(cartRow.length <= 1, "Bug, can't have more than one cart");

        // Not present cart, we have to make one
        if (cartRow.length == 0) {
            console.log("ENTERED CREATING CART FOR AUTH USER");

            let result = await client.query(`INSERT INTO carts(user_id) VALUES ($1) RETURNING cart_id`, [userId]);
            cartId = result.rows[0].cart_id;

        // Present cart, we insert in it 
        } else {
            console.log("ENTERED ALREADY CREATED CART FOR AUTH USER");

            cartId = cartRow[0].cart_id;
        }
    }

    await client.query(`
        INSERT INTO cart_items (cart_id, product_id, quantity, vat)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (cart_id, product_id)
        DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
        `, [cartId, productId, quantity, vat]);

    return "You successfully added item.";
}

async function removeFromCart(productId, client){
    await client.query(`DELETE FROM cart_items where product_id = $1`, [productId])
    return "You successfully deleted item."
}

async function mergeCart(userId, sessionIdUnauthenticatedUser, client) {
    AssertDev(sessionIdUnauthenticatedUser !== undefined, "There is not anonymn cart");
    AssertDev(userId !== undefined, "There is not logged user");

    let anonymnCart = await client.query(`SELECT * FROM carts WHERE session_id = $1`, [sessionIdUnauthenticatedUser]);

    let cartIdAnonymnCart = anonymnCart.rows[0].cart_id;
    let userCart = await client.query(`SELECT * FROM carts WHERE user_id = $1`, [userId]);

    if (userCart.rows.length > 0) {
        // The user already has a cart -> to merge the session cart into the existing cart
        let existingCartId = userCart.rows[0].cart_id;

        let anonymnCartItems = await client.query(`SELECT * FROM cart_items WHERE cart_id = $1`, [cartIdAnonymnCart]);

        for (let item of anonymnCartItems.rows) {
            // Check if the item already exists in the user’s cart
            let existingItem = await client.query(
                `SELECT * FROM cart_items WHERE cart_id = $1 AND product_id = $2`, 
                [existingCartId, item.product_id]
            );

            if (existingItem.rows.length > 0) {
                // If the product exists in the user's cart, update the quantity
                await client.query(
                    `UPDATE cart_items 
                     SET quantity = quantity + $1 
                     WHERE cart_id = $2 AND product_id = $3`,
                    [item.quantity, existingCartId, item.product_id]
                );
            } else {
                // Otherwise, move the item from the anonymous cart to the user's cart
                await client.query(
                    `INSERT INTO cart_items (cart_id, product_id, quantity, added_at, vat) 
                     VALUES ($1, $2, $3, $4, $5)`,
                    [existingCartId, item.product_id, item.quantity, item.added_at, item.vat]
                );
            }
        }

        await client.query(`DELETE FROM cart_items WHERE cart_id = $1`, [cartIdAnonymnCart]);
        await client.query(`DELETE FROM carts WHERE cart_id = $1`, [cartIdAnonymnCart]);
    } else {
        // If the user does not have a cart, update the session cart to belong to the user
        await client.query(`
            UPDATE carts 
            SET user_id = $1, session_id = null 
            WHERE cart_id = $2
        `, [userId, cartIdAnonymnCart]);
    }
}

async function cart(deliveryInformation, authenticatedUser, client) {
    let { first_name: firstName, last_name: lastName, email: email, address: address, country_code: countryCode, phone: phone, town: town } = deliveryInformation;

    const regexPhone = /^\d{7,15}$/;
    const regexEmail = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b/;

    AssertUser(firstName.length >= 3 && firstName.length <= 50, "First name must be between 3 and 50 symbols", errors.NAME_LENGTH_ERROR_CODE);
    AssertUser(lastName.length >= 3 && lastName.length <= 50, "Last name must be between 3 and 50 symbols", errors.NAME_LENGTH_ERROR_CODE);
    AssertUser(regexEmail.test(email), "Email is not valid", errors.INVALID_EMAIL_ERROR_CODE);
    AssertUser(regexPhone.test(phone), "Phone number format is not valid. The number should be between 7 and 15 digits", errors.PHONE_FORMAT_ERROR_CODE);
    AssertUser(phone[0] !== '0', "Phone number format is not valid.", errors.PHONE_FORMAT_ERROR_CODE);

    // Retrieve cart items for the user
    let cartItemsResult = await client.query(`
        SELECT
            users.id               AS user_id,
            users.first_name       AS user_first_name,
            users.last_name        AS user_last_name,
            carts.cart_id,
            cart_items.product_id,
            products.name,
            cart_items.quantity    AS cart_quantity,
            products.price,
            currencies.symbol,
            cart_items.vat,
            products.quantity      AS db_quantity
        FROM users
            JOIN carts      ON carts.user_id         = users.id
            JOIN cart_items ON cart_items.cart_id    = carts.cart_id
            JOIN products   ON cart_items.product_id = products.id
            JOIN currencies ON products.currency_id  = currencies.id
        WHERE users.email = $1
    `, [authenticatedUser.userRow.data]);

    let cartItems = cartItemsResult.rows;
    let userId = cartItems[0].user_id;
    let cartId = cartItems[0].cart_id;
    let userFirstName = cartItems[0].user_first_name;
    let userLastName = cartItems[0].user_last_name;

    let productIds = cartItems.map(item => item.product_id);
    let cartPrices = {};
    let cartQuantities = {};
    let dbQuantities = {};

    cartItems.forEach(item => {
        cartPrices[item.product_id] = item.price;
        cartQuantities[item.product_id] = item.cart_quantity;
        dbQuantities[item.product_id] = item.db_quantity;
    });

    console.log("productIds");
    console.log(productIds);
    console.log("cartPrices");
    console.log(cartPrices);
    console.log("cartQuantities");
    console.log(cartQuantities);
    console.log("dbQuantities");
    console.log(dbQuantities);

    for (let [productId, cartQuantity] of Object.entries(cartQuantities)) {
        AssertUser(cartQuantity < dbQuantities[productId], 
            `We don't have ${cartQuantity} of product: ${cartItems[0].name} in our store. You can purchase less or remove the product from your cart.`,
            errors.NOT_ENOUGHT_QUANTITY);
    }

    let updateCases = productIds.map(productId => `WHEN ${productId} THEN quantity - ${cartQuantities[productId]}`).join(' ');
    let query = `
        UPDATE products
        SET quantity = CASE id ${updateCases}
        END
        WHERE id = ANY($1::int[])
    `;

    console.log("query");
    console.log(query);

    await client.query(query, [productIds]);

    // Insert into orders
    let orderResult = await client.query(`
        INSERT INTO orders (user_id, status, order_date)
        VALUES ($1, $2, CURRENT_TIMESTAMP)
        RETURNING order_id
    `, [userId, 'Ready for Paying']);

    let orderId = orderResult.rows[0].order_id;

    const orderItemsData = cartItems.map(item => [
        orderId,
        item.product_id,
        item.cart_quantity,
        item.price,
        item.vat
    ]);

    console.log("orderItemsData");
    console.log(orderItemsData);

    // Prepare a single query to insert all order items at once
    let orderItemsQuery = `
        INSERT INTO order_items (order_id, product_id, quantity, price, vat)
        VALUES ${orderItemsData.map((_, index) => `($1, $${index * 4 + 2}, $${index * 4 + 3}, $${index * 4 + 4}, $${index * 4 + 5})`).join(', ')}
    `;

    console.log("orderItemsQuery");
    console.log(orderItemsQuery);

    // Flatten the orderItemsData into a single array
    let orderItemsValues = orderItemsData.reduce((acc, item) => acc.concat([item[1], item[2], item[3], item[4]]), []);

    console.log("orderItemsValues");
    console.log(orderItemsValues);

    // Execute the batch insert
    await client.query(orderItemsQuery, [orderId, ...orderItemsValues]);

    let countryCodeResult = await client.query('SELECT id FROM country_codes WHERE code = $1', [countryCode]);
    let countryCodeId = countryCodeResult.rows[0].id;

    await client.query(`
        INSERT INTO shipping_details (order_id, email, first_name, last_name, town, address, phone, country_code_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, [orderId, email, firstName, lastName, town, address, phone, countryCodeId]);

    let totalSum = cartItems.reduce((sum, item) => sum + (parseFloat(item.price) * parseFloat(item.cart_quantity)), 0);
    let totalSumWithVat = cartItems.reduce((sum, item) => sum + (parseFloat(item.price) * parseFloat(item.cart_quantity) * (1 + parseFloat(item.vat) / 100)), 0);

    await client.query('DELETE FROM cart_items WHERE cart_id = $1', [cartId]);

    let shippingDetailsResult = await client.query(`
        SELECT 
            shipping_details.*, 
            country_codes.code 
        FROM shipping_details
            JOIN country_codes ON shipping_details.country_code_id = country_codes.id 
        WHERE shipping_details.order_id = $1
    `, [orderId]);

    let shippingDetails = shippingDetailsResult.rows;
    let settingsResult = await client.query('SELECT * FROM settings');
    let settingsRow = settingsResult.rows[0];

    return {
        order_id: orderId,
        cart_items: cartItems,
        shipping_details: shippingDetails,
        total_sum_with_vat: totalSumWithVat,
        total_sum: totalSum,
        user_first_name: userFirstName,
        user_last_name: userLastName,
        vat_in_persent: settingsRow.vat
    };
}

async function getOrder(orderId, client) {
    AssertDev(orderId, "orderId is missing");

    let query = `
                SELECT 
                    orders.*,
                    order_items.*,
                    shipping_details.*,
                    products.name       AS product_name,
                    currencies.symbol   AS product_currency
                FROM orders 
                JOIN order_items      ON orders.order_id      = order_items.order_id 
                JOIN shipping_details ON orders.order_id      = shipping_details.order_id
                JOIN products         ON products.id          = order_items.product_id
                JOIN currencies       ON products.currency_id = currencies.id
                WHERE orders.order_id = $1
                `;

    let resultQuery = await client.query(query, [orderId]);

    AssertDev(resultQuery.rows.length != 0, "There is not items in the purchase");

    let cartItems = [];
    let totalSum = 0;
    let totalSumWithVat = 0;
    let shippingDetails = null;

    resultQuery.rows.forEach(row => {
        // Extract each cart item from the row
        cartItems.push({
            product_id: row.product_id,
            name: row.product_name,
            quantity: row.quantity,
            price: parseFloat(row.price),
            vat: row.vat,
            symbol: row.product_currency
        });

        // Calculate total sum without VAT and with VAT
        totalSum += row.quantity * parseFloat(row.price);  // Total without VAT
        totalSumWithVat += row.quantity * parseFloat(row.price) * (1 + parseFloat(row.vat) / 100);  // Total with VAT

        // Extract shipping details (same across all rows, so just assign once)
        if (!shippingDetails) {
            shippingDetails = {
                email: row.email,
                first_name: row.first_name,
                last_name: row.last_name,
                town: row.town,
                address: row.address,
                phone: row.phone,
                country_code_id: row.country_code_id
            };
        }
    });

    return {
        order_id: orderId,
        cart_items: cartItems,
        shipping_details: shippingDetails,
        total_sum_with_vat: totalSumWithVat,
        total_sum: totalSum,
        user_first_name: shippingDetails.first_name,
        user_last_name: shippingDetails.last_name,
        vat_in_persent: 20,
    };
}

async function payOrder(orderId, paymentAmount, client) {
    console.log(orderId);
    console.log(paymentAmount);

    AssertDev(orderId != undefined, "orderId is undefined");
    AssertDev(paymentAmount != undefined, "paymentAmount is undefined");

    let floatPaymentAmount = parseFloat(paymentAmount);
    let roundedPaymentAmount = Math.round((floatPaymentAmount + Number.EPSILON) * 100) / 100;

    let order = await client.query(`SELECT * FROM orders WHERE order_id = $1`, [orderId]);
    let orderRow = order.rows;

    AssertDev(orderRow.length == 1, "There can't be more than one row with same order id");

    let orderItems = await client.query(`SELECT * FROM order_items WHERE order_id = $1`, [orderId]);
    let orderItemsRows = orderItems.rows;

    AssertUser(orderRow[0].status == 'Ready for Paying', "This order can't be payed, due to it's status");

    let total = 0;
    let totalWithVat = 0;

    orderItemsRows.forEach(row => {
        console.log("row");
        console.log(row);
        total += parseInt(row.quantity) * parseFloat(row.price);
        totalWithVat += parseInt(row.quantity) * parseFloat(row.price) + (parseFloat((row.vat / 100)) * (parseInt(row.quantity) * parseFloat(row.price)));
    })

    let totalWithVatToFixed = totalWithVat.toFixed(2)

    AssertUser(!(roundedPaymentAmount < totalWithVatToFixed), "You entered amout, which is less than the order you have");
    AssertUser(!(roundedPaymentAmount > totalWithVatToFixed), "You entered amout, which is bigger than the order you have");

    const paymentResult = await fetch("http://10.20.3.224:5002/api/payments", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            client_id: orderId,
            amount: totalWithVatToFixed,
        }),
    });

    console.log(paymentResult);
    AssertUser(paymentResult.ok, "Payment method failed, try again", errors.PAYMENT_METHOD_FAILED);  

    await client.query(`UPDATE orders SET status = 'Paid' WHERE order_id = $1`, [orderId]);

    return "You paid the order successful";
}

async function postProfile(userDetails, authenticatedUser, client) {
    const { firstName, lastName, email, oldPassword, newPassword, address, phone, countryCode } = userDetails;

    const validate = ajv.compile(userDetailsSchema);
    const valid = validate(userDetails);

    if (!valid) {
        const errorMessages = validate.errors ? validate.errors.map(error => `${error.instancePath} ${error.message}`).join(', ') : "Unknown validation error";
        AssertUser(false, `Validation Error: ${errorMessages}`, errors.INVALID_FIELD_FROM_PROFILE_SCHEMA);
    }

    // Query construction logic
    let queryString = "UPDATE users SET ";
    let fieldsList = [];
    let updatedFields = [];

    const updates = {
        first_name: firstName,
        last_name: lastName,
        email: email,
        address: address,
        phone: phone,
    };

    if (oldPassword && newPassword) {
        const userQuery = `SELECT password FROM users WHERE id = $1`;
        const userResult = await client.query(userQuery, [authenticatedUser['userRow']['user_id']]);

        AssertDev(userResult.length !== 0, "No such user registered")

        const currentHashedPassword = userResult.rows[0].password;

        const isMatch = await bcrypt.compare(oldPassword, currentHashedPassword);
    
        AssertUser(isMatch, "Old password is incorrect.")

        const saltRounds = 10;
        const hashedPassword = await bcrypt.hash(newPassword, saltRounds);

        updates.password = hashedPassword;
    }

    if (countryCode) {
        const countryQuery = `SELECT id FROM country_codes WHERE code = $1`;
        const countryResult = await client.query(countryQuery, [countryCode]);

        AssertUser(countryResult.rows.length !== 0, "Invalid country code.");

        updates.country_code_id = countryResult.rows[0].id;
    }

    for (const [key, value] of Object.entries(updates)) {
        if (value !== undefined) {
            queryString += `${key} = $${fieldsList.length + 1}, `;
            fieldsList.push(value);
            updatedFields.push(key);
        }
    }

    AssertUser(updatedFields.length !== 0, "No fields to update. At least one field must be provided.");

    queryString = queryString.slice(0, -2) + ` WHERE id = $${updatedFields.length + 1}`;
    fieldsList.push(authenticatedUser['userRow']['user_id']);

    await client.query(queryString, fieldsList);
    let updatedFieldsMessage = updatedFields.join(', ');
    
    return {
        success: true,
        message: `Updated fields: ${updatedFieldsMessage}`
    };
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
    updateCartQuantity,
    uuidv4,
    addToCart,
    removeFromCart,
    mergeCart,
    cart,
    getOrder,
    payOrder,
    postProfile
}