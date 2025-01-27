const { AssertUser, AssertDev } = require('./exceptions');
const errors = require('./error_codes');
const bcrypt = require('bcryptjs');
const fs = require('fs');
const path = require('path');
const { pipeline } = require('stream');
const { promisify } = require('util');
const { v4: uuidv4 } = require('uuid');
const bufferSplit = require('buffer-split');
const Cursor = require('pg-cursor');
const axios = require('axios');
const config = require('./config');
const { EmailDataMapper } = require('./emailDataMapper');

const INTERFACE_MAPPING = {
  staff: 'CRUD Staff',
  roles: 'Staff roles',
  users: 'CRUD Users',
  orders: 'CRUD Orders',
  products: 'CRUD Products',
  email_template: 'CRUD Email',
  settings: 'CRUD Email',
  promotions: 'CRUD Promotions',
  target_groups: 'CRUD Target Groups',
  settings: 'CRUD Settings'
};

const VALID_INTERFACES = [
  'CRUD Products',
  'Logs',
  'Captcha Settings',
  'Report sales',
  'Staff roles',
  'CRUD Orders',
  'CRUD Users',
  'CRUD Staff',
  'CRUD Email',
  'CRUD Promotions',
  'CRUD Target Groups',
  'CRUD Settings'
];

async function login(username, password, client) {
	AssertDev(username != undefined, "username is undefined");
	AssertDev(password != undefined, "password is undefined");

	let user = await client.query(`SELECT * FROM staff WHERE username = $1`, [username]);
	let userRow = user.rows;

	AssertDev(userRow.length == 1, "User row can't return more than one user");
    AssertUser(await bcrypt.compare(password, userRow[0]['password']), "Invalid email or password")

	return userRow[0].username;
}

async function parseMultipartFormData(req, client) {
    AssertUser(req.headers['content-type'].startsWith('multipart/form-data'), 'Invalid inputs: Expected multipart/form-data', errors.NOT_FOUND_MULTYPART_FROM_DATA);

    const boundary = getBoundary(req.headers['content-type']);
    AssertUser(boundary, 'Invalid inputs: Boundary not found in the Content-Type header', errors.NOT_FOUND_BOUNDARY);

    let formData = {};
    let imageIds = [];
    let buffer = Buffer.alloc(0);

    for await (const chunk of req) {
        buffer = Buffer.concat([buffer, chunk]);
    }
    console.log("buffer.toString()", buffer.toString());

    try {
        const parts = bufferSplit(buffer, new Buffer(`--${boundary}`));

        console.log("parts", parts.toString());

        for (const part of parts) {
            let partString = part.toString();

            console.log("partString", partString);

            if (partString === '--\r\n' || partString === '--\r\n--') continue;

            // Separate headers from content
            const [headers, content] = bufferSplit(part, new Buffer('\r\n\r\n')); // '\r\n\r\n'

            if (!headers || !content) continue;

            let headersString = headers.toString();
            const headerLines = headersString.split('\r\n');

            const contentDisposition = headerLines.find(line => line.startsWith('Content-Disposition'));
            const contentType = headerLines.find(line => line.startsWith('Content-Type'));

            const nameMatch = /name="(.+?)"/.exec(contentDisposition);
            const filenameMatch = /filename="(.+?)"/.exec(contentDisposition);

            if (filenameMatch) {
                AssertDev(contentType && contentType.includes("image/jpeg"), "Not image/jpeg");
                const filename = filenameMatch[1];
                const uniqueFilename = `${uuidv4()}-${filename}`;
                const filePath = path.join(__dirname, 'images', uniqueFilename);

                const { rows } = await client.query(
                    `INSERT INTO images (product_id, path, status) VALUES ($1, $2, $3) RETURNING id`,
                    [null, uniqueFilename, 'in_progress']
                );

                await client.query('COMMIT');
                await client.query('BEGIN');

                const imageId = rows[0].id;
                imageIds.push(imageId);

                var len = Buffer.byteLength(content);
                console.log("binaryContent", filenameMatch, len);

                await fs.promises.writeFile(filePath, content.slice(0, -2));

                await client.query(`UPDATE images SET status = 'completed' WHERE id = $1`, [imageId]);
            } else {
                const fieldName = nameMatch[1];
                const fieldValue = content.toString().trim();

                console.log("fieldName", fieldName, "fieldValue", fieldValue)

                if (fieldName === 'categories') {
                    if (!Array.isArray(formData.categories)) {
                        formData.categories = formData.categories ? [formData.categories] : [];
                    }

                    formData.categories.push(fieldValue);
                    console.log("formData categories debug", formData)
                } else if (fieldName === 'roles') {
                    formData.roles = formData.roles || [];
                    formData.roles.push(fieldValue);
                } else {
                    formData[fieldName] = fieldValue;
                }
            }
        }

        console.log("formData returned", formData);
        return { formData, imageIds};
    } catch (error) {
        throw(error);
    }
}

