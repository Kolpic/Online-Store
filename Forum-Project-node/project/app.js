const express = require('express');
const path = require('path');
const pool = require('./db');
const { router } = require('./main'); 

const app = express();

const PORT = process.env.PORT || 5002;
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});

// Serve static files
app.use(express.static(path.join(__dirname, 'views')));

const myLogger = function (req, res, next) {
  console.log('LOGGED')
  next()
}
app.use(myLogger)

app.use(express.static(path.join(__dirname, '/schemas')));
app.use(express.static(path.join(__dirname, '/views')));
app.use(express.static(path.join(__dirname, '/images')));

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