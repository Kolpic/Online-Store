MAIL_SERVER = "smtp.gmail.com";
MAIL_PORT = 465;
MAIL_USERNAME = "galincho112@gmail.com";
MAIL_PASSWORD = "kskf nciq lqfm zevh";
MAIL_USE_TLS = false;
MAIL_USE_SSL = true;

//cache = []
CACHE_TIMEOUT = 60000;

// urls for sending emails
urlVerifyEmail = "http://10.20.3.101:5002/verify.html?token=";

// TODO: work database -> user_registration, laptop database -> users_registration
database = "users_registration";
user = "myuser";
password = "1234";
host = "localhost";

// Database for testing js
test_database_js = "users_registration_js_tests";

// Database for testing
test_database = "users_registration_database_for_pytest";

// Database for QA
test_qa_database = "user_registration_qa_testing";

// Database for migration to look (emty database to test the new scripts - mig)
postgres_db = 'postgresql://myuser:1234@localhost/users_registration';

module.exports = {
  MAIL_SERVER: "smtp.gmail.com",
  MAIL_PORT: 465,
  MAIL_USERNAME: "galincho112@gmail.com",
  MAIL_PASSWORD: "kskf nciq lqfm zevh",
  MAIL_USE_TLS: false,
  MAIL_USE_SSL: true,
  database: database,
  user: "myuser",
  password: "1234",
  host: "localhost",
  postgres_db: 'postgresql://myuser:1234@localhost/users_registration',
  CACHE_TIMEOUT: 60000,
  test_database: "users_registration_database_for_pytest",
  test_qa_database: "user_registration_qa_testing",
  test_database_js: test_database_js,
  urlVerifyEmail: urlVerifyEmail,
};