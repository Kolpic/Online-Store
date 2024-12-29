const { Pool } = require('pg');
const config = require('./config');

const pool = new Pool({
    user: config.user,
    host: config.host,
    database: config.database_home_office,
    password: config.password,
    port: 5432,
});

console.log("Pool initialized in db.js:");

module.exports = pool;