async function* parseMultipartFormDataGenerator(req, client) {
    AssertUser(req.headers['content-type'].startsWith('multipart/form-data'), 'Invalid inputs: Expected multipart/form-data', errors.NOT_FOUND_MULTYPART_FROM_DATA);

    const boundary = getBoundary(req.headers['content-type']);
    AssertUser(boundary, 'Invalid inputs: Boundary not found in the Content-Type header', errors.NOT_FOUND_BOUNDARY);

    let buffer = Buffer.alloc(0);

    for await (const chunk of req) {
        buffer = Buffer.concat([buffer, chunk]);
    }
    const parts = bufferSplit(buffer, new Buffer(`--${boundary}`));

    for (const part of parts) {
        let partString = part.toString();

        if (partString.startsWith('--\r\n') || partString.startsWith('--\r\n--') || partString === `--\n `) continue;

        const [headers, content] = bufferSplit(part, new Buffer('\r\n\r\n')); // '\r\n\r\n'

        if (!headers || !content) continue;

        let headersString = headers.toString();
        const headerLines = headersString.split('\r\n');
        const contentDisposition = headerLines.find(line => line.startsWith('Content-Disposition'));
        const contentType = headerLines.find(line => line.startsWith('Content-Type'));

        const filenameMatch = /filename="(.+?)"/.exec(contentDisposition);
        const csvMatch =  contentType.includes("text/csv");

        AssertUser(csvMatch, "Provide csv file !");

        console.log("contentDisposition", contentDisposition);
        console.log("contentDisposition", contentDisposition.split(";")[2].split("filename="));

        const filename = filenameMatch[1];
        const filePath = path.join(__dirname, 'uploads', filename);
        await fs.promises.writeFile(filePath, content.slice(0, -2));
        const csvData = await fs.promises.readFile(filePath, 'utf8');

        for await (const parsedRow of parseCSV(csvData, client)) {
            yield parsedRow; // Yield each parsed row from CSV
        }
    }

}

async function* parseCSV(data, client) {
    const lines = data.split('\n').filter(line => line.trim().length > 0);
    const headers = parseLine(lines[0]);

    for (const line of lines.slice(1)) {
        const values = parseLine(line);

        const row = headers.reduce((obj, header, index) => {
            obj[header] = values[index];
            return obj;
        }, {});

        const originalFileName = path.basename(new URL(row.path).pathname);
        const uniqueFilename = `${uuidv4()}-${originalFileName}`;
        const filePath = path.join(__dirname, 'images', uniqueFilename);

        const { rows } = await client.query(
            `INSERT INTO images (product_id, path, status) VALUES ($1, $2, $3) RETURNING id`,
            [null, uniqueFilename, 'in_progress']
        );

        await client.query('COMMIT');
        await client.query('BEGIN');

        const imageId = rows[0].id;
        let imageIds = [];
        imageIds.push(imageId);

        try {
            const response = await axios({
                method: 'get',
                url: row.path,
                responseType: 'arraybuffer'
            });

            await fs.promises.writeFile(filePath, response.data);
            await client.query(`UPDATE images SET status = 'completed' WHERE id = $1`, [imageId]);

        } catch (error) {
            console.error(`Error processing image at ${row.path}:`, error);
            throw error;
        }

        let objToReturn = {row: row, imageId: imageIds}
        yield objToReturn;
    }
}

function parseLine(line) {
    const result = [];
    let currentField = '';
    let insideQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];

        if (char === '"' && line[i + 1] === '"') {
            // Handle escaped quotes (double quotes inside a quoted field)
            currentField += '"';
            i++; // Skip the next quote
        } else if (char === '"') {
            // Whether we are inside quotes
            insideQuotes = !insideQuotes;
        } else if (char === ',' && !insideQuotes) {
            // Field separator (only outside quotes)
            result.push(currentField);
            currentField = '';
        } else {
            // Add character to the current field
            currentField += char;
        }
    }

    // Add the last field
    result.push(currentField);

    return result.map(value => value.trim()); // Trim spaces around each value
}

