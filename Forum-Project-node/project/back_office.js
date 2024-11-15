const crypto = require('crypto');
const pool = require('./db');
const errors = require('./error_codes');
const sessions = require('./sessions');
const mailer = require('./mailer');
const express = require('express');
const { AssertUser, AssertDev, WrongUserInputException } = require('./exceptions');
const bcrypt = require('bcryptjs');
const backOfficeService = require('./backOfficeService')
const router = express.Router();
const fs = require('fs');
const path = require('path');
const formidable = require('formidable');
const { pipeline } = require('stream');
const { promisify } = require('util');
const { v4: uuidv4 } = require('uuid');
const Ajv = require('ajv');
const ajvErrors = require('ajv-errors');

console.log("Pool imported in back_office.js:"); 

const urlToFunctionMapBackOffice = {
    GET: {
        '/header': getHeaderHandler,
        '/logout': getLogoutHandler,
        '/currencies': getCurrenciesHandler,
        '/gender': getGenderHandler,
        '/categories': getCategoriesHandler,
        '/country_codes': getCountryCodesHandler,
        '/reports/:schema': getReportsHandler,
        '/order_items': getOrderItemsData,
        '/order_status': getOrderStatusHadler,
        '/user_emails': getUserEmailsHandler,
        '/products_for_order': getProductsForOrderHandler,
    },
    POST: {
        '/login': postLoginHandler,
        '/crud/:schema': filterEntities,
        '/create/:schema': createEntity,
    },
    PUT: {
        '/update/:schema': updateEntity,
    }
};

const crudHooks = {
    users: {
        create: {
            before: {
                handlePasswordHash
            },
            after: {

            }
        },
        update: {
            before: {
                handlePasswordHash
            },
            after: {

            }
        }
    },
    products: {
        create: {
            before: {

            },
            after: {
                addProductIdToImages
            }
        },
        update: {
            before: {

            },
            after: {
                addProductIdToImages,
                removeImages,
            }
        }
    },
    orders: {
        create: {
            before: {
                findUserIdByEmail,
            },
            after: {
                decreaseProductsQuantityInDB,
            }
        },
        update: {
            before: {
                findUserIdByEmail,
                updateProductsQuantityDB,
            },
            after: {

            }
        }
    }
}

function mapUrlToFunction(req) {
    const methodMap = urlToFunctionMapBackOffice[req.method];

    let basePath = req.path.split('/')[1];
    let matchedHandler;

    if (basePath) {
        // First check for exact path matches
        matchedHandler = methodMap[`/${basePath}`];
        
        // If not found, check for dynamic routes like `/products/:id`
        if (!matchedHandler) {
            Object.keys(methodMap).forEach((key) => {
                const dynamicRoute = key.includes('/:'); // Check if the route is dynamic
                if (dynamicRoute) {
                    // Create a regular expression to match dynamic routes
                    const regex = new RegExp(key.replace(/:[^\s/]+/, '([\\w-]+)'));
                    const match = req.path.match(regex);
                    if (match) {
                        req.params.id = match[1]; // Assign the dynamic param (like id) to req.params
                        matchedHandler = methodMap[key]; // Get the matching handler
                    }
                }
            });
        }
    }

    return matchedHandler;
}

router.use(async (req, res, next) => {
    console.log("Pool inside router.use in back_office.js:");

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

        console.log(req.path);

        client = await pool.connect();
        await client.query('BEGIN');

        let handler = mapUrlToFunction(req);
        AssertUser(handler != undefined, "Invalid url", errors.INVALID_URL);

        await handler(req, res, next, client);

        await client.query('COMMIT');
    } catch (error) {
        console.log("error");
        console.log(error);

        if (client) await client.query('ROLLBACK');

        let clientCatch = await pool.connect();
        await clientCatch.query('BEGIN');

        let sessionId = req.cookies['session_id']
        let userDataSession = await sessions.getCurrentUser(sessionId, clientCatch);
        let userData;
        if (userDataSession == null) {
            userData = "Guest";
        } else {
            userData = userDataSession.userRow.data;
        }

        await logException(userData, error.name, error.message, "back office");

        if (error instanceof WrongUserInputException) {
            return res.status(400).json({ 
                error_message: error.message, 
                error_code: error.errorCode 
            });
        } else if (error.code == '23514') {
            return res.status(500).json({ 
                error_message: 'The seleted quantity you want for the product will be negative in out store. Try selecting less.' 
            });
        } else if (error.code == 'P8000') {
            return res.status(500).json({ 
                error_message: error.message 
            });
        } else {
            return res.status(500).json({ 
                error_message: 'Internal Server Error' 
            });
        }

    } finally {
        if (client) {
            client.release();
        }
    }
});

