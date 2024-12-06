const express = require('express');
const request = require('supertest'); // for making HTTP requests to the express app
const crypto = require('crypto');
const { router } = require('../../main');
const front_office = require('../../front_office');
const { WrongUserInputException } = require('../../exceptions');
const errors = require('../../error_codes');
const { app, backOfficeApp } = require('../../app');
const pool = require('../../db');
const cookie = require('cookie');

// jest.mock('../../front_office');

describe('GET /registration test', () => {
    let app;

    beforeAll(() => {
        app = express();
        app.use(express.json());
        app.use(router);
    });

    it('should return registration data with captcha', async () => {
        // Mock data for the test
        const mockPreparedData = {
            first_captcha_number: 12,
            second_captcha_number: 34,
            captcha_id: 1,
            country_codes: [
                { id: 1, name: 'Country1', code: 'C1' },
                { id: 2, name: 'Country2', code: 'C2' }
            ]
        };

        // Mock the `prepareRegistrationData` method
        front_office.prepareRegistrationData = jest.fn().mockResolvedValue(mockPreparedData);

        const response = await request(app)
            .get('/registration')
            .expect('Content-Type', /json/)
            .expect(200);

        expect(response.body).toEqual({
            country_codes: mockPreparedData.country_codes,
            captcha: {
                first: mockPreparedData.first_captcha_number,
                second: mockPreparedData.second_captcha_number
            },
            captcha_id: mockPreparedData.captcha_id
        });
    });

    it('should throw when we dont enter valid url', async () => {
      const response = await request(app)
            .get('/registration-wrong-url')
            .expect('Content-Type', /json/)
            .expect(400);
    });
});

describe('POST /registration', () => {
  it('should register a user successfully without polluting the database', async () => {
    const client = await pool.connect();

    await client.query(`
        INSERT INTO captcha (first_number, second_number, result) 
        VALUES (10, 2, 12)
        RETURNING id
    `);

    const captchaResult = await client.query(`SELECT id FROM captcha WHERE result = 12`);
    const captcha_id = captchaResult.rows[0].id;

    let insertedCaptcha = await client.query(`SELECT * from captcha where id = ${captcha_id}`);

    const requestData = {
        first_name: 'Galin',
        last_name: 'Petrov',
        email: 'galin@example.com',
        password: '123456789',
        confirm_password: '123456789',
        address: 'Georgi Kirkov 56',
        country_code: '+359',
        phone: '894703986',
        gender: 'male',
        captcha: '12',
        captcha_id: captcha_id,
    };

    const response = await request(app)
        .post('/registration')
        .send(requestData)
        .expect(201);

    expect(response.body).toEqual({
        success: true,
        message: "User registered successfully. Please verify your email to complete the registration.",
        email: requestData.email,
    });

    const result = await client.query('SELECT * FROM users WHERE email = $1', [requestData.email]);
    expect(result.rows.length).toBe(1);
    await client.query(`DELETE FROM users WHERE email = $1`, [requestData.email]);
    client.release();
  });
});

describe('POST /registration test should return error', () => {
    it('should handle errors from registration method', async () => {
        const requestData = {
            first_name: 'Ga', // Invalid first name with less than 3 characters
            last_name: 'Petrov',
            email: 'galin@example.com',
            password: '123456789',
            confirm_password: '123456789',
            address: 'Georgi Kirkov 56',
            country_code: '+359',
            phone: '894703986',
            gender: 'male',
            captcha: '12',
            captcha_id: 1,
        };

        const response = await request(app)
            .post('/registration')
            .send(requestData)
            .expect('Content-Type', /json/)
            .expect(400);

        expect(response.body).toEqual({
            error_message: "First name must be between 3 and 50 characters",
            error_code: errors.NAME_LENGTH_ERROR_CODE,
        });
    });
});

