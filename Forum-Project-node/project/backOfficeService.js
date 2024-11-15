const { AssertUser, AssertDev } = require('./exceptions');
const errors = require('./error_codes');
const bcrypt = require('bcryptjs');
const fs = require('fs');
const path = require('path');
const { pipeline } = require('stream');
const { promisify } = require('util');
const { v4: uuidv4 } = require('uuid');

async function login(username, password, client) {
	AssertDev(username != undefined, "username is undefined");
	AssertDev(password != undefined, "password is undefined");

	let user = await client.query(`SELECT * FROM staff WHERE username = $1 AND password = $2`, [username, password]);
	let userRow = user.rows;

	AssertDev(userRow.length == 1, "User row can't return more than one user");

	return userRow[0].username;
}

async function parseMultipartFormData(req, client) {
    AssertUser(req.headers['content-type'].startsWith('multipart/form-data'), 'Invalid inputs: Expected multipart/form-data', errors.NOT_FOUND_MULTYPART_FROM_DATA);

    const boundary = getBoundary(req.headers['content-type']);
    AssertUser(boundary, 'Invalid inputs: Boundary not found in the Content-Type header', errors.NOT_FOUND_BOUNDARY);

    const formData = {};
    const imageIds = [];
    let buffer = Buffer.alloc(0);

    for await (const chunk of req) {
        buffer = Buffer.concat([buffer, chunk]);
    }

    try {
        const parts = buffer.toString().split(`--${boundary}`);

        for (const part of parts) {
            if (part === '--\r\n' || part === '--\r\n--') continue;

            // Separate headers from content
            const [headers, content] = part.split('\r\n\r\n');
            if (!headers || !content) continue;

            const headerLines = headers.split('\r\n');
            const contentDisposition = headerLines.find(line => line.startsWith('Content-Disposition'));
            const contentType = headerLines.find(line => line.startsWith('Content-Type'));

            const nameMatch = /name="(.+?)"/.exec(contentDisposition);
            const filenameMatch = /filename="(.+?)"/.exec(contentDisposition);

            if (filenameMatch) {
                console.log("File contentType:", contentType);

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

                const binaryContent = Buffer.from(content, 'binary').slice(0, -2);
                await fs.promises.writeFile(filePath, binaryContent);

                await client.query(`UPDATE images SET status = 'completed' WHERE id = $1`, [imageId]);
            } else {
                const fieldName = nameMatch[1];
                const fieldValue = content.trim();

                if (fieldName === 'categories') {
                    formData.categories = formData.categories || [];
                    formData.categories.push(fieldValue);
                } else {
                    formData[fieldName] = fieldValue;
                }
            }
        }

        return { formData, imageIds};
    } catch (error) {
        throw(error);
    }
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

async function makeTableJoins(schema) {
	let selectFields = [];
    let joins = [];
    let groupByFields = [];

    let tableName = schema.title;

    for (const [field, details] of Object.entries(schema.properties)) {
        console.log("field");
        console.log(field);
        console.log("details");
        console.log(details);

        if (details.computed) {
            if (field === "total") {
                selectFields.push("SUM(order_items.price * order_items.quantity) AS Total");
            } else if (field === "vat") {
                selectFields.push("ROUND(SUM(order_items.price * order_items.quantity * (CAST(order_items.vat AS numeric) / 100)), 2) AS Vat");
            } else if (field === "total_with_vat") {
                selectFields.push(
                    "ROUND(SUM(order_items.price * order_items.quantity) + " +
                    "SUM(order_items.price * order_items.quantity * (CAST(order_items.vat AS numeric) / 100)), 2) AS Total_With_Vat"
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

	        joins.push(`JOIN ${joinTable} ON ${tableName}.id = ${joinTable}.${joinColumnOnePK}`);
	        joins.push(`JOIN ${targetTable} ON ${joinTable}.${joinColumnTwoPK} = ${targetTable}.id`);

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
                    selectFields.push(`array_agg(DISTINCT(${details.foreignKey.columnsToShowOnEdit})) AS ${field}`);
                } else {
                    joins.push(`JOIN ${joinTable} ON ${currentTableToJoin} = ${joinTable}.${joinColumn}`);
	                selectFields.push(`array_agg(DISTINCT(${joinTable}.${joinColumnToDisplay})) AS ${field}`);
                }
	        } else {
	            console.log("Array.isArray(details.type) ELSEEE");

	             const joinColumnToDisplay = details.foreignKey.column;
	             joins.push(`JOIN ${joinTable} ON ${tableName}.${field} = ${joinTable}.${joinColumn}`);
	             selectFields.push(`${joinTable}.${joinColumnToDisplay} AS ${joinColumnToDisplay}`);

	             groupByFields.push(`${joinTable}.${joinColumnToDisplay}`);
	        }
            console.log("-----------------------------");
	        
	        // joins.push(`JOIN ${joinTable} ON ${tableName}.${field} = ${joinTable}.${joinColumn}`);

	        // selectFields.push(`${joinTable}.${joinColumnToDisplay} AS ${joinColumnToDisplay}`); 

        } else {
            // Regular field, add to selectFields as is
            selectFields.push(`${tableName}.${field}`);
            groupByFields.push(`${tableName}.${field}`);
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

        // if (req.body[filter] === undefined) { return; }

        if (schema.properties[filter].format === 'date') {
            const fromDate = req.body[`${filter}_from`];
            const toDate = req.body[`${filter}_to`];

            if (fromDate) {
                whereConditions.push(`${tableName}.${filter} >= $${values.length + 1}`);
                values.push(fromDate);
            }
            if (toDate) {
                whereConditions.push(`${tableName}.${filter} <= $${values.length + 1}`);
                values.push(toDate);
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
                whereConditions.push(`${tableName}.price >= $${values.length + 1}`);
                values.push(req.body.price_min);
            }
            if (req.body.price_max !== undefined) {
                whereConditions.push(`${tableName}.price <= $${values.length + 1}`);
                values.push(req.body.price_max);
            }
        } else if (schema.properties[filter].type === 'integer' && req.body[filter] != undefined) {
            console.log("filter is integer");
            whereConditions.push(`${tableName}.${filter} = $${values.length + 1}`);
            values.push(req.body[filter]);
        } else if (filter === "user_id" && req.body.email) {
            whereConditions.push(`users.email = $${values.length + 1}`);
            values.push(req.body.email);
        }
    });

    return {whereConditions, values}
}

async function generateReportSQLQuery(inputData, reportFilters) {
    let sqlTemplate = `
        SELECT 
            $select_expressions$
        FROM exception_logs el
        WHERE TRUE
            AND $time_filter_expression$
            AND $message_filter_expression$
            AND $exception_type_filter_expression$
            AND $user_email_filter_expression$
            AND $sub_system_filter_expression$
            AND $log_type_filter_expression$
        $group_by_clause$
        ORDER BY $order_by_clause$
        LIMIT 20
    `;

    let selectExpressions = [];
    let groupByExpressions = [];
    let orderByClauses = [];
    let groupingSelected = false;
    let countExpression = '';
    let queryParams = [];
    let paramIndex = 1;

    reportFilters.fields.forEach((reportFilter) => {
    	if (inputData[`${reportFilter.key}_grouping_select_value`] !== undefined && inputData[`${reportFilter.key}_grouping_select_value`] != "") {
            groupingSelected = true;
        }
    });

    reportFilters.fields.forEach((reportFilter) => {
        const groupingKey = `${reportFilter.key}_grouping_select_value`;
        const groupingValue = inputData[groupingKey];

        if (groupingValue !== undefined && groupingValue != "") {
        	if (reportFilter.type === 'timestamp' && groupingValue) {
                // Apply `date_trunc` based on grouping value (day, month, year)
                const dateTruncExpression = `date_trunc('${groupingValue}', ${reportFilter.grouping_expression})`;
                selectExpressions.push(`${dateTruncExpression} AS "${reportFilter.key}"`);
                groupByExpressions.push(dateTruncExpression);
            } else {
                selectExpressions.push(`${reportFilter.grouping_expression} AS "${reportFilter.key}"`);
                groupByExpressions.push(reportFilter.grouping_expression);
            }
        } else if (!groupingSelected) {
            // For non-grouped fields, include them directly in SELECT clause
            selectExpressions.push(`${reportFilter.grouping_expression} AS "${reportFilter.key}"`);
        } else {
            // Placeholder for grouped query with `-`
            selectExpressions.push(`'-' AS "${reportFilter.key}"`);
        }

        // Filter expression logic
        const filterKey = `${reportFilter.key}_filter_expression`;
        if (reportFilter.type === 'timestamp') {
            let beginTimestamp = inputData[`${reportFilter.key}_filter_value_begin`];
            let endTimestamp = inputData[`${reportFilter.key}_filter_value_end`];

            if (beginTimestamp && endTimestamp) {
                let filterExpr = reportFilter.filter_expression
                    .replace('$FILTER_VALUE_BEGIN$', `$${paramIndex}`)
                    .replace('$FILTER_VALUE_END$', `$${paramIndex + 1}`);
                queryParams.push(beginTimestamp, endTimestamp);
                paramIndex += 2;
                sqlTemplate = sqlTemplate.replace(`$${filterKey}$`, filterExpr);
            } else {
                sqlTemplate = sqlTemplate.replace(`$${filterKey}$`, 'TRUE');
            }
        } else {
            const filterValue = inputData[`${reportFilter.key}_filter_value`];
            if (filterValue) {
                const filterExpr = reportFilter.filter_expression.replace('$FILTER_VALUE$', `$${paramIndex}`);
                queryParams.push(filterValue);
                paramIndex += 1;
                sqlTemplate = sqlTemplate.replace(`$${filterKey}$`, filterExpr);
            } else {
                sqlTemplate = sqlTemplate.replace(`$${filterKey}$`, 'TRUE');
            }
        }

        // Order by clause
        const orderBy = inputData[`${reportFilter.key}_order`];
        if (orderBy) {
            orderByClauses.push(`${reportFilter.grouping_expression} ${orderBy.toUpperCase()}`);
        }
    });

    // COUNT if we have group by
    if (groupingSelected) {
        countExpression = `, COUNT(*) AS "Count"`;
    }

    sqlTemplate = sqlTemplate
        .replace('$select_expressions$', selectExpressions.join(', ') + countExpression)
        .replace('$group_by_clause$', groupingSelected ? `GROUP BY ${groupByExpressions.join(', ')}` : '')
        .replace('$order_by_clause$', orderByClauses.length > 0 ? orderByClauses.join(', ') : '1 DESC');

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

module.exports = {
	login,
	parseMultipartFormData,
	mapSchemaPropertiesToDBRelations,
	makeTableJoins,
	makeTableFilters,
	generateReportSQLQuery,
}