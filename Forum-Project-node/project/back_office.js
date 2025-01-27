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
const addFormats = require("ajv-formats");
const { stringify } = require('csv-stringify');
const ExcelJS = require('exceljs');
const { Transform } = require('stream');
const { PassThrough } = require('stream');
const timeout = require('express-timeout-handler');

console.log("Pool imported in back_office.js:");

const SESSION_ID = "back_office_session_id";

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
        '/roles': getRolesHandler,
        '/role_permissions': getRolePermissions,
        '/permissions': getPermissions,
        '/permissions_for_create': getPermissionsForCreate,
        '/get_staff_permissions': getStaffPermissions,
        '/email_templates': getEmailTemplatesHandler,
        '/email_by_id': getEmailByIdHnadler,
        '/distinct_values': getDistinctValuesHandler,
        '/target_groups': getTargetGroupsHandler,
        '/users_in_target_group': getUsersInTargetGroup,
        '/export_target_group_to_csv': exportTargetGroupHandler,
    },
    POST: {
        '/login': postLoginHandler,
        '/crud/:schema': filterEntities,
        '/create/:schema': createEntityHandler,
        '/export/:entity': exportEntityHandler,
        '/upload/:schema/csv': uploadEntitiesHandler,
    },
    PUT: {
        '/update/:schema': updateEntity,
    }
};

const TIMEOUT_CONFIG = {
    '/export/:entity': 5 * 60 * 1000,     // 5 min
    '/upload/:schema/csv': 5 * 60 * 1000, // 5 min
    default: 200 * 1000,                   // 20 sec
};