describe('orders CRUD', () => {
    let userEmail = 'galin@example.com';
    let staffUsername = 'Kolpic';

    it('should register a user successfully without polluting the database', async () => {
        const client = await pool.connect();

        await client.query(`
            INSERT INTO captcha (first_number, second_number, result) 
            VALUES (10, 2, 12)
            RETURNING id
        `);

        const captchaResult = await client.query(`SELECT id FROM captcha WHERE result = 12`);
        const captcha_id = captchaResult.rows[0].id;

        let insertedCaptcha = await client.query(`SELECT * from captcha where id = ${captcha_id}`);

        const requestData = {
            first_name: 'Galin',
            last_name: 'Petrov',
            email: userEmail,
            password: '123456789',
            confirm_password: '123456789',
            address: 'Georgi Kirkov 56',
            country_code: '+359',
            phone: '894703986',
            gender: 'male',
            captcha: '12',
            captcha_id: captcha_id,
        };

        const response = await request(app)
            .post('/registration')
            .send(requestData)
            .expect(201);

        expect(response.body).toEqual({
            success: true,
            message: "User registered successfully. Please verify your email to complete the registration.",
            email: requestData.email,
        });

        const result = await client.query('SELECT * FROM users WHERE email = $1', [requestData.email]);
        expect(result.rows.length).toBe(1);
        client.release();
  });

    it('should login user successfully', async () => {
        const client = await pool.connect();

        const requestData = {
            username: staffUsername,
            password: '123456789'
        };

        const response = await request(backOfficeApp)
            .post('/login')
            .send(requestData)
            .expect(200);

        console.log("Login response headers:", response.headers);
        expect(response.headers['set-cookie']).toBeDefined();

        const sessionCookie = response.headers['set-cookie'].find(cookie => cookie.startsWith('session_id='));
        expect(sessionCookie).toBeDefined();

        const sessionId = sessionCookie.split(';')[0].split('=')[1]; // Extract session_id value
        console.log("Extracted session_id:", sessionId);

        expect(sessionId).toBeTruthy();

        const result = await client.query('SELECT * FROM staff WHERE username = $1', [staffUsername]);

        console.log("result");
        console.log(result.rows);

        expect(result.rows.length).toBe(1);
        client.release();
  });

    it('should create an order successfully', async () => {
        const client = await pool.connect();
        let userRow = await client.query(`SELECT * FROM users WHERE email = $1`, [userEmail]);
        let userId = userRow.rows[0].id;

        console.log("userRow");
        console.log(userRow.rows[0]);

        let productRow = await client.query(`INSERT INTO products (name, price, quantity, currency_id) VALUES ('ZZZ01', 18.18, 50, 1) RETURNING id`);
        let productId = productRow.rows[0].id;

        console.log("productId");
        console.log(productId);

        const requestData = {
          order_date: '2024-11-15T12:00:00Z',
          status: 'Ready for Paying',
          email: userEmail,
          order_items: JSON.stringify([
            { product_id: productId, quantity: 7, price: 18.18 },
            { product_id: productId, quantity: 3, price: 18.18 }
          ])
        };

        let sessionRow = await client.query(`SELECT * FROM staff JOIN custom_sessions staff_id ON staff.id = staff_id WHERE username = $1`, [staffUsername]);
        let sessionId = sessionRow.rows[0].session_id;

        const response = await request(backOfficeApp)
            .post('/create/orders')
            .set('Content-Type', 'multipart/form-data')
            .set('Cookie', cookie.serialize('session_id', sessionId))
            .field('order_date', requestData.order_date)
            .field('status', requestData.status)
            .field('email', requestData.email)
            .field('order_items', requestData.order_items)
            .expect(201);

        expect(response.body).toEqual({
          message: 'orders created successfully',
        });

        let updatedProductRow = await client.query(`SELECT * FROM products WHERE id =$1`, [productId]);
        const updatedQuantity = updatedProductRow.rows[0].quantity;
        expect(updatedQuantity).toBe(40);

        // Clean up: delete the created order (for isolated tests)
        await client.query('DELETE FROM order_items');
        await client.query('DELETE FROM orders');
        await client.query(`DELETE FROM users WHERE id = $1`, [userId]);
        await client.query(`DELETE FROM custom_sessions`);
        client.release();
    });
});