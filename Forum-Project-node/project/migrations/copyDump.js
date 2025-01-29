const fs = require('fs');
const path = require('path');

const dumpFilePath = '/var/lib/postgresql/28-01-2025.sql';
const migrationFilePath = path.join(__dirname, '../files/2025-01-28-00-initial-migration.sql');

fs.writeFileSync(
    migrationFilePath,
    `-- Migration: Initial database setup from pg_dump
-- Created: ${new Date().toISOString()}

`
);

const readStream = fs.createReadStream(dumpFilePath);
const writeStream = fs.createWriteStream(migrationFilePath, { flags: 'a' });

readStream.pipe(writeStream);

readStream.on('error', (error) => {
    console.error('Error reading dump file:', error);
});

writeStream.on('error', (error) => {
    console.error('Error writing migration file:', error);
});

writeStream.on('finish', () => {
    console.log('Successfully copied pg_dump to initial migration file');
});