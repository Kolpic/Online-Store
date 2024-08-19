import pytest
import psycopg2
from project.main import app
from project import config

#TODO: _old

@pytest.fixture(scope="module")
def client():
    print('Configuration !!!!!!!!!!!!!!!')
    app.config['TESTING'] = True
    app.config['MAIL_SUPPRESS_SEND'] = True
    app.config['DATABASE'] = 'users_registration_database_for_pytest'
    app.config['USER'] = 'myuser'
    app.config['PASSWORD'] = '1234'

    with app.test_client() as client:
        with app.app_context():
            yield client
            
@pytest.fixture(autouse=True)
def setup_database():
    print('Configuration DB!!!!!!!!!!!!!!!')
    conn_params = {
        'dbname': 'users_registration_database_for_pytest',
        'user': 'myuser',
        'password': '1234',
        'host':'localhost'
    }

    conn = psycopg2.connect(**conn_params)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    yield conn, cursor

    cursor.close()
    conn.close()