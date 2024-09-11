const express = require('express');
const path = require('path');
const pool = require('./db');
const { router } = require('./main'); 

const app = express();

// Serve static files
app.use(express.static(path.join(__dirname, 'views')));

const myLogger = function (req, res, next) {
  console.log('LOGGED')
  next()
}
app.use(myLogger)

app.use(express.static(path.join(__dirname, '/views')));

// Middleware for parsing JSON and urlencoded data
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Use the main routes for handling API requests
app.use(router);

// Global error handler
app.use((err, req, res, next) => {
    console.error('Global error handler:', err.stack);
    res.status(500).send('Something broke!+++');
});

module.exports = app;