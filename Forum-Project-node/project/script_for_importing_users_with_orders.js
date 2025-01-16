const config = require('./config');
const { logEvent, logException } = require('./logger');
const { AssertDev, DevException, TemporaryError, TemporaryException } = require('./exceptions');

const { Pool } = require('pg');
const { faker } = require('@faker-js/faker');

const pool = new Pool({
    user: config.user,
    host: config.host,
    database: config.test_qa_database,
    password: config.password,
    port: 5432,
});

const DAILY_USER_LIMIT = 1000;
const DAILY_ORDER_LIMIT = 50000;
const HOURLY_USER_LIMIT = Math.ceil(DAILY_USER_LIMIT / 24);
const HOURLY_ORDER_LIMIT = Math.ceil(DAILY_ORDER_LIMIT / 24);
const AUDIT_EXCEPTION_SUB_SYSTEM_NAME = "script_for_importing_users_with_orders";
const AUDIT_EXCEPTION_USER_NAME = "CronJob";
const AUDIT_LOG_EXCEPTION_TYPE_EMPTY_STRING = "";
const AUDIT_LOG_MESSAGE_LIMIT_REACHED = "Daily import limits reached. Skipping import.";
const AUDIT_LOG_TYPE_EVENT = "event";

async function getDailyStats(client) {
  const today = new Date().toISOString().split('T')[0];
  
  await client.query(`
    INSERT INTO user_orders_script_import (date, users_imported, orders_imported)
    VALUES ($1, 0, 0)
    ON CONFLICT (date) DO NOTHING
  `, [today]);
  
  const result = await client.query(`
    SELECT users_imported, orders_imported
    FROM user_orders_script_import
    WHERE date = $1
  `, [today]);
  
  return result.rows[0];
}

function generateUser() {
  const firstName = faker.person.firstName().replace(/'/g, " ");
  const lastName = faker.person.lastName().replace(/'/g, " ");
  
  return {
    first_name: firstName,
    last_name: lastName,
    email: faker.internet.email({ firstName, lastName }),
    password: faker.internet.password(),
    verification_status: true,
    verification_code: faker.string.alphanumeric(8),
    address: faker.location.streetAddress().replace(/'/g, " "),
    gender: faker.person.sex(),
    phone: faker.phone.number().replace(/[^\d\s-+()x.]/g, " "),
    country_code_id: faker.number.int({ min: 1, max: 10 })
  };
}

async function insertUsers(count, client) {
  const users = Array(count).fill().map(generateUser);
  const values = users.map(user => `(
    '${user.first_name}',
    '${user.last_name}',
    '${user.email}',
    '${user.password}',
    ${user.verification_status},
    '${user.verification_code}',
    '${user.address}',
    '${user.gender}',
    '${user.phone}',
    ${user.country_code_id}
  )`).join(',');
  
  const query = `
    INSERT INTO users (
      first_name, last_name, email, password,
      verification_status, verification_code,
      address, gender, phone, country_code_id
    )
    VALUES ${values}
    RETURNING id;
  `;
  
  const result = await client.query(query);
  return result.rows.map(row => row.id);
}

async function insertOrders(userIds, count, client) {
  for (let i = 0; i < count; i++) {
    const userId = userIds[Math.floor(Math.random() * userIds.length)];
    const orderDate = new Date();
    const status = 'Paid';
    const discountPercentage = faker.number.int({ min: 0, max: 30});

    const orderResult = await client.query(`
      INSERT INTO orders (user_id, status, order_date, discount_percentage)
      VALUES ($1, $2, $3, $4)
      RETURNING order_id
    `, [userId, status, orderDate, discountPercentage]);
    
    const orderId = orderResult.rows[0].order_id;

    // Insert 1-3 order items
    const itemCount = faker.number.int({ min: 1, max: 3 });
    for (let j = 0; j < itemCount; j++) {
      await client.query(`
        INSERT INTO order_items (order_id, product_id, quantity, price, vat)
        VALUES ($1, $2, $3, $4, $5)
      `, [
        orderId,
        faker.number.int({ min: 263698, max: 263722 }), 
        faker.number.int({ min: 1, max: 5 }),
        faker.number.int({ min: 10, max: 1000 }),
        '20'
      ]);
    }
  }
}

async function updateStats(usersCount, ordersCount, client) {
  const today = new Date().toISOString().split('T')[0];
  
  await client.query(`
    UPDATE user_orders_script_import
    SET users_imported = users_imported + $1, orders_imported = orders_imported + $2
    WHERE date = $3
  `, [usersCount, ordersCount, today]);
}

async function runImport() {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const stats = await getDailyStats(client);
    
    if (stats.users_imported >= DAILY_USER_LIMIT && 
        stats.orders_imported >= DAILY_ORDER_LIMIT) {
      console.log('Daily import limits reached. Skipping import.');
      await logEvent(AUDIT_LOG_EXCEPTION_TYPE_EMPTY_STRING, AUDIT_LOG_EXCEPTION_TYPE_EMPTY_STRING, AUDIT_LOG_MESSAGE_LIMIT_REACHED, AUDIT_EXCEPTION_SUB_SYSTEM_NAME, AUDIT_LOG_TYPE_EVENT);
      return;
    }
    
    const remainingUsers = Math.min(
      HOURLY_USER_LIMIT,
      DAILY_USER_LIMIT - stats.users_imported
    );
    const remainingOrders = Math.min(
      HOURLY_ORDER_LIMIT,
      DAILY_ORDER_LIMIT - stats.orders_imported
    );
    
    if (remainingUsers > 0) {
      const userIds = await insertUsers(remainingUsers, client);
      if (remainingOrders > 0) {
        await insertOrders(userIds, remainingOrders, client);
      }
      await updateStats(remainingUsers, remainingOrders, client);
      
      let successfulLogMessage = `Imported ${remainingUsers} users and ${remainingOrders} orders`;

      await logEvent(AUDIT_EXCEPTION_USER_NAME, AUDIT_LOG_EXCEPTION_TYPE_EMPTY_STRING, successfulLogMessage, AUDIT_EXCEPTION_SUB_SYSTEM_NAME, AUDIT_LOG_TYPE_EVENT);
    }
    
    await client.query('COMMIT');

  } catch (error) {
    await client.query('ROLLBACK');

    console.error('Import failed:', "error -> ", error, "error.message -> ", error.message, "error.name -> ", error.name);

    await logException(AUDIT_LOG_EXCEPTION_TYPE_EMPTY_STRING, error.name, error.message, AUDIT_EXCEPTION_SUB_SYSTEM_NAME);

  } finally {
    client.release();
    await pool.end();
  }
}

runImport();