async function logException(user_email, exception_type, message, subSystem) {
    let clientForExcaptionLog = await pool.connect();
    try {
        await clientForExcaptionLog.query('BEGIN');
        await clientForExcaptionLog.query(`INSERT INTO exception_logs (user_email, exception_type, message, sub_system, log_type) VALUES ($1, $2, $3, $4, $5)`, [user_email, exception_type, message, subSystem, "error"]);
        await clientForExcaptionLog.query('COMMIT');
    } catch (error) {
        await clientForExcaptionLog.query('ROLLBACK');
        throw error;
     } finally {
        clientForExcaptionLog.release();
    }
}

async function logEvent(user, exception_type, message) {
    let clientForExcaptionLog = await pool.connect();
    await clientForExcaptionLog.query('BEGIN');

    console.log("Logged event -> " + message);
    await clientForExcaptionLog.query(`INSERT INTO exception_logs (user_email, exception_type, message, sub_system, log_type) VALUES ($1, $2, $3, $4, $5)`, 
        [user, exception_type, message, "back office", "event"]);

    await clientForExcaptionLog.query('COMMIT');
    clientForExcaptionLog.release();
}

async function postLoginHandler(req, res, next, client) {
    let username = req.body.username;
    let password = req.body.password;

    let response = await backOfficeService.login(username, password, client);

    let sessionId = await sessions.createSession(username, false, client);

    await logEvent(username, "", "User logged in back office");

    res.cookie('session_id', sessionId, {
      httpOnly: true,
      sameSite: 'Lax',
    });

    res.json({
      success: true,
      user: response,
    });
}

async function getHeaderHandler(req, res, next, client) {
    let sessionId = req.cookies['session_id']
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    AssertUser(authenticatedUser != null, "You have to be logged to access this page");

    return res.json({
        email: authenticatedUser['userRow']['data'],
    });
}

async function getLogoutHandler(req, res, next, client) {
    sessionId = req.cookies['session_id']
    authenticatedUser = await sessions.getCurrentUser(sessionId, client)

    AssertUser(authenticatedUser != null, "You have to be logged to access this page");

    await client.query(`DELETE FROM custom_sessions WHERE session_id = $1`,[authenticatedUser['userRow']['session_id']]);

    await logEvent(authenticatedUser.userRow.data, "", "User logged out from back office");

    res.cookie('session_id', "", {
      httpOnly: true,
      sameSite: 'Lax',
    });

    res.json({
      success: true,
      message: "Successfully logged out",
    });
}

async function filterEntities(req, res, next, client) {
    let schema = req.body.schema;
    let filterById = req.body.id;
    let tableName = schema.title;

    let {selectFields, joins, groupByFields} = await backOfficeService.makeTableJoins(schema);

    let { whereConditions, values} = await backOfficeService.makeTableFilters(schema, req);

    let selectClause = selectFields.join(", ");
    let joinClause = joins.join(" ");
    let groupByClause = groupByFields.length > 0 ? `GROUP BY ${groupByFields.join(", ")}` : "";
    let whereClause = whereConditions.length > 0 ? `WHERE ${whereConditions.join(" AND ")}` : "";

    let query = `SELECT ${selectClause} FROM ${tableName} ${joinClause} ${whereClause} ${groupByClause} LIMIT 50`;
    console.log(query);

    const result = await client.query(query, values);
    return res.json(result.rows);
}

async function getCurrenciesHandler(req, res, next, client) {
    const result = await pool.query(`
        SELECT
            id,
            symbol AS name,
            code   AS param
        FROM currencies
    `); 
    return res.json(result.rows); 
}

async function getGenderHandler(req, res, next, client) {
    const result = await pool.query(`
        SELECT
            DISTINCT(gender) AS name
        FROM users
    `); 
    return res.json(result.rows); 
}

async function getCountryCodesHandler(req, res, next, client) {
    const result = await pool.query(`
        SELECT
            id,
            name           AS name,
            code           AS param
        FROM country_codes
    `); 
    return res.json(result.rows); 
}

async function getCategoriesHandler(req, res, next, client) {
    const result = await pool.query('SELECT * FROM categories');
    return res.json(result.rows); 
}

const pipelineAsync = promisify(pipeline);