async function mapSchemaPropertiesToDBRelations(formData, schema) {
    console.log("ENTERED IN mapSchemaPropertiesToDBRelations");
    console.log("formData");
    console.log(formData);
	let columns = [];
    let values = [];
    let foreignKeyLookups = [];
    let manyToManyInserts = [];
    let oneToManyInsertions = [];

	for (let [field, definition] of Object.entries(schema.properties)) {

        console.log("field");
        console.log(field);

        console.log("definition.foreignKey");
        console.log(definition.foreignKey);

        console.log("formData[field]");
        console.log(formData[field]);

        console.log("formData[field]");
        console.log(formData.field);

        console.log("");

        if (definition.readOnly || field == "vat_id") continue;

        console.log("After continue");
        if (definition.foreignKey) {
            if (definition.type == 'array') {
                if (field == "images") {continue;}
                console.log("Entered in array foreignKey handling for", field);
                // continue;
                // oneToManyInsertions.push({ field, ...definition.manyToMany, values: formData[field] });
                const itemsArray = JSON.parse(formData[field]); 
                const tableName = definition.foreignKey.table;
                const foreignKeyField = definition.foreignKey.value;

                console.log("itemsArray");
                console.log(itemsArray);
                console.log("tableName");
                console.log(tableName);
                console.log("foreignKeyField");
                console.log(foreignKeyField);

                const orderItemsInsertions = buildInsertQueries(tableName, itemsArray, foreignKeyField);
                console.log("orderItemsInsertions");
                console.log(orderItemsInsertions);
                oneToManyInsertions.push(...orderItemsInsertions);
                console.log("oneToManyInsertions");
                console.log(oneToManyInsertions);
            } else {
                console.log("Entered in single value foreignKey handling for", field);
                foreignKeyLookups.push({ field, ...definition.foreignKey, value: formData[field] });
            }
            console.log("END");

        } else if (definition.manyToMany) {
            // Handle many-to-many relationships: Insert into join table
            manyToManyInserts.push({ field, ...definition.manyToMany, values: formData[field] });
        } else {
            // Regular insert column
            // if (details.PK === true) {
            //     selectFields.push(`${tableName}.${tableNamePrimaryKey}`);
            //     groupByFields.push(`${tableName}.${tableNamePrimaryKey}`);
            // } else {
            //     selectFields.push(`${tableName}.${field}`);
            //     groupByFields.push(`${tableName}.${field}`);
            // }
            columns.push(field);
            values.push(formData[field]);
        }
    }

    return {columns, values, foreignKeyLookups, manyToManyInserts, oneToManyInsertions}
}

// Helper function to parse the multipart form data boundary
function getBoundary(header) {
    const items = header.split(';');

    // items -> ['multipart/form-data',' boundary=----WebKitFormBoundarySBOhdraLPnSR4F2D']

    for (let i = 0; i < items.length; i++) {
        const item = items[i].trim();

        if (item.startsWith('boundary')) {
            return item.split('=')[1]; // return -> boundary=----WebKitFormBoundarySBOhdraLPnSR4F2D
        }
    }
    return null;
}

