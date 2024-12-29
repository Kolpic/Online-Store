// const express = require('express');
// const request = require('supertest'); // for making HTTP requests to the express app
// const crypto = require('crypto');
// const { router } = require('../../main');
// const front_office = require('../../front_office');
// const { WrongUserInputException } = require('../../exceptions');
// const errors = require('../../error_codes');
// const { app, backOfficeApp } = require('../../app');
// const pool = require('../../db');
// const cookie = require('cookie');

// jest.mock('../../front_office');

// const axios = require('axios');
const { createOrder, capturePayment, generateAccessToken } = require('../../paypal');
const main = require('../../main');

global.fetch = jest.fn();

describe('PayPal API Integration Basic Cases', () => {
    let client;
  
    beforeEach(() => {
        fetch.mockClear();
    });
  
    it('should return valid generated token', async () => {
        fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ access_token: 'test_access_token' })
        });
         
        const token = await generateAccessToken();

        console.log("token", token);

        expect(token).toBe('test_access_token');
    });

    it('should throw error when fetch fails', async () => {
        fetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ error: 'Invalid client credentials' })
        });

        await expect(generateAccessToken()).rejects.toThrow('Failed to generate access token');
    });

    it('should create order successfully', async () => {
        fetch
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({ access_token: 'test_access_token' })
        }) // Mock for `generateAccessToken`
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                links: [{ rel: 'approve', href: 'https://approval-link.com' }]
            })
        }); // Mock for `createOrder`

        const mockClient = {
            query: jest.fn()
                .mockResolvedValueOnce({
                    rows: [{ order_id: 123, status: 'Ready for Paying' }]
                })
                .mockResolvedValueOnce({
                    rows: [
                        {
                            id: 1,
                            order_id: 123,
                            product_id: 132,
                            cart_quantity: 2,
                            price: '50.00',
                            vat: '10',
                            name: 'Product A',
                            symbol: 'USD'
                        }
                    ]
                })
        };

        const orderId = 123;
        const approvalLink = await createOrder(orderId, mockClient);
        console.log("Approval link", approvalLink);

        expect(approvalLink).toBe('https://approval-link.com');
    });

    it('should throw error when fetch fails for createOrder', async () => {
        fetch
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({ access_token: 'test_access_token' })
        }) // Mock for `generateAccessToken`
        .mockResolvedValueOnce({
            ok: false,
            json: async () => ({
                links: [{ rel: 'approve', href: 'https://approval-link.com' }]
            })
        }); // Mock for `createOrder`

        const mockClient = {
            query: jest.fn()
                .mockResolvedValueOnce({
                    rows: [{ order_id: 123, status: 'Ready for Paying' }]
                })
                .mockResolvedValueOnce({
                    rows: [
                        {
                            id: 1,
                            order_id: 123,
                            product_id: 132,
                            cart_quantity: 2,
                            price: '50.00',
                            vat: '10',
                            name: 'Product A',
                            symbol: 'USD'
                        }
                    ]
                })
        };

        const orderId = 123;
        await expect(createOrder(orderId, mockClient)).rejects.toThrow('Failed to create order');
    });

    it('should capture payment successfully', async () => {
        fetch
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({ access_token: 'test_access_token' })
        })
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({ status: 'COMPLETED' })
        });

        const response = await capturePayment('order1');
        expect(response.status).toBe('COMPLETED');
    })

    it('should throw error when fetch fails for capturePayment', async () => {
        fetch
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({ access_token: 'test_access_token' })
        })
        .mockResolvedValueOnce({
            ok: false,
            json: async () => ({ status: 'COMPLETED' })
        });

        await expect(capturePayment('order1')).rejects.toThrow('Failed to capture payment with paypal');
    })
});