async function createEntity(req, res, next, client) {
    let sessionId = req.cookies['session_id']
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    let schemaName = req.path.split("/")[2];
    let schema = require(`./schemas/${schemaName}_validation_schema.json`);

    const ajv = new Ajv({ allErrors: true, useDefaults: true, strict: false});
    ajvErrors(ajv);
    const validateEntity = ajv.compile(schema);

    let {formData, imageIds} = await backOfficeService.parseMultipartFormData(req, client);

    let beforeHookObj = {formData}
    let hooksBefore = crudHooks[schemaName]?.create.before;
    if (hooksBefore) {
        for(const hook of Object.values(hooksBefore)) {
            value = await hook(client, beforeHookObj);
        }
    }

    let {columns, values, foreignKeyLookups, manyToManyInserts, oneToManyInsertions} = await backOfficeService.mapSchemaPropertiesToDBRelations(formData, schema);

    // Step 2: Execute foreign key lookups
    for (const fk of foreignKeyLookups) {
        columns.push(fk.field);
        values.push(fk.value);
    }

    let insertQuery;
    let entityId;

    if (schemaName == "orders") {
        // Step 3: Insert main entity
        const placeholders = columns.map((_, i) => `$${i + 1}`);
        insertQuery = `INSERT INTO ${schema.title} (${columns.join(", ")})
                             VALUES (${placeholders.join(", ")}) RETURNING order_id`;

        const { rows } = await client.query(insertQuery, values);
        entityId = rows[0].order_id;
    } else {
        // Step 3: Insert main entity
        const placeholders = columns.map((_, i) => `$${i + 1}`);
        insertQuery = `INSERT INTO ${schema.title} (${columns.join(", ")})
                             VALUES (${placeholders.join(", ")}) RETURNING id`;

        const { rows } = await client.query(insertQuery, values);
        entityId = rows[0].id;
    }

    // Step 4: Handle many-to-many insertions
    for (const m2m of manyToManyInserts) {
        const joinInserts = m2m.values.map(value => ({
            query: `INSERT INTO ${m2m.joinTable} (${m2m.joinColumnOnePK}, ${m2m.joinColumnTwoPK})
                    VALUES ($1, (SELECT ${m2m.targetColumnFilter} FROM ${m2m.targetTable} WHERE ${m2m.targetColumnFilter} = $2))`,
            values: [entityId, value]
        }));
        for (const insert of joinInserts) {
            await client.query(insert.query, insert.values);
        }
    }

    // Step 5: Handle one to many insertions
    for (const o2m of oneToManyInsertions) {
        // Update each insertion with the actual entityId
        o2m.values[0] = entityId;

        await client.query(o2m.query, o2m.values);
    }

    let afterHookObj = {imageIds, formData};
    let hooksAfter = crudHooks[schemaName]?.create.after;
    if (hooksAfter) {
        for(const hook of Object.values(hooksAfter)) {
            values = await hook(client, entityId, afterHookObj);
        }
    }

    await logEvent(authenticatedUser.userRow.data, "", "User created new " + schema.title + " from CRUD inteface");

    res.status(201).json({ message: `${schema.title} created successfully`});
}