async function makeTableJoins(schema, action) {
	let selectFields = [];
    let joins = [];
    let groupByFields = [];

    let tableName = schema.title;
    let tableNamePrimaryKey = schema.primaryKey;
    console.log("tableNamePrimaryKey", tableNamePrimaryKey);

    for (const [field, details] of Object.entries(schema.properties)) {
        console.log("field");
        console.log(field);
        console.log("details");
        console.log(details);
        console.log("action", action);

        if (details?.skippable?.[action] == true) {
            continue;
        }

        if (details.computed) {
            if (field === "total") {
                selectFields.push("SUM(order_items.price * order_items.quantity) AS Total");
            } else if (field === "vat") {
                selectFields.push("ROUND(SUM(order_items.price * order_items.quantity * (CAST(order_items.vat AS numeric) / 100)), 2) AS Vat");
            } else if (field === "total_with_vat") {
                selectFields.push(
                    "ROUND(SUM(order_items.price * order_items.quantity) + " +
                    "SUM(order_items.price * order_items.quantity * (CAST(order_items.vat AS numeric) / 100)), 2) AS \"Total With Vat\""
                );
            } else if (field === "discount_amount") {
                selectFields.push(
                    "round(((sum(order_items.price * order_items.quantity) + sum(order_items.price * order_items.quantity * " + 
                    "(cast(order_items.vat as numeric) / 100)))) * (orders.discount_percentage / 100.0), 2) AS \"Discount Amount\""
                );
            } else if (field === "price_after_discount") {
                selectFields.push(
                    "round( sum(order_items.price * order_items.quantity) + sum(order_items.price * order_items.quantity * " + 
                    "(cast(order_items.vat as numeric) / 100)) - ((sum(order_items.price * order_items.quantity) + sum(order_items.price * order_items.quantity * (cast(order_items.vat as numeric) / 100)))) * (orders.discount_percentage / 100.0), 2) AS \"Price after discount\""
                );
            }
            continue;
        }

	    if (details.manyToMany) {

	        let joinTable = details.manyToMany.joinTable;
	        let joinColumnOnePK = details.manyToMany.joinColumnOnePK;
	        let joinColumnTwoPK = details.manyToMany.joinColumnTwoPK;
	        let targetTable = details.manyToMany.targetTable;
	        let targetColumn = details.manyToMany.targetColumn;
            let targetColumnFilter = details.manyToMany.targetColumnFilter;

            console.log("joinTable", joinTable, "joinColumnOnePK", joinColumnOnePK, "joinColumnTwoPK", joinColumnTwoPK, "targetTable", targetTable, "targetColumn", targetColumn);

	        // joins.push(`JOIN ${joinTable} ON ${tableName}.id = ${joinTable}.${joinColumnOnePK}`);
            joins.push(`JOIN ${joinTable} ON ${tableName}.${schema.primaryKey} = ${joinTable}.${joinColumnOnePK}`);
	        // joins.push(`JOIN ${targetTable} ON ${joinTable}.${joinColumnTwoPK} = ${targetTable}.id`);
            // if (schema.title == "roles") {
            joins.push(`JOIN ${targetTable} ON ${joinTable}.${joinColumnTwoPK} = ${targetTable}.${targetColumnFilter}`);
            // } else {
            //     joins.push(`JOIN ${targetTable} ON ${joinTable}.${joinColumnTwoPK} = ${targetTable}.id`);
            // }

	        selectFields.push(`array_agg(DISTINCT(${targetTable}.${targetColumn})) AS ${targetTable}`);

	    } else if (details.foreignKey) {
            // if (field == "order_items") {continue;}

	        let joinTable = details.foreignKey.table;
	        let joinColumn = details.foreignKey.value;
	        let joinColumnToDisplay = details.foreignKey.column;
	        let currentTableToJoin = details.foreignKey.currentTableToJoin;

            console.log("-----------------------------");
            console.log("joinTable");
            console.log(joinTable);
            console.log("joinColumn");
            console.log(joinColumn);
            console.log("joinColumnToDisplay");
            console.log(joinColumnToDisplay);
	        console.log("currentTableToJoin");
	        console.log(currentTableToJoin);
	        console.log("details.type");
	        console.log(details.type);

	        if (details.type == 'array') { // Handle one-to-many
	            console.log("Array.isArray(details.type) NO ELSEEE");
                if (joinTable == 'order_items') {
                    joins.push(`JOIN ${joinTable} ON ${currentTableToJoin} = ${joinTable}.${joinColumn}`);
                    selectFields.push(`array_agg(DISTINCT(${details.foreignKey.columnsToShowOnEdit})) AS "${details.label}"`);
                } else {
                    joins.push(`JOIN ${joinTable} ON ${currentTableToJoin} = ${joinTable}.${joinColumn}`);
	                selectFields.push(`array_agg(DISTINCT(${joinTable}.${joinColumnToDisplay})) AS "${details.label}"`);
                }
	        } else {
	            console.log("Array.isArray(details.type) ELSEEE");

	             const joinColumnToDisplay = details.foreignKey.column;
	             joins.push(`JOIN ${joinTable} ON ${tableName}.${field} = ${joinTable}.${joinColumn}`);
	             selectFields.push(`${joinTable}.${joinColumnToDisplay} AS "${details.label}"`);

	             groupByFields.push(`${joinTable}.${joinColumnToDisplay}`);
	        }
            console.log("-----------------------------");
	        
	        // joins.push(`JOIN ${joinTable} ON ${tableName}.${field} = ${joinTable}.${joinColumn}`);

	        // selectFields.push(`${joinTable}.${joinColumnToDisplay} AS ${joinColumnToDisplay}`); 

        } else {
            // Regular field, add to selectFields as is
            if (details.PK === true) {
                selectFields.push(`${tableName}.${tableNamePrimaryKey} AS "${details.label}"`);
                groupByFields.push(`${tableName}.${tableNamePrimaryKey}`);
            } else {
                selectFields.push(`${tableName}.${field} AS "${details.label}"`);
                groupByFields.push(`${tableName}.${field}`);
            }
        }
    }

    console.log("selectFields");
    console.log(selectFields);
    console.log("joins");
    console.log(joins);
    console.log("groupByFields");
    console.log(groupByFields);
    return {selectFields, joins, groupByFields}
}