describe('PayPal API Integration - Edge Cases', () => {
    let mockClient;

    beforeEach(() => {
        fetch.mockClear();
        mockClient = {
            query: jest.fn()
                .mockResolvedValueOnce({
                    rows: [{ order_id: 123, status: 'Ready for Paying' }]
                })
                .mockResolvedValueOnce({
                    rows: [
                        {
                            id: 1,
                            order_id: 123,
                            product_id: 132,
                            cart_quantity: 2,
                            price: '50.00',
                            vat: '10',
                            name: 'Product A',
                            symbol: 'USD'
                        }
                    ]
                })
        };
    });

    it('should handle invalid headers in generateAccessToken', async () => {
        fetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ error: 'Invalid Authorization header' })
        });

        await expect(generateAccessToken()).rejects.toThrow('Failed to generate access token with paypal');
    });

    it('should handle wrong HTTP method in generateAccessToken', async () => {
        fetch.mockImplementationOnce((url, options) => {
            expect(options.method).toBe('POST'); // Ensuring it's called with correct method
            options.method = 'GET'; // Simulate incorrect method
            return Promise.resolve({
                ok: false,
                json: async () => ({ error: 'Invalid HTTP method' })
            });
        });

        await expect(generateAccessToken()).rejects.toThrow('Failed to generate access token with paypal');
    });

    it('should handle invalid headers in createOrder', async () => {
        fetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'test_access_token' })
            }) // Mock for `generateAccessToken`
            .mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Invalid headers' })
            }); // Mock for `createOrder`

        const orderId = 123;

        await expect(createOrder(orderId, mockClient)).rejects.toThrow('Failed to create order with paypal');
    });

    it('should handle wrong HTTP method in createOrder', async () => {
        fetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'test_access_token' })
            }) // Mock for `generateAccessToken`
            .mockImplementationOnce((url, options) => {
                expect(options.method).toBe('POST'); // Ensuring it's called with correct method
                options.method = 'GET'; // Simulate incorrect method
                return Promise.resolve({
                    ok: false,
                    json: async () => ({ error: 'Invalid HTTP method for creating order' })
                });
            });

        const orderId = 123;

        await expect(createOrder(orderId, mockClient)).rejects.toThrow('Failed to create order with paypal');
    });

    it('should handle invalid payload in createOrder', async () => {
        fetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'test_access_token' })
            }) // Mock for `generateAccessToken`
            .mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Invalid payload' })
            }); // Mock for `createOrder`

        const orderId = 123;
        const badClient = {
            query: jest.fn()
                .mockResolvedValueOnce({
                    rows: [{ order_id: 123, status: 'Ready for Paying' }]
                })
                .mockResolvedValueOnce({
                    rows: [
                        {
                            id: 1,
                            order_id: 123,
                            product_id: 132,
                            cart_quantity: 'bad_value', // Simulate invalid payload
                            price: '50.00',
                            vat: '10',
                            name: 'Product A',
                            symbol: 'USD'
                        }
                    ]
                })
        };

        await expect(createOrder(orderId, badClient)).rejects.toThrow('Failed to create order with paypal');
    });

    it('should handle invalid headers in capturePayment', async () => {
        fetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'test_access_token' })
            }) // Mock for `generateAccessToken`
            .mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Invalid headers' })
            }); // Mock for `capturePayment`

        const orderId = 'order1';

        await expect(capturePayment(orderId)).rejects.toThrow('Failed to capture payment with paypal');
    });

    it('should handle wrong HTTP method in capturePayment', async () => {
        fetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'test_access_token' })
            }) // Mock for `generateAccessToken`
            .mockImplementationOnce((url, options) => {
                expect(options.method).toBe('POST'); // Ensuring it's called with correct method
                options.method = 'GET'; // Simulate incorrect method
                return Promise.resolve({
                    ok: false,
                    json: async () => ({ error: 'Invalid HTTP method for capturing payment' })
                });
            });

        const orderId = 'order1';

        await expect(capturePayment(orderId)).rejects.toThrow('Failed to capture payment with paypal');
    });
});

// describe('GET /registration test', () => {
//     let app;

//     beforeAll(() => {
//         app = express();
//         app.use(express.json());
//         app.use(router);
//     });