const PUBLIC_PATHS = {
    GET: {
        '/categories/:id': true
    },
    POST: {
        '/login': true
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
    },
    staff: {
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
    roles: {
        create: {
            before: {
                
            },
            after: {

            }
        },
        update: {
            before: {
                auditRolePermissionChanges,
            },
            after: {

            }
        }
    },
    target_groups: {
        create: {
            before: {
                mapTargetGroupsWithFilters,
            },
            after: {
                mapUsersToTargetGroup
            }
        },
        update: {
            before: {

            },
            after: {

            }
        }
    }
}

function requiresAuth(method, path) {
    const methodPaths = PUBLIC_PATHS[method];
    if (!methodPaths) return true;
    
    if (methodPaths[path]) return false;
    
    for (const publicPath of Object.keys(methodPaths)) {
        if (publicPath.includes('/:')) {
            const regex = new RegExp(publicPath.replace(/:[^\s/]+/, '([\\w-]+)'));
            if (path.match(regex)) return false;
        }
    }
    
    return true;
}

function getTimeoutForPath(path) {
    for (const [key, value] of Object.entries(TIMEOUT_CONFIG)) {
        if (key.includes('/:')) {
            const regex = new RegExp(key.replace(/:[^\s/]+/, '([\\w-]+)'));
            if (path.match(regex)) {
                return value;
            }
        } else if (key === path) {
            return value;
        }
    }
    return TIMEOUT_CONFIG.default;
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

function createCancellablePromise(executor) {
    let cancel;
    const cancelToken = {cancel: false};

    const promise = new Promise((resolve, reject) => {
        cancel = () => {
            if (!cancelToken.cancelled) {
                cancelToken.cancelled = true;
                reject(new Error("Promise cancelled"));
            }
        };
        executor(resolve, reject, cancelToken);
    });
    return { promise, cancel, cancelToken };
}

router.use(async (req, res, next) => {
    console.log("Pool inside router.use in back_office.js:");
    const TIMEOUT_MS = getTimeoutForPath(req.path);

    let client;
    let cookieObj = {};
    let timeoutHandle;
    let cancelHandler;

    try {
        // Create a timeout promise
        const timeoutPromise = new Promise((_, reject) => {
            timeoutHandle = setTimeout(() => {
                reject(new Error('Request timed out'));
            }, TIMEOUT_MS);
        });

        // Create a cancellable handler promise
        const cancellableHandler = createCancellablePromise(async (resolve, reject, cancelToken) => {
            try {
                console.log("Pool inside router.use in back_office.js:");
                let cookieObj = {};
                let cookieString = req.headers.cookie;

                if (cookieString) {
                    cookieString.split(";").forEach(cookie => {
                        let [name, value] = cookie.split("=");
                        name = name.trim();
                        cookieObj[name] = value;
                    });
                }

                req.cookies = cookieObj;
                console.log("Parsed cookies:", req.cookies);
                console.log(req.path);

                client = await pool.connect();
                await client.query("BEGIN");

                let handler = mapUrlToFunction(req);
                AssertUser(handler !== undefined, "Invalid url", errors.INVALID_URL);

                let sessionId = req.cookies[SESSION_ID]
                let authenticatedUser = await sessions.getCurrentUser(sessionId, client);

                if (requiresAuth(req.method, req.path)) {
                    AssertUser(authenticatedUser != null, "You have to be logged to access this page");
                }

                await handler(req, res, next, client, authenticatedUser);
                await client.query("COMMIT");

                resolve(); // Mark handler as resolved
            } catch (err) {
                reject(err); // Reject on error
            }
        });

        const handlerPromise = cancellableHandler.promise;
        cancelHandler = cancellableHandler.cancel;

        // Race between the handler and timeout
        await Promise.race([handlerPromise, timeoutPromise]);

    } catch (error) {
        if (timeoutHandle) clearTimeout(timeoutHandle);

        console.log("error in server catch block");
        console.log(error);

        // if (client) await client.query('ROLLBACK');

        let clientCatch = await pool.connect();
        await clientCatch.query('BEGIN');

        let sessionId = req.cookies[SESSION_ID]
        let userDataSession = await sessions.getCurrentUser(sessionId, clientCatch);
        clientCatch.release();
        let userData;
        if (userDataSession == null) {
            userData = "Guest";
        } else {
            userData = userDataSession.userRow.data;
        }

        await logException(userData, error.name, error.message, "back office");

        if (error.message === "Request timed out") {
            cancelHandler();
            console.log("res.headersSent", res.headersSent)
            if (!res.headersSent) {
                console.log("ENTERED in server try catch !res.headersSent");

                return res.status(503).json({
                    error_message: "Request timed out. Please try again later.",
                });
            } else {
                console.log('Response already sent. Ending...');
                res.end();
            }
        } else 
        if (error instanceof WrongUserInputException) {
            return res.status(400).json({ 
                error_message: error.message, 
                error_code: error.errorCode 
            });
        } else if (error.code == '23514') {
            return res.status(500).json({ 
                error_message: 'The seleted quantity you want for the product will be negative in out store. Try selecting less.' 
            });
        } else if (error.code == '23505') {
            return res.status(500).json({
                error_message: 'Some of the products you are trying to upload are already present'
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
        if (timeoutHandle) clearTimeout(timeoutHandle);
        if (client) {
            await client.query('ROLLBACK');
            client.release();
        }
    }
});

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

    await clientForExcaptionLog.query(`INSERT INTO exception_logs (user_email, exception_type, message, sub_system, audit_type, log_type) VALUES ($1, $2, $3, $4, $5, $6)`, 
        [user_email, exception_type, message, subSystem, auditType,"error"]);

    try {
        await clientForExcaptionLog.query('BEGIN');

        await clientForExcaptionLog.query(`INSERT INTO exception_logs (user_email, exception_type, message, sub_system, audit_type, log_type) VALUES ($1, $2, $3, $4, $5, $6)`, 
            [user_email, exception_type, message, subSystem, auditType, "error"]);
        
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

    res.cookie(SESSION_ID, sessionId, {
      httpOnly: true,
      sameSite: 'Lax',
    });

    return res.json({
      success: true,
      user: response,
    });
}

async function getHeaderHandler(req, res, next, client, authenticatedUser) {
    return res.json({
        email: authenticatedUser['userRow']['data'],
    });
}

async function getLogoutHandler(req, res, next, client, authenticatedUser) {
    await client.query(`DELETE FROM custom_sessions WHERE session_id = $1`,[authenticatedUser['userRow']['session_id']]);

    await logEvent(authenticatedUser.userRow.data, "", "User logged out from back office");

    res.cookie(SESSION_ID, "", {
      httpOnly: true,
      sameSite: 'Lax',
    });

    res.json({
      success: true,
      message: "Successfully logged out",
    });
}

async function filterEntities(req, res, next, client, authenticatedUser) {
    let schema = req.body.schema;
    let filterById = req.body.id;
    console.log("filterById", filterById, "schema", schema);
    let tableName = schema.title;
    let action = (filterById === undefined) ? "read" : "edit";
    console.log("action <-> ", action);

    await backOfficeService.checkStaffPermissions(client, authenticatedUser.userRow.data, schema.title, "read");

    let {selectFields, joins, groupByFields} = await backOfficeService.makeTableJoins(schema, action);

    console.log("selectFields", selectFields, "joins", joins, "groupByFields", groupByFields);

    let { whereConditions, values} = await backOfficeService.makeTableFilters(schema, req);

    console.log("whereConditions", whereConditions, "values", values);

    let selectClause = selectFields.join(", ");
    let joinClause = joins.join(" ");
    let groupByClause = groupByFields.length > 0 ? `GROUP BY ${groupByFields.join(", ")}` : "";
    let whereClause = whereConditions.length > 0 ? `WHERE ${whereConditions.join(" AND ")}` : "";

    let query = `SELECT ${selectClause} FROM ${tableName} ${joinClause} ${whereClause} ${groupByClause} LIMIT 50`;
    console.log(query);
    console.log(values);
    const result = await client.query(query, values);
    AssertUser(result.rows.length != 0, "There is no such entity with this filters, try another filters", errors.NO_SUCH_ENTITY_WITH_APLIED_FILTERS);
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

async function createEntityHandler(req, res, next, client, authenticatedUser) { // client -> dbConnection
    let schemaName = req.path.split("/")[2];
    let schema = require(`./schemas/${schemaName}_validation_schema.json`);

    await backOfficeService.checkStaffPermissions(client, authenticatedUser.userRow.data, schema.title, "create");

    let {formData, imageIds} = await backOfficeService.parseMultipartFormData(req, client);

    console.log("formData (?)", formData, "imageIds (?)", imageIds);

    await createEntity(client, schemaName, schema, formData, imageIds);

    await logEvent(authenticatedUser.userRow.data, "", "User created new " + schema.title + " from CRUD inteface");

    res.status(201).json({ message: `${schema.title} created successfully`});
}

async function createEntity(client, schemaName, schema, formData, imageIds) {
    const ajv = new Ajv({ allErrors: true, useDefaults: true, strict: false});
    addFormats(ajv);
    ajvErrors(ajv);
    const validateEntity = ajv.compile(schema);

    let beforeHookObj = {formData}
    let hooksBefore = crudHooks[schemaName]?.create.before;
    if (hooksBefore) {
        for(const hook of Object.values(hooksBefore)) {
            value = await hook(client, beforeHookObj);
            // 
            formData.filters = value;
        }
    }

    let {columns, values, foreignKeyLookups, manyToManyInserts, oneToManyInsertions} = await backOfficeService.mapSchemaPropertiesToDBRelations(formData, schema);

    console.log("beforeHookObj AFTER beforeHookObj", beforeHookObj);
    console.log("columns (?)", columns, "values (?)", values, "foreignKeyLookups (?)", foreignKeyLookups, "manyToManyInserts (?)", manyToManyInserts, "oneToManyInsertions (?)", oneToManyInsertions);

    // Step 2: Execute foreign key lookups
    for (const fk of foreignKeyLookups) {
        columns.push(fk.field);
        values.push(fk.value);
    }

    let insertQuery;
    let tablePK = schema.primaryKey;
    console.log("tablePK in create entity", tablePK);
    let entityId;

    // Step 3: Insert main entity
    const placeholders = columns.map((_, i) => `$${i + 1}`);
    insertQuery = `INSERT INTO ${schema.title} (${columns.join(", ")})
                         VALUES (${placeholders.join(", ")}) RETURNING ${tablePK}`;

    console.log("insertQuery", insertQuery);
    const { rows } = await client.query(insertQuery, values);
    console.log("rows[0][tablePK]", rows[0][tablePK]);
    entityId = rows[0][tablePK];

    console.log("entityId", entityId);

    // Step 4: Handle many-to-many insertions
    for (const m2m of manyToManyInserts) {
        console.log("m2m", m2m);
        console.log("m2m.values", m2m.values);
        console.log("m2m.values.typeof", typeof m2m.values);

        if (m2m.field === 'permissions') {
            formData.permissions = JSON.parse(formData.permissions);
            for (const permissionId of formData.permissions) {
                const insertQuery = `
                    INSERT INTO ${m2m.joinTable} (${m2m.joinColumnOnePK}, ${m2m.joinColumnTwoPK})
                    VALUES ($1, $2)
                `;
                console.log("permissionId", permissionId, "typeof permissionId", typeof permissionId, "insertQuery", insertQuery, "entityId", entityId);
                await client.query(insertQuery, [entityId, permissionId]);
            }
        } else if (typeof m2m.values === 'string') {
            m2m.values = [...m2m.values];
            console.log("m2m.values", m2m.values);
            console.log("m2m.values.typeof", typeof m2m.values);

            const joinInserts = m2m.values.map(value => ({
                query: `INSERT INTO ${m2m.joinTable} (${m2m.joinColumnOnePK}, ${m2m.joinColumnTwoPK})
                        VALUES ($1, (SELECT ${m2m.targetColumnFilter} FROM ${m2m.targetTable} WHERE ${m2m.targetColumnFilter} = $2))`,
                values: [entityId, value]
            }));

            for (const insert of joinInserts) {
                await client.query(insert.query, insert.values);
            }
        } else {
            const joinInserts = m2m.values.map(value => ({
                query: `INSERT INTO ${m2m.joinTable} (${m2m.joinColumnOnePK}, ${m2m.joinColumnTwoPK})
                        VALUES ($1, (SELECT ${m2m.targetColumnFilter} FROM ${m2m.targetTable} WHERE ${m2m.targetColumnFilter} = $2))`,
                values: [entityId, value]
            }));

            for (const insert of joinInserts) {
                await client.query(insert.query, insert.values);
            }
        }
    }

    // Step 5: Handle one to many insertions
    for (const o2m of oneToManyInsertions) {
        // Update each insertion with the actual entityId
        console.log("o2m", o2m);
        console.log("values[0]", values[0]);
        o2m.values[0] = entityId;

        await client.query(o2m.query, o2m.values);
    }

    let afterHookObj = {imageIds, formData, beforeHookObj};
    let hooksAfter = crudHooks[schemaName]?.create.after;
    if (hooksAfter) {
        for(const hook of Object.values(hooksAfter)) {
            values = await hook(client, entityId, afterHookObj);
        }
    }
}

async function updateEntity(req, res, next, client, authenticatedUser) {
    let schemaName = req.path.split("/")[2];
    let schema = require(`./schemas/${schemaName}_validation_schema.json`);

    await backOfficeService.checkStaffPermissions(client, authenticatedUser.userRow.data, schema.title, "update");

    const ajv = new Ajv({ allErrors: true, useDefaults: true, strict: false});
    ajvErrors(ajv);
    const validateEntity = ajv.compile(schema);

    let {formData, imageIds} = await backOfficeService.parseMultipartFormData(req, client);

    formData.user = authenticatedUser.userRow.data;

    let beforeHookObj = {formData}
    let hooksBefore = crudHooks[schemaName]?.update.before;
    if (hooksBefore) {
        for(const hook of Object.values(hooksBefore)) {
            let values = await hook(client, beforeHookObj);
        }
    }

    let {columns, values, foreignKeyLookups, manyToManyInserts, oneToManyInsertions} = await backOfficeService.mapSchemaPropertiesToDBRelations(formData, schema);

    console.log("columns", columns, "values", values, "foreignKeyLookups", foreignKeyLookups, "manyToManyInserts", manyToManyInserts, "oneToManyInsertions", oneToManyInsertions);

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
    let tablePK = schema.primaryKey;
    console.log("tablePK", tablePK);

    updateQuery = `UPDATE ${schema.title} SET ${setClause} WHERE ${tablePK} = $${columns.length + 1} RETURNING ${tablePK}`;
    // if (schemaName == "orders") {
    //     updateQuery = `UPDATE ${schema.title} SET ${setClause} WHERE order_id = $${columns.length + 1} RETURNING order_id`;
    // } else {
    //     updateQuery = `UPDATE ${schema.title} SET ${setClause} WHERE id = $${columns.length + 1} RETURNING id`;
    // }

    console.log("formData", formData, "formData.tablePK", formData[tablePK]);
    // let update
    let entityId = formData[tablePK];
    console.log("entityId", entityId);
    // if (schemaName == 'orders') {
    //     entityId = formData.order_id;
    // } else {
    //     entityId = formData.id;
    // }

    values.push(entityId);
    console.log("updateQuery", updateQuery, "values", values);

    const { rows } = await client.query(updateQuery, values);

    // Handle Many-to-Many Updates
    for (const m2m of manyToManyInserts) {
        const deleteQuery = `DELETE FROM ${m2m.joinTable} WHERE ${m2m.joinColumnOnePK} = $1`;
        console.log("m2m", m2m, "deleteQuery", deleteQuery, "entityId", entityId);
        await client.query(deleteQuery, [entityId]);

        if (m2m.field === 'permissions') {
            formData.permissions = JSON.parse(formData.permissions);
            for (const permissionId of formData.permissions) {
                const insertQuery = `
                    INSERT INTO ${m2m.joinTable} (${m2m.joinColumnOnePK}, ${m2m.joinColumnTwoPK})
                    VALUES ($1, $2)
                `;
                console.log("permissionId", permissionId, "typeof permissionId", typeof permissionId, "insertQuery", insertQuery, "entityId", entityId);
                await client.query(insertQuery, [entityId, permissionId]);
            }
        } else {
            for (const value of m2m.values) {
                const insertQuery = `
                    INSERT INTO ${m2m.joinTable} (${m2m.joinColumnOnePK}, ${m2m.joinColumnTwoPK})
                    VALUES ($1, (SELECT ${m2m.targetColumnFilter} FROM ${m2m.targetTable} WHERE ${m2m.targetColumnFilter} = $2))
                `;
                console.log("insertQuery in many to many table", insertQuery);
                await client.query(insertQuery, [entityId, value]);
            }
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

    console.log("inputData", inputData, "reportFilters", reportFilters, "reportName", reportName);

    const { sqlTemplate, queryParams } = await backOfficeService.generateReportSQLQuery(inputData, reportFilters, reportName);

    const result = await client.query(sqlTemplate, queryParams);
    let resultRows = result.rows;

    console.log("resultRows", resultRows);

    let totalRows = resultRows.length > 0 ? resultRows[0]["Total Rows"] : 0;
    resultRows.forEach(row => delete row["Total Rows"]);

    if (resultRows.length > 0) {
        const firstColumnName = Object.keys(resultRows[0])[0];
        const totalsRow = resultRows[0];
        
        // Check if first row is a totals row
        if (totalsRow[firstColumnName] === null || 
            totalsRow[firstColumnName] === 'TOTAL' || 
            totalsRow[firstColumnName] === '-') {
            
            // Remove totals row from the beginning
            resultRows.shift();
            // Add it to the end
            resultRows.push(totalsRow);
        }
    }

    res.json({resultRows, totalRows});
}

async function getOrderItemsData(req, res, next, client) {
    const inputData = req.query;
    let orderId = inputData.order_id;

    let settings = await client.query(`SELECT vat FROM settings`);

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

    return res.status(200).json({ data: rows.rows, vat: settings.rows[0].vat });
}

async function getRolePermissions(req, res, next, client) {
    const inputData = req.query;
    let roleId = inputData.role_id;

    console.log("inputData", inputData, "roleId", roleId);

    console.log("getRolePermissions for role");    

    let rows = await client.query(`
                                SELECT
                                    permissions.permission_id,
                                    permission_name, 
                                    interface, 
                                    description 
                                FROM roles 
                                    JOIN role_permissions ON roles.role_id = role_permissions.role_id 
                                    JOIN permissions ON role_permissions.permission_id = permissions.permission_id 
                                where roles.role_id = $1;
                                `, [roleId]);
    let permissionResult = rows.rows;
    console.log(permissionResult);
    return res.status(200).json({ permissionResult });
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

async function exportEntityHandler(req, res, next, client) {
    const { format } = req.query;
    const { entityType, filters } = req.body;

    const { sqlTemplate, queryParams } = await backOfficeService.generateReportSQLQuery(filters, require(`./schemas/${entityType}.json`), entityType);

    console.log("sqlTemplate", sqlTemplate);
    console.log("queryParams", queryParams);

    const metadata = [
        ['Filters Applied'],
        ...Object.entries(filters).map(([key, details]) => 
            [formatKey(key), JSON.stringify(details)]
        ),
        ['Generated On', new Date().toLocaleString()]
    ];

    console.log("metadata", metadata);

    if (format === 'csv') {
        await exportCsv(res, client, sqlTemplate, queryParams, metadata);
    } else if (format === 'excel') {
        await exportExcel(res, client, sqlTemplate, queryParams, metadata);
    } else {
        AssertUser(false, "Invalid format");
    }
}

function formatKey(key) {
    return key
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' '); // Join back with spaces
}

async function exportCsv(res, client, sqlTemplate, queryParams, metadata) {
    const csvStream = stringify();
    try {
        res.setHeader('Content-Type', 'text/csv');
        res.setHeader('Content-Disposition', 'attachment; filename="report.csv"');

        csvStream.pipe(res);

        metadata.forEach((meta) => csvStream.write(meta));

        const reportHeaders = await getReportHeaders(client, sqlTemplate, queryParams);
        csvStream.write(reportHeaders);

        for await (const rows of backOfficeService.fetchReportData(client, sqlTemplate, queryParams)) {
            // await client.query("BEGIN");
            console.log("rows -> ", rows)
            for (let row of rows) {
                const formattedRow = Object.entries(row).reduce((acc, [key, value]) => {
                    if (key.includes('Inserted At') && value) {
                        acc[key] = formatTimestamp(value);
                    } else {
                        acc[key] = value;
                    }
                    return acc;
                }, {});
                csvStream.write(Object.values(formattedRow));
            }
        }
    } catch (error) {
        throw error;
    } finally {
        csvStream.end();
    }
}

async function getReportHeaders(client, sqlTemplate, queryParams) {
    const previewQuery = sqlTemplate.replace('LIMIT 1000', 'LIMIT 1');
    const { rows } = await client.query(previewQuery, queryParams);
    return rows.length > 0 ? Object.keys(rows[0]) : [];
}

async function exportExcel(res, client, sqlTemplate, queryParams, metadata) {
    const workbook = new ExcelJS.Workbook();
    try {
        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        res.setHeader('Content-Disposition', 'attachment; filename="report.xlsx"');

        const workbook = new ExcelJS.Workbook();
        const worksheet = workbook.addWorksheet('Report');

        metadata.forEach((metaRow) => {
            worksheet.addRow(metaRow);
        });

        worksheet.addRow([]);

        const reportHeaders = await getReportHeaders(client, sqlTemplate, queryParams);
        worksheet.addRow(reportHeaders);

        for await (const rows of backOfficeService.fetchReportData(client, sqlTemplate, queryParams)) {
            rows.forEach((row) => {
                const formattedRow = Object.entries(row).map(([key, value]) => {
                    if (key.includes('Inserted At') && value) {
                        return formatTimestamp(value);
                    }
                    return value;
                });

                worksheet.addRow(formattedRow);
            });

            await streamWorkbookToResponse(workbook, res);
        }
    } catch (error) {
        throw error;
    } finally {
        await workbook.xlsx.write(res);
        res.end();
    }
}
async function streamWorkbookToResponse(workbook, res) {
    const tempStream = new PassThrough();
    await workbook.xlsx.write(tempStream, { useSharedStrings: true, useStyles: true });
    tempStream.pipe(res, { end: false });
}

function formatTimestamp(timestamp) {
    const date = new Date(Number(timestamp)); 
    return date.toLocaleString();
}

async function uploadEntitiesHandler(req, res, next, client, authenticatedUser) {
    let schemaName = "products";
    let schema = require(`./schemas/${schemaName}_validation_schema.json`);

    await client.query('COMMIT');
    let count = 0;
    for await (const formData of backOfficeService.parseMultipartFormDataGenerator(req, client)) {

        await client.query('BEGIN');

        await createEntity(client, schemaName, schema, formData.row, formData.imageId);

        await client.query('COMMIT');
    }

    return res.status(200).json({ message: `Successfully uploaded ${count} rows`});
}

async function getRolesHandler(req, res, next, client) {
    const result = await client.query(`
        SELECT
            role_id             AS id ,
            role_name           AS name
        FROM roles
    `); 
    return res.json(result.rows); 
}

async function getPermissions(req, res, next, client) {
    const result = await client.query(`
        SELECT
            *
        FROM permissions
    `); 
    return res.json({data: result.rows}); 
}

async function getPermissionsForCreate(req, res, next, client) {
    const result = await client.query(`
        SELECT
            DISTINCT(permission_name) as name
        FROM permissions
    `);

    return res.json( result.rows ); 
}

async function getStaffPermissions(req, res, next, client, authenticatedUser) {
    const permissions = await backOfficeService.getStaffPermissions(client, authenticatedUser.userRow.data);

    return res.json({ data: permissions })
}

async function auditRolePermissionChanges(client, beforeHookObj) {
    console.log(" beforeHookObj in auditRolePermissionChanges", beforeHookObj);

    const permissionsAudit = JSON.parse(beforeHookObj.formData.permissionsAudit);

    console.log("Parsed permissionsAudit:", permissionsAudit);

    let message = "";

    const permissionIds = [...permissionsAudit.added, ...permissionsAudit.removed];

    console.log("permissionIds", permissionIds);

    if (permissionIds.length > 0) {
        const query = `
            SELECT permission_id, permission_name, interface
            FROM permissions
            WHERE permission_id = ANY($1)
        `;
        const { rows } = await client.query(query, [permissionIds]);

        console.log("rows", rows);

        const idToPermissionInfoMap = rows.reduce((acc, row) => {
            acc[row.permission_id] = { name: row.permission_name, interface: row.interface };
            return acc;
        }, {});

        console.log("idToPermissionInfoMap", idToPermissionInfoMap);

        if (permissionsAudit.added.length > 0) {
            const addedInfo = permissionsAudit.added.map(id => 
                `${idToPermissionInfoMap[id].name} (${idToPermissionInfoMap[id].interface})`
            );

            console.log("addedInfo", addedInfo);

            message += `Added permissions: ${addedInfo.join(", ")}. `;
        }

        if (permissionsAudit.removed.length > 0) {
            const removedInfo = permissionsAudit.removed.map(id => 
                `${idToPermissionInfoMap[id].name} (${idToPermissionInfoMap[id].interface})`
            );

            console.log("removedInfo", removedInfo);

            message += `Removed permissions: ${removedInfo.join(", ")}. `;
        }
        message += `Updated for role: ${beforeHookObj.formData.role_name}`;
    }

    console.log("Audit Log Message:", message);

    await logEvent(beforeHookObj.formData.user, "", message);
}

async function getEmailTemplatesHandler(req, res, next, client, authenticatedUser) {
    const templatesData = await backOfficeService.getTemplatesData(client);

    console.log("templatesData", templatesData);

    return res.json({ emails: templatesData});
}

async function getEmailByIdHnadler(req, res, next, client) {
    let templateId = req.path.split("/")[2];

    const templateRow = await backOfficeService.getTemplateById(client, templateId);

    console.log("templateRow", templateRow.rows);

    return res.json({ template: templateRow.rows});
}


async function getDistinctValuesHandler(req, res, next, client) {
    const { field } = req.query;

    const allowedFields = ['audit_type', 'sub_system', 'log_type'];

    AssertUser(allowedFields.includes(field), "Invalid field");

    const result = await client.query(`SELECT DISTINCT ${field} FROM exception_logs`);
    const values = result.rows.map(row => row[field]);

    res.json(values);
}

async function mapTargetGroupsWithFilters(client, beforeHookObj) {
    console.log("beforeHookObj", beforeHookObj);
    const formData = beforeHookObj.formData;
    
    const jsonFilters = Object.entries(formData)
        .reduce((acc, [key, value]) => {
            if (key.startsWith('filter_')) {
                const filterKey = key.replace('filter_', '');
                acc[filterKey] = value;
            }
            return acc;
        }, {});

    console.log("jsonFilters", jsonFilters);
    beforeHookObj.jsonFilters = jsonFilters
    console.log("beforeHookObj", beforeHookObj);

    return jsonFilters;
}

async function mapUsersToTargetGroup(client, entityId, afterHookObj) { 
    const filterResult = await client.query(
        "SELECT filters FROM target_groups WHERE id = $1",
        [entityId]
    );
    
    const filters = filterResult.rows[0].filters;
    
    const columnMap = {
        'date': 'birth_date',
        'first_name': 'first_name',
        'last_name': 'last_name'
    };

    let paramIndex = 3;
    const whereConditions = Object.entries(filters).map(([key, value]) => {
        const columnName = columnMap[key] || key;
        if (key === 'date') {
            return `${columnName} = $${paramIndex++}`;
        }
        return `${columnName} ILIKE $${paramIndex++}`;
    });
    
    const paramValues = Object.entries(filters).map(([key, value]) => {
        if (key === 'date') {
            return value;
        }
        return `%${value}%`;
    });

    // check if we have user in the group
    const insertQuery = `
        INSERT INTO user_target_groups (user_id, target_group_id)
        SELECT id, $1
        FROM users
        WHERE ${whereConditions.join(' AND ')}
        AND NOT EXISTS (
            SELECT 1 FROM user_target_groups 
            WHERE user_id = users.id 
            AND target_group_id = $2
        )
    `;
    
    const params = [entityId, entityId, ...paramValues];
    
    await client.query(insertQuery, params);
}

async function getTargetGroupsHandler(req, res, next, client) {
    let resultRows = await client.query(`
        SELECT 
            id, 
            name, 
            count(user_target_groups.user_id), 
            created_at 
        FROM target_groups 
        JOIN user_target_groups ON target_groups.id = user_target_groups.target_group_id 
        GROUP BY id, name, created_at
    `);

    return res.json({
        resultRows: resultRows.rows
    })
}

async function getUsersInTargetGroup(req, res, next, client) {
    let targetGroupId = req.path.split("/")[2];
    let query = `
        SELECT 
            users.first_name, 
            users.last_name, 
            users.email, 
            users.birth_date 
        FROM target_groups 
        JOIN user_target_groups ON target_groups.id = user_target_groups.target_group_id 
        JOIN users on user_target_groups.user_id = users.id 
        WHERE target_groups.id = $1`

    let resultRows = await client.query(query, [targetGroupId]);

    return res.json({
        resultRows: resultRows.rows
    })
}

async function exportTargetGroupHandler(req, res, next, client) {
    let targetGroupId = req.path.split("/")[2];

    const filters = { 'target_group_filter_value': targetGroupId };

    req.query.format = 'csv';
    req.body = { entityType: 'target_group', filters };

    await exportEntityHandler(req, res, next, client);
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
    if (error.message === 'Request timed out') {
        console.log('Ignored timeout error:', error);
        return;
    }
    console.error("error in unhandledRejection >>>");
    console.error(error);
    try {
        await logException("Guest", error.name || "Error", error.message || "reason", "back office");
    } catch (loggingError) {
        console.error("Error while logging unhandled rejection:", loggingError);
    }
});

module.exports = router;