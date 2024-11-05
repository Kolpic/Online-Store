const crypto = require('crypto');
const pool = require('./db');
const errors = require('./error_codes');
const sessions = require('./sessions');
const mailer = require('./mailer');
const express = require('express');
const { AssertUser, AssertDev, WrongUserInputException } = require('./exceptions');
const bcrypt = require('bcrypt');
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
    },
    POST: {
        '/login': postLoginHandler,
        '/crud/:schema': filterEntities,
        '/create/:schema': creteCRUDSchema,
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
        console.log(error, "error")

        let sessionId = req.cookies['session_id']
        let userData = await sessions.getCurrentUser(sessionId, client);
        if (userData == null) {
            userData = "Guest";
        }

        await logException(userData, error.name, error.message, "back office");

        await client.query('ROLLBACK');

        if (error instanceof WrongUserInputException) {
            return res.status(400).json({ 
                error_message: error.message, 
                error_code: error.errorCode 
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
    await clientForExcaptionLog.query('BEGIN');

    await clientForExcaptionLog.query(`INSERT INTO exception_logs (user_email, exception_type, message, sub_system) VALUES ($1, $2, $3, $4)`, [user_email, exception_type, message, subSystem]);

    await clientForExcaptionLog.query('COMMIT');
    clientForExcaptionLog.release();
}

async function postLoginHandler(req, res, next, client) {
    let username = req.body.username;
    let password = req.body.password;

    let response = await backOfficeService.login(username, password, client);

    let sessionId = await sessions.createSession(username, false, client);

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

    let query = `SELECT ${selectClause} FROM ${tableName} ${joinClause} ${whereClause} ${groupByClause}`;

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

async function creteCRUDSchema(req, res, next, client) {
    let schemaName = req.path.split("/")[2];
    let schema = require(`./schemas/${schemaName}_validation_schema.json`);

    const ajv = new Ajv({ allErrors: true, useDefaults: true, strict: false});
    ajvErrors(ajv);
    const validateEntity = ajv.compile(schema);

    let {formData, files} = await backOfficeService.parseMultipartFormData(req);

    let {columns, values, foreignKeyLookups, manyToManyInserts, oneToManyInsertions} = await backOfficeService.mapSchemaPropertiesToDBRelations(formData, files, schema);

    let hooksBefore = crudHooks[schemaName]?.update.before;
    if (hooksBefore) {
        for(const hook of Object.values(hooksBefore)) {
            values = await hook(values);
        }
    }

    // Step 2: Execute foreign key lookups
    for (const fk of foreignKeyLookups) {
        columns.push(fk.field);
        values.push(fk.value);
    }

    // Step 3: Insert main entity
    const placeholders = columns.map((_, i) => `$${i + 1}`);
    const insertQuery = `INSERT INTO ${schema.title} (${columns.join(", ")})
                         VALUES (${placeholders.join(", ")}) RETURNING id`;

    const { rows } = await client.query(insertQuery, values);
    const entityId = rows[0].id;

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

    res.status(201).json({ message: `${schema.title} created successfully`});
}

async function updateEntity(req, res, next, client) {
    let schemaName = req.path.split("/")[2];
    let schema = require(`./schemas/${schemaName}_validation_schema.json`);

    const ajv = new Ajv({ allErrors: true, useDefaults: true, strict: false});
    ajvErrors(ajv);
    const validateEntity = ajv.compile(schema);

    let {formData, files} = await backOfficeService.parseMultipartFormData(req);

    let {columns, values, foreignKeyLookups, manyToManyInserts, oneToManyInsertions} = await backOfficeService.mapSchemaPropertiesToDBRelations(formData, files, schema);

    let hooksBefore = crudHooks[schemaName]?.update.before;
    if (hooksBefore) {
        for(const hook of Object.values(hooksBefore)) {
            values = await hook(values);
        }
    }

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
    const updateQuery = `UPDATE ${schema.title} SET ${setClause} WHERE id = $${columns.length + 1} RETURNING id`;

    const entityId = formData.id;
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
        o2m.values[0] = entityId; 
        await client.query(o2m.query, o2m.values);
    }

    res.status(200).json({ message: `${schema.title} updated successfully` });
}

async function handlePasswordHash(values) {
    let password = values[3];
    const saltRounds = 10;
    const hashed_password = await bcrypt.hash(password, saltRounds);
    values[3] = hashed_password;
    return values;
}

async function getReportsHandler(req, res, next, client) {
    const inputData = req.query;
    let reportName = req.path.split("/")[2];
    let reportFilters = require(`./schemas/${reportName}.json`);

    const sqlQuery = await backOfficeService.generateReportSQLQuery(inputData, reportFilters);

    const result = await client.query(sqlQuery);
    res.json(result.rows);
}


module.exports = router;