//     it('should return registration data with captcha', async () => {
//         // Mock data for the test
//         const mockPreparedData = {
//             first_captcha_number: 12,
//             second_captcha_number: 34,
//             captcha_id: 1,
//             country_codes: [
//                 { id: 1, name: 'Country1', code: 'C1' },
//                 { id: 2, name: 'Country2', code: 'C2' }
//             ]
//         };

//         // Mock the `prepareRegistrationData` method
//         front_office.prepareRegistrationData = jest.fn().mockResolvedValue(mockPreparedData);

//         const response = await request(app)
//             .get('/registration')
//             .expect('Content-Type', /json/)
//             .expect(200);

//         expect(response.body).toEqual({
//             country_codes: mockPreparedData.country_codes,
//             captcha: {
//                 first: mockPreparedData.first_captcha_number,
//                 second: mockPreparedData.second_captcha_number
//             },
//             captcha_id: mockPreparedData.captcha_id
//         });
//     });

//     it('should throw when we dont enter valid url', async () => {
//       const response = await request(app)
//             .get('/registration-wrong-url')
//             .expect('Content-Type', /json/)
//             .expect(400);
//     });
// });

// describe('POST /registration', () => {
//   it('should register a user successfully without polluting the database', async () => {
//     const client = await pool.connect();

//     await client.query(`
//         INSERT INTO captcha (first_number, second_number, result) 
//         VALUES (10, 2, 12)
//         RETURNING id
//     `);

//     const captchaResult = await client.query(`SELECT id FROM captcha WHERE result = 12`);
//     const captcha_id = captchaResult.rows[0].id;

//     let insertedCaptcha = await client.query(`SELECT * from captcha where id = ${captcha_id}`);

//     const requestData = {
//         first_name: 'Galin',
//         last_name: 'Petrov',
//         email: 'galin@example.com',
//         password: '123456789',
//         confirm_password: '123456789',
//         address: 'Georgi Kirkov 56',
//         country_code: '+359',
//         phone: '894703986',
//         gender: 'male',
//         captcha: '12',
//         captcha_id: captcha_id,
//     };

//     const response = await request(app)
//         .post('/registration')
//         .send(requestData)
//         .expect(201);

//     expect(response.body).toEqual({
//         success: true,
//         message: "User registered successfully. Please verify your email to complete the registration.",
//         email: requestData.email,
//     });

//     const result = await client.query('SELECT * FROM users WHERE email = $1', [requestData.email]);
//     expect(result.rows.length).toBe(1);
//     await client.query(`DELETE FROM users WHERE email = $1`, [requestData.email]);
//     client.release();
//   });
// });

// describe('POST /registration test should return error', () => {
//     it('should handle errors from registration method', async () => {
//         const requestData = {
//             first_name: 'Ga', // Invalid first name with less than 3 characters
//             last_name: 'Petrov',
//             email: 'galin@example.com',
//             password: '123456789',
//             confirm_password: '123456789',
//             address: 'Georgi Kirkov 56',
//             country_code: '+359',
//             phone: '894703986',
//             gender: 'male',
//             captcha: '12',
//             captcha_id: 1,
//         };

//         const response = await request(app)
//             .post('/registration')
//             .send(requestData)
//             .expect('Content-Type', /json/)
//             .expect(400);

//         expect(response.body).toEqual({
//             error_message: "First name must be between 3 and 50 characters",
//             error_code: errors.NAME_LENGTH_ERROR_CODE,
//         });
//     });
// });

// describe('orders CRUD', () => {
//     let userEmail = 'galin@example.com';
//     let staffUsername = 'Kolpic';

//     it('should register a user successfully without polluting the database', async () => {
//         const client = await pool.connect();

//         await client.query(`
//             INSERT INTO captcha (first_number, second_number, result) 
//             VALUES (10, 2, 12)
//             RETURNING id
//         `);

//         const captchaResult = await client.query(`SELECT id FROM captcha WHERE result = 12`);
//         const captcha_id = captchaResult.rows[0].id;

