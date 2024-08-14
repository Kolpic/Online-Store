MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 465
MAIL_USERNAME = "galincho112@gmail.com"
MAIL_PASSWORD = "kskf nciq lqfm zevh"
MAIL_USE_TLS = False
MAIL_USE_SSL = True

cache = []
CACHE_TIMEOUT = 600

# TODO: work database -> user_registration, laptop database -> users_registration
database = "users_registration"
user = "myuser"
password = "1234"
host = "localhost"

# Database for testing
test_database = "users_registration_database_for_pytest"

# Database for QA
test_qa_database = "user_registration_qa_testing"

# Database for migration to look (emty database to test the new scripts - mig)
postgres_db = 'postgresql://myuser:1234@localhost/users_registration'