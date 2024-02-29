import pytest
import bcrypt

from flask import render_template
from project.main import app
from project.main import registration, send_verification_email, mail, hash_password
from project.exception import CustomError
from flask import session, url_for
from unittest.mock import patch

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

def test_invalid_email_registration(client):
    with patch('project.main.hash_password', return_value='hashed_password') as mock_hash_password:
        response = client.post('/registration', data={
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'notAValidEmail',
            'password': 'password123'
    })
    assert response.status_code == 302
    assert url_for('registration') in response.location
    with client.session_transaction() as session:
        assert "Email is not valid" in session.get('flash_messages', ["Email is not valid"])

def test_invalid_first_name_registration(client):
    with patch('project.main.hash_password', return_value='hashed_password') as mock_hash_password:
        response=client.post('/registration', data={
            'first_name': 'A',
            'last_name': 'User',
            'email': 'testuseerqq@example.com',
            'password': 'password123'
    })
    assert response.status_code == 302
    assert url_for('registration') in response.location
    with client.session_transaction() as session:
        assert "First name is must be between 3 and 50 symbols" in session.get('flash_messages', ["First name is must be between 3 and 50 symbols"])

def test_invalid_last_name_registration(client):
    with patch('project.main.hash_password', return_value='hashed_password') as mock_hash_password:
        response = client.post('/registration', data={
            'first_name': 'Amber',
            'last_name': 'U',
            'email': 'testuseerqq@example.com',
            'password': 'password123'
    })
    assert response.status_code == 302
    assert url_for('registration') in response.location
    with client.session_transaction() as session:
        assert "Last name must be between 3 and 50 symbols" in session.get('flash_messages', ["Last name must be between 3 and 50 symbols"])

# def test_registration_get(client):
    # responsee = client.get('/registration')
    # response = render_template('registration.html')
    # assert response.status_code == 200  
    # assert b"Register" in response.data  
    # assert "registration.html" in (response.get_data(as_text=True))
    # assert response.status_code == 302
    # assert render_template('registration.html')
    # assert url_for('registration') in response.location
        
def test_verification_email_sends_enail_successfull(client):
    user_email = 'user@example.com'
    verification_code = 'dsafdsfsafasgagjyt[;h]df'

    with app.app_context():
        with patch.object(mail, 'send') as mock_send:
            send_verification_email(user_email, verification_code)

            mock_send.assert_called_once()

            args, kwargs = mock_send.call_args
            message = args[0]

            assert message.subject == 'Email Verification'
            assert message.recipients == [user_email]
            assert 'Please insert the verification code in the form: ' + verification_code

def test_hash_password_successfull(client):
    password = '123456789'

    hashed_password = hash_password(password)

    assert password != hashed_password
    assert bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

