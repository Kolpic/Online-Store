import pytest
import psycopg2
from project.main import app
from project import config

@pytest.fixture(scope="module")
def client():
    print('Configuration !!!!!!!!!!!!!!!')
    app.config['TESTING'] = True
    app.config['MAIL_SUPPRESS_SEND'] = True
    app.config['DATABASE'] = config.test_database
    app.config['USER'] = config.user
    app.config['PASSWORD'] = config.password

    with app.test_client() as client:
        with app.app_context():
            yield client
            
@pytest.fixture(scope="module")
def setup_database():
    print('Configuration DB!!!!!!!!!!!!!!!')
    conn_params = {
        'dbname': 'user_registration_testing',
        'user': 'myuser',
        'password': '1234',
        'host':'localhost'
    }

    conn = psycopg2.connect(**conn_params)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cursor = conn.cursor()

    # cursor.execute('DROP DATABASE IF EXISTS user_registration_testing')
    # cursor.execute('CREATE DATABASE user_registration_testing')

    yield

    cursor.execute('DELETE FROM users;')

    cursor.close()
    conn.close()