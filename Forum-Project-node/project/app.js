const express = require('express');
const path = require('path');
const pool = require('./db');
const mainRoutes = require('./main'); 

const app = express();

// Set EJS as the template engine
app.set('view engine', 'ejs');

// Set the directory where your template files are located
app.set('views', path.join(__dirname, 'views'));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use(mainRoutes);

app.use((err, req, res, next) => {
    console.error('Global error handler:', err.stack);
    res.status(500).send('Something broke!+++');
});

module.exports = app;