async function makeTableFilters(schema, req) {
    console.log("req.body");
    console.log(req.body);

	let tableName = schema.title;

	let filters = schema.filters;
    let whereConditions = [];
    let values = [];

    console.log("filters------------------------------------------------------");
    console.log(filters);

    filters.forEach((filter) => {
        console.log("filter");
        console.log(filter);
        console.log("schema.properties[filter].type");
        console.log(schema.properties[filter].type);
        console.log("schema.properties[filter].fieldType");
        console.log(schema.properties[filter].fieldType);
        console.log("req.body[filter]", req.body[filter]);

        // if (req.body[filter] === undefined) { return; }

        if (schema.properties[filter].format === 'date') {
            const fromDate = req.body[`${filter}_from`];
            const toDate = req.body[`${filter}_to`];
            const date = req.body[`date`];

            console.log("| date |", date)

            if (fromDate) {
                whereConditions.push(`${tableName}.${filter} >= $${values.length + 1}`);
                values.push(fromDate);
            }
            if (toDate) {
                whereConditions.push(`${tableName}.${filter} <= $${values.length + 1}`);
                values.push(toDate);
            }
            if (date) {
                whereConditions.push(`${tableName}.${filter} >= $${values.length + 1} AND ${tableName}.${filter} <= $${values.length + 1}`);
                values.push(date); 
            }
        } else if (schema.properties[filter].type === 'string' && req.body[filter] != undefined) {
            console.log("filter is string");
            whereConditions.push(`${tableName}.${filter} = $${values.length + 1}`);
            values.push(req.body[filter]);
        } else if (schema.properties[filter].type === 'array' && schema.properties[filter].manyToMany && req.body[filter] != undefined) {
            console.log("filter is array (many-to-many)");
            const targetColumn = schema.properties[filter].manyToMany.targetColumnFilter;

            whereConditions.push(`${schema.properties[filter].manyToMany.targetTable}.${targetColumn} = ANY($${values.length + 1}::int[])`);
            values.push(req.body[filter]);
        } else if (schema.properties[filter].type === 'number' && schema.properties[filter].fieldType == 'range') {
            console.log("schema.properties[filter].fieldType");
            console.log(schema.properties[filter].fieldType);
            console.log("req.body.price_min");
            console.log(req.body.price_min);
            console.log("req.body.price_max");
            console.log(req.body.price_max);

            if (req.body.price_min !== undefined) {
                AssertUser(Number(req.body.price_min) > 0, "Price min can't be negative");
                whereConditions.push(`${tableName}.price >= $${values.length + 1}`);
                values.push(req.body.price_min);
            }
            if (req.body.price_max !== undefined) {
                AssertUser(Number(req.body.price_max) > 0, "Price max can't be negative");
                whereConditions.push(`${tableName}.price <= $${values.length + 1}`);
                values.push(req.body.price_max);
            }
        } else if (schema.properties[filter].type === 'integer' && req.body[filter] != undefined) {
            console.log("filter is integer", "tableName", tableName, "filter", filter, "req.body[filter]", req.body[filter]);
            whereConditions.push(`${tableName}.${schema.primaryKey} = $${values.length + 1}`);
            values.push(req.body[filter]);
            console.log("values", values)
        } else if (filter === "user_id" && req.body.email) {
            whereConditions.push(`users.email = $${values.length + 1}`);
            values.push(req.body.email);
        }
    });

    return {whereConditions, values}
}

async function generateReportSQLQuery(inputData, reportFilters, reportName, authenticatedUser) {
    let sqlTemplate = getSQLTemplateFromInterfaceName(reportName, authenticatedUser['settingsRow']['report_limitation_rows']);

    let counter = 1;
    let orderByClauses = [];
    let groupingSelected = false;
    let countExpression = '';
    let queryParams = [];
    let paramIndex = 1; // fix -> da smenq podhoda ? 

    reportFilters.fields.forEach((reportFilter) => {
    	if (inputData[`${reportFilter.key}_grouping_select_value`] !== undefined && inputData[`${reportFilter.key}_grouping_select_value`] != "all") {
            groupingSelected = true;
        }
    });

    reportFilters.fields.forEach((reportFilter) => {
        let reportFilterKey = reportFilter.key;
        if (inputData[reportFilterKey + '_' + 'grouping_select_value'] == "all" && groupingSelected == false) {
            sqlTemplate = sqlTemplate.replace('$' + reportFilterKey + '_grouping_expression' + '$', reportFilter['grouping_expression']);
        } else if (inputData[reportFilterKey + '_' + 'grouping_select_value'] == "all" && groupingSelected == true) { 
            sqlTemplate = sqlTemplate.replace('$' + reportFilterKey + '_grouping_expression' + '$', "'-'");
        } else {
            const timeGroupingValue = inputData[reportFilterKey + '_' + 'grouping_select_value'];
            if (timeGroupingValue && timeGroupingValue != "all") {
                const timeGroupingExpression = `date_trunc('${timeGroupingValue}', ${reportFilter['grouping_expression']})`;
                sqlTemplate = sqlTemplate.replace('$time_grouping_expression$', timeGroupingExpression);
            } else {
                sqlTemplate = sqlTemplate.replace('$' + reportFilterKey + '_grouping_expression' + '$', reportFilter['grouping_expression']);
            }
        }

        // Filter expression logic
        const filterKey = `${reportFilter.key}_filter_expression`;
        if (reportFilter.type === 'timestamp') {
            let beginTimestamp = inputData[`${reportFilter.key}_filter_value_begin`];
            let endTimestamp = inputData[`${reportFilter.key}_filter_value_end`];

            if (beginTimestamp && endTimestamp) { // dopulnitelna validaciq
                let filterExpr = reportFilter.filter_expression
                    .replace('$FILTER_VALUE_BEGIN$', `$${paramIndex}`)
                    .replace('$FILTER_VALUE_END$', `$${paramIndex + 1}`);
                queryParams.push(beginTimestamp, endTimestamp);
                paramIndex += 2;
                sqlTemplate = sqlTemplate.replace(`$${filterKey}$`, filterExpr);
            } else {
                sqlTemplate = sqlTemplate.replace(`$${filterKey}$`, 'TRUE');
            }
        } else if (reportFilter.type === 'range') {
            let minValue = inputData[`${reportFilter.key}_filter_value_min`];
            let maxValue = inputData[`${reportFilter.key}_filter_value_max`];

            console.log("before -> minValue", minValue,"maxValue", maxValue);

            if (minValue === undefined || minValue === '') {
                minValue = 0.01;
            }
            if (maxValue === undefined || maxValue === '') {
                maxValue = 10000000;
            }

            let filterExpr = reportFilter.filter_expression
                    .replace('$FILTER_VALUE_MIN$', `$${paramIndex}`)
                    .replace('$FILTER_VALUE_MAX$', `$${paramIndex + 1}`);
                queryParams.push(minValue, maxValue);
                paramIndex += 2;
                sqlTemplate = sqlTemplate.replace(`$${filterKey}$`, filterExpr);

            console.log("after -> minValue", minValue,"maxValue", maxValue);

        } else {
            const filterValue = inputData[`${reportFilter.key}_filter_value`];
            if (filterValue) {
                const filterExpr = reportFilter.filter_expression.replace('$FILTER_VALUE$', `$${paramIndex}`);
                queryParams.push(filterValue);
                paramIndex += 1;
                sqlTemplate = sqlTemplate.replaceAll(`$${filterKey}$`, filterExpr);
            } else {
                sqlTemplate = sqlTemplate.replaceAll(`$${filterKey}$`, 'TRUE');
            }
        }

        // Order by clause
        const orderBy = inputData[`${reportFilter.key}_order`];
        console.log("orderBy", orderBy);

        if (orderBy) {
            orderByClauses.push(`${counter} ${orderBy.toUpperCase()}`);
            counter++;
        }
    });

    sqlTemplate = sqlTemplate
        .replace('$order_by_clause$', orderByClauses.length > 0 ? orderByClauses.join(', ') : '1 ASC')
        // .replace(/\$[a-z_]+_grouping_expression\$/g, (placeholder) => {
        //     // Default to grouping expressions from the JSON
        //     const matchingField = reportFilters.fields.find((field) => `$${field.key}_grouping_expression$` === placeholder);
        //     return matchingField ? matchingField.grouping_expression : 'NULL';
        // });

    // sqlTemplate = sqlTemplate.replace(/\$\w+\$/g, 'TRUE');

    console.log("Final SQL Query:", sqlTemplate);
    console.log("QueryParams:", queryParams);

    return {sqlTemplate, queryParams};
}

