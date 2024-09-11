const frontOffice = require('../../front_office');
const utils = require('../../utils');
const { WrongUserInputException } = require('../../exceptions');

describe('Registration functions', () => {
  let client;

  beforeEach(() => {
    client = {
      query: jest.fn(),
    };
  });

  test('prepareRegistrationData should return prepared data', async () => {
    client.query.mockResolvedValueOnce({
      rows: [{ id: 1, result: 8 }],
    }).mockResolvedValueOnce({
      rows: [{ id: 1, name: 'USA', code: '+1' }, { id: 2, name: 'Canada', code: '+2' }],
    });

    const data = await frontOffice.prepareRegistrationData(client, 3, 5);

    expect(data).toEqual({
      first_captcha_number: 3,
      second_captcha_number: 5,
      captcha_id: 1,
      country_codes: [
        { id: 1, name: 'USA', code: '+1' },
        { id: 2, name: 'Canada', code: '+2' },
      ],
    });
  });

  test('registration should throw error for invalid first name', async () => {
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_settings
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_attempts
    client.query.mockResolvedValueOnce({ rows: [] }); // user with the same email

    const requestData = {
      first_name: 'G',
      last_name: 'Petrov',
      email: 'exampleewithme@gmail.bg',
      password: '123456789',
      confirm_password: '123456789',
      phone: '894703986',
      gender: 'male',
      captcha_id: 1,
      captcha: '8',
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    await expect(frontOffice.registration(client, requestData))
      .rejects
      .toThrow(new WrongUserInputException("First name must be between 3 and 50 characters"));
  });

    test('registration should throw error for invalid last name', async () => {
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_settings
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_attempts
    client.query.mockResolvedValueOnce({ rows: [] }); // user with the same email

    const requestData = {
      first_name: 'Galin',
      last_name: 'P',
      email: 'exampleewithme@gmail.bg',
      password: '123456789',
      confirm_password: '123456789',
      phone: '894703986',
      gender: 'male',
      captcha_id: 1,
      captcha: '8',
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    await expect(frontOffice.registration(client, requestData))
      .rejects
      .toThrow(new WrongUserInputException("Last name must be between 3 and 50 characters"));
  });

    test('registration should throw error for already registered email', async () => {
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_settings
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_attempts
    client.query.mockResolvedValueOnce({ rows: [{id: 1, email: "exampleewithme@gmail.bg"}] }); // user with the same email

    const requestData = {
      first_name: 'Galin',
      last_name: 'Petrov',
      email: 'exampleewithme@gmail.bg',
      password: '123456789',
      confirm_password: '123456789',
      phone: '894703986',
      gender: 'male',
      captcha_id: 1,
      captcha: '8',
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    await expect(frontOffice.registration(client, requestData))
      .rejects
      .toThrow(new WrongUserInputException("There is already registration with this email"));
  });

    test('registration should throw error for invalid email', async () => {
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_settings
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_attempts
    client.query.mockResolvedValueOnce({ rows: [] }); // user with the same email

    const requestData = {
      first_name: 'Galin',
      last_name: 'Petrov',
      email: 'exampleewithmegmail.bg',
      password: '123456789',
      confirm_password: '123456789',
      phone: '894703986',
      gender: 'male',
      captcha_id: 1,
      captcha: '8',
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    await expect(frontOffice.registration(client, requestData))
      .rejects
      .toThrow(new WrongUserInputException("Email is not valid"));
  });

    test('registration should throw error for short password', async () => {
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_settings
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_attempts
    client.query.mockResolvedValueOnce({ rows: [] }); // user with the same email

    const requestData = {
      first_name: 'Galin',
      last_name: 'Petrov',
      email: 'exampleewithmegmail.bg',
      password: '1234',
      confirm_password: '123456789',
      phone: '894703986',
      gender: 'male',
      captcha_id: 1,
      captcha: '8',
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    await expect(frontOffice.registration(client, requestData))
      .rejects
      .toThrow(new WrongUserInputException("Password must be between 7 and 20 characters"));
  });

    test('registration should throw error for not matching passwords', async () => {
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_settings
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_attempts
    client.query.mockResolvedValueOnce({ rows: [] }); // user with the same email

    const requestData = {
      first_name: 'Galin',
      last_name: 'Petrov',
      email: 'exampleewithmegmail.bg',
      password: '123456789',
      confirm_password: '1234567899',
      phone: '894703986',
      gender: 'male',
      captcha_id: 1,
      captcha: '8',
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    await expect(frontOffice.registration(client, requestData))
      .rejects
      .toThrow(new WrongUserInputException("Password and Confirm Password fields are different"));
  });

    test('registration should throw error for invalid phone', async () => {
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_settings
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_attempts
    client.query.mockResolvedValueOnce({ rows: [] }); // user with the same email

    const requestData = {
      first_name: 'Galin',
      last_name: 'Petrov',
      email: 'exampleewithmegmail.bg',
      password: '123456789',
      confirm_password: '123456789',
      phone: '89470',
      gender: 'male',
      captcha_id: 1,
      captcha: '8',
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    await expect(frontOffice.registration(client, requestData))
      .rejects
      .toThrow(new WrongUserInputException("Phone number format is not valid. The number should be between 7 and 15 digits"));
  });

    test('registration should throw error for invalid gender', async () => {
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_settings
    client.query.mockResolvedValueOnce({ rows: [] }); // captcha_attempts
    client.query.mockResolvedValueOnce({ rows: [] }); // user with the same email

    const requestData = {
      first_name: 'Galin',
      last_name: 'Petrov',
      email: 'exampleewithmegmail.bg',
      password: '123456789',
      confirm_password: '123456789',
      phone: '894703986',
      gender: 'bee',
      captcha_id: 1,
      captcha: '8',
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    await expect(frontOffice.registration(client, requestData))
      .rejects
      .toThrow(new WrongUserInputException("Gender must be Male or Female or Prefer not to say"));
  });

});

describe('Registration functions for invalid captcha and timeout', () => {
  let client;

  beforeEach(() => {
    client = {
      query: jest.fn(), // Mock the query function
    };
  });

  test('registration should throw for invalid captcha', async () => {
    // Mock the sequence of client.query calls in the correct order
    client.query
      // 1st query: SELECT * FROM captcha_settings
      .mockResolvedValueOnce({
        rows: [
          { id: 1, name: "max_captcha_attempts", value: '3' },
          { id: 2, name: "captcha_timeout_minutes", value: '11' },
        ],
      })
      // 2nd query: SELECT * FROM captcha_attempts WHERE ip_address = $1
      .mockResolvedValueOnce({
        rows: [
          { id: 1, ip_address: '127.0.0.1', last_attempt_time: new Date().toISOString(), attempts: 1 },
        ],
      })
      // 3rd query: SELECT * FROM users WHERE email = $1
      .mockResolvedValueOnce({ rows: [] }) // No user with the same email
      // 4th query: SELECT result FROM captcha WHERE id = $1
      .mockResolvedValueOnce({ rows: [{ result: 8 }] })
      // 5th query: UPDATE captcha_attempts SET attempts = $1, last_attempt_time = CURRENT_TIMESTAMP WHERE id = $2
      .mockResolvedValueOnce();

    const requestData = {
      first_name: 'Galin',
      last_name: 'Petrov',
      email: 'example@gmail.com',
      password: '123456789',
      confirm_password: '123456789',
      phone: '894703986',
      gender: 'male',
      captcha_id: 1,
      captcha: '5', // Incorrect CAPTCHA
      user_ip: '127.0.0.1',
      hashed_password: 'hashed_password_d',
      verification_code: '1234',
      country_code: '+1',
      address: 'Georgi Kirkov 56',
    };

    // Test the function and expect an exception due to invalid CAPTCHA
    await expect(frontOffice.registration(client, requestData))
      .rejects.toThrow(new WrongUserInputException('Invalid CAPTCHA. Please try again'));

    // Verify that the UPDATE query was called to increment attempts
  expect(client.query).toHaveBeenNthCalledWith(
    5, // The 5th query in the sequence
    'UPDATE captcha_attempts SET attempts = $1, last_attempt_time = CURRENT_TIMESTAMP WHERE id = $2',
    [2, 1] // New attempts count is 2, captcha_attempts id is 1
  );
  
  // Verify that the COMMIT query was called after the UPDATE query
  expect(client.query).toHaveBeenNthCalledWith(
    6, // The 6th query in the sequence
    'COMMIT'
  );
  });

  test('registration should timeout after exceeding max CAPTCHA attempts', async () => {
  // Calculate a time less than captcha_timeout_minutes ago
  const lastAttemptTime = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // 5 minutes ago

  client.query
    .mockResolvedValueOnce({
      rows: [
        { id: 1, name: 'max_captcha_attempts', value: '3' },
        { id: 2, name: 'captcha_timeout_minutes', value: '11' },
      ],
    })
    // Mock captcha_attempts: User has 3 previous attempts
    .mockResolvedValueOnce({
      rows: [
        {
          id: 1,
          ip_address: '127.0.0.1',
          last_attempt_time: lastAttemptTime,
          attempts: 3,
        },
      ],
    })
    // Mock users: No existing user with the email
    .mockResolvedValueOnce({ rows: [] });

  const requestData = {
    first_name: 'Galin',
    last_name: 'Petrov',
    email: 'example@gmail.com',
    password: '123456789',
    confirm_password: '123456789',
    phone: '894703986',
    gender: 'male',
    captcha_id: 1,
    captcha: '5', // Incorrect CAPTCHA
    user_ip: '127.0.0.1',
    hashed_password: 'hashed_password_d',
    verification_code: '1234',
    country_code: '+1',
    address: 'Georgi Kirkov 56',
  };

  await expect(frontOffice.registration(client, requestData))
    .rejects.toThrow(
      new WrongUserInputException(
        'You typed wrong captcha several times, now you have timeout 11 minutes'
      )
    );

  // Ensure that no INSERT or UPDATE queries were called after timeout
  expect(client.query).toHaveBeenCalledTimes(3); // Only the SELECT queries were called
  });
});