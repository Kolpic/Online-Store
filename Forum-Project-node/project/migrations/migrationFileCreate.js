const fs = require('fs');
const path = require('path');

const taskName = process.argv[2];

if (!taskName) {
    console.error('Please provide a task name: node create-migration.js <task-name>');
    process.exit(1);
}

const cleanTaskName = taskName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

const migrationsDir = path.join(__dirname, '../files');

if (!fs.existsSync(migrationsDir)) {
    fs.mkdirSync(migrationsDir, { recursive: true });
}

const date = new Date().toISOString().split('T')[0];
let counter = 0;
let fileName;

do {
    fileName = `${date}-${String(counter).padStart(2, '0')}-${cleanTaskName}.sql`;
    counter++;
} while (fs.existsSync(path.join(migrationsDir, fileName)));

fs.writeFileSync(
    path.join(migrationsDir, fileName),
    `-- Migration: ${taskName}\n-- Created: ${new Date().toISOString()}\n\n`
);

console.log(`Created migration file: ${fileName}`);