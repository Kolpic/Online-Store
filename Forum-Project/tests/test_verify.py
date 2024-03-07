from flask import url_for, redirect
from unittest.mock import patch, MagicMock
from project.main import verify
from flask import render_template
from project import config
import psycopg2

database = config.test_database
user = config.user
password = config.password
host = config.host

def test_verify_get(client):
    response = client.get('/verify')

    assert response.status_code == 200  
    assert b"Verify" in response.data  
    assert render_template('verify.html')

def test_verify_post_successful(client, setup_database):
    with patch('project.main.send_verification_email') as mock_send_email, \
    patch('os.urandom', MagicMock(return_value=b'\x00' * 24)) as mock_verification_code:
        verification_code = '00' * 24
        client.post('/registration', data={
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'alooooooo@example.com',
        'password': 'password123'
    })
        responce = client.post('/verify', data = {
            'email': 'alooooooo@example.com',
            'verification_code': verification_code
        })

        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("SELECT verification_status FROM users WHERE email = %s", ('alooooooo@example.com',))

        verification_status = cur.fetchone()[0]

        assert verification_status
        assert responce.status_code == 302
        assert url_for('login') in responce.headers['Location']