function buildInsertQueries(tableName, itemsArray, foreignKeyField) {
    return itemsArray.map(item => {
        const fields = [foreignKeyField, ...Object.keys(item)];
        const placeholders = fields.map((_, index) => `$${index + 1}`);
        const values = [null, ...Object.values(item)];  // `null` placeholder for foreign key (e.g., order_id)

        console.log("fields");
        console.log(fields);
        console.log("placeholders");
        console.log(placeholders);
        console.log("values");
        console.log(values);

        return {
            query: `INSERT INTO ${tableName} (${fields.join(", ")}) VALUES (${placeholders.join(", ")})`,
            values: values
        };
    });
}

function getSQLTemplateFromInterfaceName(reportName, rowsLimit) {
    AssertDev(
        rowsLimit !== undefined && rowsLimit !== null,
        "rowsLimit parameter is undefined or null"
    );

    AssertDev(
        !isNaN(rowsLimit) && typeof rowsLimit === 'number',
        `rowsLimit must be a number but received ${typeof rowsLimit}: ${rowsLimit}`
    );

    let sqlTemplate;
    if (reportName == "audits") {
        sqlTemplate = `
            SELECT 
                $time_grouping_expression$           AS "Log Inserted At",
                $message_grouping_expression$        AS "Message",
                $exception_type_grouping_expression$ AS "Exception type",
                $audit_type_grouping_expression$ AS "Audit type",
                $user_email_grouping_expression$     AS "User",
                $sub_system_grouping_expression$     AS "Sub system",
                $log_type_grouping_expression$       AS "Log type",
                count(el.id)                         AS "Count",
                count(*) OVER ()                     AS "Total Rows"     
            FROM exception_logs el
            WHERE TRUE
                AND $time_filter_expression$
                AND $message_filter_expression$
                AND $exception_type_filter_expression$
                AND $audit_type_filter_expression$
                AND $user_email_filter_expression$
                AND $sub_system_filter_expression$
                AND $log_type_filter_expression$
            GROUP BY 1, 2, 3, 4, 5, 6, 7
            ORDER BY $order_by_clause$
            LIMIT ${rowsLimit}
        `;
    } else if (reportName == "order") {
        sqlTemplate = `
        SELECT * FROM (
            SELECT 
                $time_grouping_expression$                                                                                                                           AS "Order Inserted At",
                $order_id_grouping_expression$                                                                                                                       AS "Order ID",
                $id_grouping_expression$                                                                                                                             AS "User ID",
                $status_grouping_expression$                                                                                                                         AS "Status",
                $discount_percentage_grouping_expression$                                                                                                            AS "Discount Percentage",
                c.symbol                                                                                                                                             AS "Currency",
                sum(oi.price * oi.quantity)                                                                                                                          AS "Total",
                round(sum(oi.price * oi.quantity * (CAST(oi.vat as numeric) / 100)),2)                                                                               AS "VAT",
                round(sum(oi.price * oi.quantity) + sum(oi.price * oi.quantity * (cast(oi.vat as numeric) / 100)),2)                                                 AS "Total With VAT",
                sum(round(  ((oi.price * oi.quantity) + (oi.price * oi.quantity * (cast(oi.vat as numeric) / 100)))    * (o.discount_percentage / 100.0),2))         AS "Discount Amount",
                sum(round( (oi.price * oi.quantity + (oi.price * oi.quantity * (cast(oi.vat as numeric) / 100))) - (((oi.price * oi.quantity) + 
                (oi.price * oi.quantity * (cast(oi.vat as numeric) / 100)))    * (o.discount_percentage / 100.0)),2))        AS "Price after discount",
                count(oi.order_id)                                                                                                                                   AS "Number of orders items",
                count(*) OVER ()                                                                                                                                     AS "Total Rows" 
            FROM orders o
            JOIN order_items AS oi ON o.order_id = oi.order_id
            JOIN users       AS u  ON o.user_id  = u.id
            JOIN products    AS p  ON oi.product_id = p.id
            JOIN currencies  AS c  ON p.currency_id = c.id 
            WHERE TRUE
                AND $time_filter_expression$
                AND $order_id_filter_expression$
                AND $status_filter_expression$
                AND $discount_percentage_filter_expression$
                AND $id_filter_expression$ 
            GROUP BY GROUPING SETS ( 
                (1, 2, 3, 4, 5, 6),
                ()
            )
        ) sub_quuery

            ORDER BY $order_by_clause$ NULLS FIRST
            LIMIT ${rowsLimit}
        `;
    } else if (reportName == "user_orders") {
        sqlTemplate = `
            SELECT * FROM (
                WITH order_metrics AS (
                SELECT 
                    o.user_id,
                    c.symbol AS currency,
                    COUNT(DISTINCT CASE WHEN o.order_date >= NOW() - INTERVAL '1 day' THEN o.order_id END) AS orders_last_day,
                    ROUND(SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '1 day' 
                        THEN (oi.price * oi.quantity * (1 + CAST(oi.vat AS NUMERIC) / 100)) * (1 - COALESCE(o.discount_percentage, 0) / 100.0) 
                        END), 2) AS vat_total_price_last_day,
                    
                    COUNT(DISTINCT CASE WHEN o.order_date >= NOW() - INTERVAL '1 week' THEN o.order_id END) AS orders_last_week,
                    ROUND(SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '1 week' 
                        THEN (oi.price * oi.quantity * (1 + CAST(oi.vat AS NUMERIC) / 100)) * (1 - COALESCE(o.discount_percentage, 0) / 100.0) 
                        END), 2) AS vat_total_price_last_week,
                    
                    COUNT(DISTINCT CASE WHEN o.order_date >= NOW() - INTERVAL '1 month' THEN o.order_id END) AS orders_last_month,
                    ROUND(SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '1 month' 
                        THEN (oi.price * oi.quantity * (1 + CAST(oi.vat AS NUMERIC) / 100)) * (1 - COALESCE(o.discount_percentage, 0) / 100.0) 
                        END), 2) AS vat_total_price_last_month,
                    
                    COUNT(DISTINCT CASE WHEN o.order_date >= NOW() - INTERVAL '1 year' THEN o.order_id END) AS orders_last_year,
                    ROUND(SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '1 year' 
                        THEN (oi.price * oi.quantity * (1 + CAST(oi.vat AS NUMERIC) / 100)) * (1 - COALESCE(o.discount_percentage, 0) / 100.0) 
                        END), 2) AS vat_total_price_last_year,
                    
                    COUNT(*) OVER () AS total_count
                FROM 
                    orders o
                JOIN 
                    order_items oi ON o.order_id = oi.order_id
                JOIN 
                    products p ON oi.product_id = p.id
                JOIN 
                    currencies c ON p.currency_id = c.id
                JOIN 
                    users u ON o.user_id = u.id
                WHERE TRUE
                    AND $email_filter_expression$
                    AND $id_filter_expression$
                GROUP BY 1, 2
            )
            SELECT 
                u.email AS "User Email",
                u.id AS "User ID",

                SUM(om.orders_last_day) AS "Orders Last Day",
                SUM(om.vat_total_price_last_day) AS "VAT Total Price Last Day",
                om.currency AS "Currency Last Day",
                
                SUM(om.orders_last_week) AS "Orders Last Week",
                SUM(om.vat_total_price_last_week) AS "VAT Total Price Last Week",
                om.currency AS "Currency Last Week",
                
                SUM(om.orders_last_month) AS "Orders Last Month", 
                SUM(om.vat_total_price_last_month) AS "VAT Total Price Last Month",
                om.currency AS "Currency Last Month",
                
                SUM(om.orders_last_year) AS "Orders Last Year",
                SUM(om.vat_total_price_last_year) AS "VAT Total Price Last Year", 
                om.currency AS "Currency Last Year",
                
                SUM(om.total_count) AS "Over Total Count"
            FROM 
                users u
            JOIN 
                order_metrics om ON u.id = om.user_id
            WHERE TRUE
                AND $email_filter_expression$
                AND $id_filter_expression$
                AND $price_filter_expression$
            GROUP BY GROUPING SETS ( 
                    (1, 2, 5),
                    ()
                )
        ) sub_quuery

            ORDER BY $order_by_clause$ NULLS FIRST
            ${rowsLimit};
        `
    } else if (reportName === "target_group") {
        sqlTemplate = `
            SELECT 
                u.first_name AS "User first name", 
                u.last_name  AS "User last name", 
                u.email      AS "User email", 
                u.birth_date AS "User birth date"
            FROM target_groups tg
            JOIN user_target_groups utg ON tg.id       = utg.target_group_id 
            JOIN users              u   ON utg.user_id = u.id 
            WHERE TRUE
                AND $target_group_filter_expression$
            ORDER BY $order_by_clause$
            LIMIT ${rowsLimit}
        `
    }

    // AND $price_filter_expression$
    return sqlTemplate;
}

