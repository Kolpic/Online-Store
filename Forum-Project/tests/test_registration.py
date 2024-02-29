import pytest
import psycopg2
import psycopg2.extensions

from project import config
from project.main import app
from flask import session, url_for
from unittest.mock import patch

@pytest.fixture
def client(scope="module"):
    print('Configuration !!!!!!!!!!!!!!!')
    app.config['TESTING'] = True
    app.config['DATABASE'] = config.test_database
    app.config['USER'] = config.user
    app.config['PASSWORD'] = config.password

    with app.test_client() as client:
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

def test_registartion_success(client, setup_database):
    with patch('project.main.send_verification_email') as mock_send_email, \
    patch('project.main.hash_password', return_value='hashed_password') as mock_hash_password:
        response=client.post('/registration', data={
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'testuseerqq@example.com',
        'password': 'password123'
    })
        
        assert response.status_code == 302
        assert url_for('verify') in response.location
        mock_send_email.assert_called_once
        mock_hash_password.assert_called_once

def test_invalid_email_registration(client)