async function updateEntity(req, res, next, client) {
    let sessionId = req.cookies['session_id']
    let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

    let schemaName = req.path.split("/")[2];
    let schema = require(`./schemas/${schemaName}_validation_schema.json`);

    const ajv = new Ajv({ allErrors: true, useDefaults: true, strict: false});
    ajvErrors(ajv);
    const validateEntity = ajv.compile(schema);

    let {formData, imageIds} = await backOfficeService.parseMultipartFormData(req, client);

    let beforeHookObj = {formData}
    let hooksBefore = crudHooks[schemaName]?.update.before;
    if (hooksBefore) {
        for(const hook of Object.values(hooksBefore)) {
            let values = await hook(client, beforeHookObj);
        }
    }

    let {columns, values, foreignKeyLookups, manyToManyInserts, oneToManyInsertions} = await backOfficeService.mapSchemaPropertiesToDBRelations(formData, schema);

    // Step 2: Execute foreign key lookups
    for (const fk of foreignKeyLookups) {
        if (fk.field == "someQnuque") {
            let currencyIdRow = await client.query('SELECT id FROM currencies WHERE symbol = $1', [fk.value]);
            columns.push(fk.field);
            values.push(currencyIdRow.rows[0].id);
        } else {
            columns.push(fk.field);
            values.push(fk.value);
        }
    }
    const setClause = columns.map((column, index) => `${column} = $${index + 1}`).join(", ");

    let updateQuery;
    if (schemaName == "orders") {
        updateQuery = `UPDATE ${schema.title} SET ${setClause} WHERE order_id = $${columns.length + 1} RETURNING order_id`;
    } else {
        updateQuery = `UPDATE ${schema.title} SET ${setClause} WHERE id = $${columns.length + 1} RETURNING id`;
    }


    let entityId;
    if (schemaName == 'orders') {
        entityId = formData.order_id;
    } else {
        entityId = formData.id;
    }

    values.push(entityId);

    const { rows } = await client.query(updateQuery, values);

    // Handle Many-to-Many Updates
    for (const m2m of manyToManyInserts) {
        const deleteQuery = `DELETE FROM ${m2m.joinTable} WHERE ${m2m.joinColumnOnePK} = $1`;
        await client.query(deleteQuery, [entityId]);

        // Insert updated relations
        for (const value of m2m.values) {
            const insertQuery = `
                INSERT INTO ${m2m.joinTable} (${m2m.joinColumnOnePK}, ${m2m.joinColumnTwoPK})
                VALUES ($1, (SELECT ${m2m.targetColumnFilter} FROM ${m2m.targetTable} WHERE ${m2m.targetColumnFilter} = $2))
            `;
            await client.query(insertQuery, [entityId, value]);
        }
    }

    // Handle One-to-Many Updates
    for (const o2m of oneToManyInsertions) {
        console.log("Handle One-to-Many Updates");
        o2m.values[0] = entityId;
        await client.query(o2m.query, o2m.values);
    }

    let afterHookObj = {imageIds, formData} // For more than one function to call in after hook - make obj and each function takes needed values from the obj
    let hooksAfter = crudHooks[schemaName]?.update.after;
    if (hooksAfter) {
        for(const hook of Object.values(hooksAfter)) {
            values = await hook(client, entityId, afterHookObj);
        }
    }

    await logEvent(authenticatedUser.userRow.data, "", "User updated " + schema.title + " from CRUD inteface");

    res.status(200).json({ message: `${schema.title} updated successfully` });
}

async function handlePasswordHash(client, beforeHookObj) {
    let password = beforeHookObj.formData.password;
    const saltRounds = 10;
    const hashed_password = await bcrypt.hash(password, saltRounds);
    beforeHookObj.formData.password = hashed_password;
}

async function addProductIdToImages(client, entityId, afterHookObj){
    let imageIds = afterHookObj.imageIds;
    if (imageIds.length > 0) {
        const updateQuery = `
            UPDATE images 
            SET product_id = $1 
            WHERE id = ANY($2::int[])
    `;
    await client.query(updateQuery, [entityId, imageIds]);
    }
}

async function removeImages(client, entityId, afterHookObj) {
    let formData = afterHookObj.formData
    const imagesToRemove = [];
        for (const [key, value] of Object.entries(formData)) {
            if (key.startsWith('remove_image_') && value) {
                imagesToRemove.push(value);
            }
    }

    if (imagesToRemove.length > 0) {
        const deleteQuery = `DELETE FROM images WHERE path = ANY($1) AND product_id = $2`;
        await client.query(deleteQuery, [imagesToRemove, entityId]);
    }
}

async function getReportsHandler(req, res, next, client) {
    const inputData = req.query;
    let reportName = req.path.split("/")[2];
    let reportFilters = require(`./schemas/${reportName}.json`);

    const { sqlTemplate, queryParams } = await backOfficeService.generateReportSQLQuery(inputData, reportFilters);

    const countQuery = `
        SELECT COUNT(*) AS total_rows
        FROM (${sqlTemplate.replace("LIMIT 20", "")}) AS total_count_query
    `;
    const countResult = await client.query(countQuery, queryParams);
    const totalRows = countResult.rows[0].total_rows;

    const result = await client.query(sqlTemplate, queryParams);
    let resultRows = result.rows;

    res.json({resultRows, totalRows});
}

async function getOrderItemsData(req, res, next, client) {
    const inputData = req.query;
    let orderId = inputData.order_id;

    let rows = await client.query(`
                                SELECT 
                                    products.id           AS product_id,
                                    products.name         AS product_name,
                                    order_items.quantity,
                                    order_items.price,
                                    currencies.symbol     AS currency_symbol
                                FROM orders
                                    JOIN order_items ON orders.order_id        = order_items.order_id
                                    JOIN products    ON order_items.product_id = products.id
                                    JOIN currencies  ON products.currency_id   = currencies.id
                                WHERE orders.order_id = $1
                                `, [orderId]);
    return res.status(200).json({ data: rows.rows });
}