async function* fetchReportData(client, sql, params) {
    const cursor = client.query(new Cursor(sql, params));
    try {
        while (true) {
            console.log("Fetched rows fetchReportData form db");
            const rows = await new Promise((resolve, reject) => {
                cursor.read(100, (err, rows) => {
                    if (err) return reject(err);
                    resolve(rows);
                });
            });

            if (rows.length === 0) break;
            yield rows;
        }
    } finally {
        cursor.close();
    }
}

async function getStaffPermissions(client, staffUsername) {
    const permissions = await client.query(`
                    SELECT 
                        * 
                    FROM staff 
                        JOIN staff_roles      ON staff.id                       = staff_roles.staff_id 
                        JOIN roles            ON staff_roles.role_id            = roles.role_id 
                        JOIN role_permissions ON roles.role_id                  = role_permissions.role_id 
                        JOIN permissions      ON role_permissions.permission_id = permissions.permission_id 
                    WHERE staff.username = $1
                      `, [staffUsername]);

    return permissions.rows;
}

async function checkStaffPermissions(client, staffUsername, interfaceI, permission) {
    const mappedInterface = INTERFACE_MAPPING[interfaceI] || interfaceI;
    AssertDev(VALID_INTERFACES.includes(mappedInterface),`Invalid interface: ${mappedInterface}`);

    const permissions = await getStaffPermissions(client, staffUsername);
    const allowedPermissions = permissions
        .filter(p => p.interface === mappedInterface)
        .map(p => p.permission_name);

    AssertUser(allowedPermissions.includes(permission), `Permission denied: Missing required permission '${permission}'`)
}

