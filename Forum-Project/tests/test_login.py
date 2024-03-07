from flask import render_template, url_for, session
from unittest.mock import patch, MagicMock

def test_login_get_successful(client, setup_database):
    responce = client.get('/login')

    assert responce.status_code == 200
    assert b"Login" in responce.data
    assert render_template('login.html')

def test_login_post_successful(client, setup_database):
    with patch('project.main.send_verification_email') as mock_send_email, \
    patch('os.urandom', MagicMock(return_value=b'\x00' * 24)) as mock_verification_code, \
    patch('project.main.hash_password', return_value='hashed_password') as mock_hash_password, \
    patch('project.main.verify_password', return_value='hashed_password') as mock_verify_password :
        verification_code = '00' * 24
        client.post('/registration', data={
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'alooooooo@example.com',
        'password': 'password123'
    })
        client.post('/verify', data = {
            'email': 'alooooooo@example.com',
            'verification_code': verification_code
        })
        responce = client.post('/login', data = {
           'email': 'alooooooo@example.com',
           'password': 'password123'
        })

        assert responce.status_code == 302
        assert session.get('user_email') == 'alooooooo@example.com'
        assert url_for('home') in responce.location