//         let insertedCaptcha = await client.query(`SELECT * from captcha where id = ${captcha_id}`);

//         const requestData = {
//             first_name: 'Galin',
//             last_name: 'Petrov',
//             email: userEmail,
//             password: '123456789',
//             confirm_password: '123456789',
//             address: 'Georgi Kirkov 56',
//             country_code: '+359',
//             phone: '894703986',
//             gender: 'male',
//             captcha: '12',
//             captcha_id: captcha_id,
//         };

//         const response = await request(app)
//             .post('/registration')
//             .send(requestData)
//             .expect(201);

//         expect(response.body).toEqual({
//             success: true,
//             message: "User registered successfully. Please verify your email to complete the registration.",
//             email: requestData.email,
//         });

//         const result = await client.query('SELECT * FROM users WHERE email = $1', [requestData.email]);
//         expect(result.rows.length).toBe(1);
//         client.release();
//   });

//     it('should login user successfully', async () => {
//         const client = await pool.connect();

//         const requestData = {
//             username: staffUsername,
//             password: '123456789'
//         };

//         const response = await request(backOfficeApp)
//             .post('/login')
//             .send(requestData)
//             .expect(200);

//         console.log("Login response headers:", response.headers);
//         expect(response.headers['set-cookie']).toBeDefined();

//         const sessionCookie = response.headers['set-cookie'].find(cookie => cookie.startsWith('session_id='));
//         expect(sessionCookie).toBeDefined();

//         const sessionId = sessionCookie.split(';')[0].split('=')[1]; // Extract session_id value
//         console.log("Extracted session_id:", sessionId);

//         expect(sessionId).toBeTruthy();

//         const result = await client.query('SELECT * FROM staff WHERE username = $1', [staffUsername]);

//         console.log("result");
//         console.log(result.rows);

//         expect(result.rows.length).toBe(1);
//         client.release();
//   });

//     it('should create an order successfully', async () => {
//         const client = await pool.connect();
//         let userRow = await client.query(`SELECT * FROM users WHERE email = $1`, [userEmail]);
//         let userId = userRow.rows[0].id;

//         console.log("userRow");
//         console.log(userRow.rows[0]);

//         let productRow = await client.query(`INSERT INTO products (name, price, quantity, currency_id) VALUES ('ZZZ01', 18.18, 50, 1) RETURNING id`);
//         let productId = productRow.rows[0].id;

//         console.log("productId");
//         console.log(productId);

//         const requestData = {
//           order_date: '2024-11-15T12:00:00Z',
//           status: 'Ready for Paying',
//           email: userEmail,
//           order_items: JSON.stringify([
//             { product_id: productId, quantity: 7, price: 18.18 },
//             { product_id: productId, quantity: 3, price: 18.18 }
//           ])
//         };

//         let sessionRow = await client.query(`SELECT * FROM staff JOIN custom_sessions staff_id ON staff.id = staff_id WHERE username = $1`, [staffUsername]);
//         let sessionId = sessionRow.rows[0].session_id;

//         const response = await request(backOfficeApp)
//             .post('/create/orders')
//             .set('Content-Type', 'multipart/form-data')
//             .set('Cookie', cookie.serialize('session_id', sessionId))
//             .field('order_date', requestData.order_date)
//             .field('status', requestData.status)
//             .field('email', requestData.email)
//             .field('order_items', requestData.order_items)
//             .expect(201);

//         expect(response.body).toEqual({
//           message: 'orders created successfully',
//         });

//         let updatedProductRow = await client.query(`SELECT * FROM products WHERE id =$1`, [productId]);
//         const updatedQuantity = updatedProductRow.rows[0].quantity;
//         expect(updatedQuantity).toBe(40);

//         // Clean up: delete the created order (for isolated tests)
//         await client.query('DELETE FROM order_items');
//         await client.query('DELETE FROM orders');
//         await client.query(`DELETE FROM users WHERE id = $1`, [userId]);
//         await client.query(`DELETE FROM custom_sessions`);
//         client.release();
//     });
// });