async function getTemplatesData(client) {
    const emailTemplates = await client.query(`
                                    SELECT
                                        *
                                    FROM email_template
                                    `)

    const settings = await client.query(`
                                    SELECT
                                        *
                                    FROM settings
                                    `)

    return {templates: emailTemplates.rows, settings: settings.rows}
}

async function getTemplateById(client, id) {
    const emailTemplates = await client.query(`
                                    SELECT
                                        *
                                    FROM email_template
                                    WHERE id = $1
                                    `, [id])

    AssertDev(emailTemplates.rows.length == 1, "Expect one on fetch email by id");

    return emailTemplates;
}

async function mapEmailData(client, email, subject, bodyData, informationToMap, orderObj) {
    const settingsRow = await client.query(`SELECT * FROM settings`);
    const settings = settingsRow.rows[0];

    AssertDev(settingsRow.rows.length == 1, "Expect one settings");

    const emailMapper = new EmailDataMapper(settings);

    switch (subject) {
        case "Verification Email":
            return emailMapper.mapVerificationEmail(email, informationToMap, bodyData.body);
        case "Purchase Email":
        case "Payment Email":
            return emailMapper.mapPurchaseEmail(email, informationToMap, bodyData.body, orderObj || {});
        default:
            AssertDev(false, "No more options");
    }
}

module.exports = {
	login,
	parseMultipartFormData,
	mapSchemaPropertiesToDBRelations,
	makeTableJoins,
	makeTableFilters,
	generateReportSQLQuery,
    fetchReportData,
    parseMultipartFormDataGenerator,
    getStaffPermissions,
    checkStaffPermissions,
    getTemplatesData,
    getTemplateById,
    mapEmailData,
}