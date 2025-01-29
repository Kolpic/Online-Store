const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');
const config = require('../config');
// const dotenv = require('dotenv');
const readline = require('readline');
const { Transform } = require('stream');

// dotenv.config();

const pool = new Pool({
    user: config.user,
    host: config.host,
    database: config.database,
    password: config.password,
    port: 5432,
});

const migrationsDir = path.join(__dirname, '../files');

async function runMigrations() {
    const client = await pool.connect();
    try {
        await client.query('BEGIN');
        await client.query(`
            CREATE TABLE IF NOT EXISTS migrations (
                id SERIAL PRIMARY KEY,
                file_name TEXT NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        `);

        const appliedMigrations = await client.query('SELECT file_name FROM migrations');
        const appliedFiles = new Set(appliedMigrations.rows.map(row => row.file_name));

        const migrationFiles = (await fs.promises.readdir(migrationsDir)).filter(file => file.endsWith('.sql'));

        for (const file of migrationFiles) {
            if (!appliedFiles.has(file)) {
                const filePath = path.join(migrationsDir, file);
                await executeMigrationFileInChunks(client, filePath);
                await client.query('INSERT INTO migrations (file_name) VALUES ($1)', [file]);
                console.log(`Applied migration: ${file}`);
            }
        }

        await client.query('COMMIT');
    } catch (error) {
        await client.query('ROLLBACK');
        console.error('Error running migrations:', error);
    } finally {
        client.release();
    }
}

async function executeMigrationFileInChunks(client, filePath) {
    const readStream = fs.createReadStream(filePath, { encoding: 'utf8' });
    const rl = readline.createInterface({
        input: readStream,
        crlfDelay: Infinity
    });

    let sqlChunk = '';

    for await (const line of rl) {
        sqlChunk += line + '\n';
        if (line.trim().endsWith(';')) {
            await client.query(sqlChunk);
            sqlChunk = '';
        }
    }

    if (sqlChunk.trim()) {
        await client.query(sqlChunk);
    }
}

runMigrations().catch(error => console.error('Error running migrations:', error));