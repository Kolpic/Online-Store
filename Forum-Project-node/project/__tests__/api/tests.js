const express = require('express');
const request = require('supertest'); // for making HTTP requests to the express app
const crypto = require('crypto');
const { router } = require('../../main');
const front_office = require('../../front_office');
const utils = require('../../utils');
const { WrongUserInputException } = require('../../exceptions');

jest.mock('../../front_office');
jest.mock('../../utils');

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
            .expect(500);
    });
});

describe('POST /registration test', () => {
    let app;

    beforeAll(() => {
        app = express();
        app.use(express.json());
        app.use(router);
    });

    it('should register a user successfully', async () => {
        // Mock data for the test
        const mockHashPassword = 'hashed_password';

        // Mock functions
        front_office.registration = jest.fn().mockResolvedValue();
        utils.hashPassword = jest.fn().mockReturnValue(mockHashPassword);

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
            captcha_id: 1,
        };

        const response = await request(app)
        .post('/registration')
        .send(requestData)
        .expect('Content-Type', /json/)
        .expect(201);

        expect(response.body).toEqual({
            message: "User registered successfully. Please verify your email to complete the registration.",
            redirect_url: '/verify.html'
        });

        // Verify that registration was called with the expected arguments
        expect(front_office.registration).toHaveBeenCalledWith(expect.anything(), {
            ...requestData,
            hashed_password: mockHashPassword,
            verification_code: expect.any(String),
            user_ip: expect.any(String)
        });
    });
});

describe('POST /registration test should return error', () => {
    let app;

    beforeAll(() => {
        app = express();
        app.use(express.json());
        app.use(router);
    });
    
    it('should handle errors from registration method', async () => {
        // Mock data for the test
        const mockHashPassword = 'hashed_password';
        
        // Mock the registration function to throw an error
        front_office.registration = jest.fn().mockRejectedValue(new WrongUserInputException("First name must be between 3 and 50 characters"));
        utils.hashPassword = jest.fn().mockReturnValue(mockHashPassword);

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
            .expect(400); // Expecting a 400 Bad Request due to the error

        // Check if the error message returned is the same as the one thrown by registration
        expect(response.body).toEqual({
            error: "First name must be between 3 and 50 characters"
        });

        // Verify that the registration function was called with the expected arguments
        expect(front_office.registration).toHaveBeenCalledWith(expect.anything(), {
            ...requestData,
            hashed_password: mockHashPassword,
            verification_code: expect.any(String),
            user_ip: expect.any(String)
        });
    });
});