async function getOrderStatusHadler(req, res, next, client) {
    const result = await client.query(`
                                    SELECT
                                        DISTINCT(status) AS name
                                    FROM orders
                                    `);
    return res.json(result.rows);
}

async function getUserEmailsHandler(req, res, next, client) {
    const page = parseInt(req.query.page) || 1;
    const pageSize = parseInt(req.query.page_size) || 20;
    const offset = (page - 1) * pageSize;
    const emails = await client.query(`
                                SELECT 
                                    DISTINCT(email)
                                FROM users
                                LIMIT $1
                                OFFSET $2
                                `,[pageSize, offset])
    return res.json(emails.rows);
}

async function getProductsForOrderHandler(req, res, next, client) {
    const page = parseInt(req.query.page) || 1;
    const pageSize = parseInt(req.query.page_size) || 20;
    const offset = (page - 1) * pageSize;

    const products = await client.query(`
                                SELECT 
                                    products.id, 
                                    products.name, 
                                    products.price, 
                                    currencies.symbol,
                                    settings.vat
                                FROM products
                                    JOIN currencies ON products.currency_id = currencies.id
                                    JOIN settings   ON products.vat_id      = settings.id
                                LIMIT $1
                                OFFSET $2
                                `,[pageSize, offset])
    console.log(products.rows);
    return res.json(products.rows);
}

async function findUserIdByEmail(client, beforeHookObj) {
    let user = await client.query(`
                                SELECT
                                    *
                                FROM users
                                WHERE email = $1
                                `, [beforeHookObj.formData.email]);

    AssertDev(user.rows.length == 1, "Expect one for user")

    beforeHookObj.formData.user_id = user.rows[0].id;
}

async function decreaseProductsQuantityInDB(client, entityId, afterHookObj) {
    let orderItems = JSON.parse(afterHookObj.formData.order_items);

    for (let product of orderItems) {
        let productDB = await client.query(`SELECT * FROM products WHERE id = $1`, [product.product_id]);

        AssertDev(productDB.rows.length == 1, "Expext one on product");

        let productRow = productDB.rows[0];

        await client.query(`UPDATE products SET quantity = $1 WHERE id = $2`, [productRow.quantity - product.quantity, productRow.id]);
    }
}

async function updateProductsQuantityDB(client, beforeHookObj) {
    let orderItems = JSON.parse(beforeHookObj.formData.order_items);

    for (let product of orderItems) {
        let productDB = await client.query(`SELECT quantity FROM products WHERE id = $1`, [product.product_id]);
        AssertDev(productDB.rows.length == 1, "Expext one on product");

        let productRowQuantity = productDB.rows[0].quantity;

        let orderItemDB = await client.query(`SELECT quantity FROM order_items WHERE order_id = $1 AND product_id = $2`, [beforeHookObj.formData.order_id, product.product_id])
        AssertDev(orderItemDB.rows.length == 1, "Expext one on order_items");

        let orderItemRowQuantity = orderItemDB.rows[0].quantity;

        let newOrderItemQuantity = product.quantity;

        let updatedProductQuantity;

        if (newOrderItemQuantity > orderItemRowQuantity) {
            updatedProductQuantity = productRowQuantity - (newOrderItemQuantity - orderItemRowQuantity);
        } else {
            updatedProductQuantity = productRowQuantity + (orderItemRowQuantity - newOrderItemQuantity);
        }

        await client.query(`DELETE FROM order_items WHERE order_id = $1 AND product_id = $2`, [beforeHookObj.formData.order_id, product.product_id]);
        await client.query(`UPDATE products SET quantity = $1 WHERE id = $2`, [updatedProductQuantity, product.product_id]);
    }
}

process.on('uncaughtException', async (error) => {
    console.error("error in uncaughtException <<<");
    console.error(error);
    try {
        await logException("Guest", error.name, error.message, "back office");
    } catch (loggingError) {
        console.error("Error while logging uncaught exception:", loggingError);
    }
});

process.on('unhandledRejection', async (error) => {
    console.error("error in unhandledRejection >>>");
    console.error(error);
    try {
        await logException("Guest", error.name || "Error", error.message || "reason", "back office");
    } catch (loggingError) {
        console.error("Error while logging unhandled rejection:", loggingError);
    }
});

module.exports = router;