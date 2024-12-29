const express = require('express');
const path = require('path');
const pool = require('./db');
const { router } = require('./main');
const backOfficeRouter = require('./back_office');
const favicon = require('serve-favicon');

const app = express();
const backOfficeApp = express();

const PORT_FRONT = process.env.PORT || 5002;
const PORT_BACK = process.env.BACKOFFICE_PORT || 5003;

app.listen(PORT_FRONT, () => {
    console.log(`Server is running on port ${PORT_FRONT}`);
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
//app.use(favicon(path.join(__dirname, 'images', 'favicon-32x32.png')));

// Middleware for parsing JSON and urlencoded data
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Use the main routes for handling API requests
app.use(router);

backOfficeApp.listen(PORT_BACK, () => {
    console.log(`Back-office server is running on port ${PORT_BACK}`);
});

backOfficeApp.use(express.static(path.join(__dirname, '/schemas')));
backOfficeApp.use(express.static(path.join(__dirname, '/views_backoffice')));
backOfficeApp.use(express.static(path.join(__dirname, '/images')));
//backOfficeApp.use(favicon(path.join(__dirname, 'images', 'favicon-32x32.png')));

// Middleware for parsing JSON and urlencoded data
backOfficeApp.use(express.json());
backOfficeApp.use(express.urlencoded({ extended: true }));

backOfficeApp.use(backOfficeRouter);

// Global error handler
app.use((err, req, res, next) => {
    console.error('Global error handler:', err.stack);
    res.status(500).send('Something broke!+++');
});

backOfficeApp.use((err, req, res, next) => {
    console.error('Back-office error handler:', err.stack);
    res.status(500).send('Something broke in the back-office!++++');
});

module.exports = {app, backOfficeApp};