import pytest
import bcrypt

from flask import render_template
from project.main import app
from project.main import registration, send_verification_email, mail, hash_password
from project.exception import CustomError
from project import config
from flask import session, url_for
from unittest.mock import patch, MagicMock
import psycopg2

database = config.test_database
user = config.user
password = config.password
host = config.host

def test_registration_get(client):
    response = client.get('/registration')

    assert response.status_code == 200  
    assert b"Register" in response.data  
    assert render_template('registration.html')

def test_registartion_success(client, setup_database):
    # Ако не мокна изпращането на мейл се изпраща реален имейл от тест кейса
    with patch('project.main.send_verification_email') as mock_send_email, \
    patch('project.main.captcha.validate', return_value=True) as mock_validate:
        response=client.post('/registration', data={
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'testuseerqq@example.com',
        'password': 'password123',
        'captcha': 'valid_captcha'
    })
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", ('testuseerqq@example.com',))

        row = cur.fetchone()

        assert row is not None, "No record found for the user"
        assert cur.fetchone() is None, "More than one record found for the user" 
        assert response.status_code == 302
        assert url_for('verify') in response.location

        cur.close()
        conn.close()

def test_invalid_email_registration(client):
    with patch('project.main.captcha.validate', return_value=True) as mock_validate:
        response = client.post('/registration', data={
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'notAValidEmail',
            'password': 'password123',
            'captcha': 'valid_captcha'
        })
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", ('notAValidEmail',))

    row = cur.fetchone()
    assert row is None, "No record found for the user"
    assert response.status_code == 302
    assert url_for('registration') in response.location

def test_invalid_first_name_registration(client):
    with patch('project.main.captcha.validate', return_value=True) as mock_validate:
        response=client.post('/registration', data={
            'first_name': 'A',
            'last_name': 'User',
            'email': 'gfhdughfduhgjdf@example.com',
            'password': 'password123',
            'captcha': 'valid_captcha'
    })
        
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", ('gfhdughfduhgjdf@example.com',))

    row = cur.fetchone()
    assert row is None, "No record found for the user"
    assert response.status_code == 302
    assert url_for('registration') in response.location

def test_invalid_last_name_registration(client):
    with patch('project.main.hash_password', return_value='hashed_password') as mock_hash_password, \
    patch('project.main.captcha.validate', return_value=True) as mock_validate:
        response = client.post('/registration', data={
            'first_name': 'Amber',
            'last_name': 'U',
            'email': 'gfhdughfduhgjdf@example.com',
            'password': 'password123',
            'captcha': 'valid_captcha'
    })
        
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", ('gfhdughfduhgjdf@example.com',))

    row = cur.fetchone()
    assert row is None, "No record found for the user"
    assert response.status_code == 302
    assert url_for('registration') in response.location
        
def test_verification_email_sends_enail_successful(client):
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

def test_hash_password_successful(client):
    password = '123456789'

    hashed_password = hash_password(password)

    assert password != hashed_password
    assert bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def test_verify_get(client):
    response = client.get('/verify')

    assert response.status_code == 200  
    assert b"Verify" in response.data  
    assert render_template('verify.html')

def test_verify_post_successful(client, setup_database):
    with patch('project.main.send_verification_email') as mock_send_email, \
    patch('project.main.captcha.validate', return_value=True) as mock_validate:
        verification_code = '56156565454565644'
        client.post('/registration', data={
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'alooooooo@example.com',
        'password': 'password123',
        'captcha': 'valid_captcha'
    })
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

        cur.execute("UPDATE users SET verification_code = '56156565454565644' WHERE email = %s", ('alooooooo@example.com',))
        conn.commit()
        
        responce = client.post('/verify', data = {
            'email': 'alooooooo@example.com',
            'verification_code': verification_code
        })

        cur.execute("SELECT verification_status FROM users WHERE email = %s", ('alooooooo@example.com',))
        conn.commit()

        verification_status = cur.fetchone()['verification_status']

        assert verification_status
        assert responce.status_code == 302
        assert url_for('login') in responce.headers['Location']
        cur.close()

def test_login_get_successful(client, setup_database):
    responce = client.get('/login')

    assert responce.status_code == 200
    assert b"Login" in responce.data
    assert render_template('login.html')

def test_login_post_successful(client, setup_database):
    with patch('project.main.send_verification_email') as mock_send_email, \
    patch('project.main.captcha.validate', return_value=True) as mock_validate, \
    patch('project.main.verify_password', return_value='hashed_password') as mock_verify_password :
        verification_code = '561565644'
        client.post('/registration', data={
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'alooo@example.com',
        'password': 'password123',
        'captcha': 'valid_captcha'
    })
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()

        cur.execute("UPDATE users SET verification_code = '561565644' WHERE email = %s", ('alooooooo@example.com',))
        conn.commit()

        client.post('/verify', data = {
            'email': 'alooo@example.com',
            'verification_code': '561565644'
        })

        cur.execute("UPDATE users SET verification_status = true WHERE email = %s", ('alooo@example.com',))
        conn.commit()

        responce = client.post('/login', data = {
           'email': 'alooo@example.com',
           'password': 'password123'
        })
        
        assert responce.status_code == 302
        assert session.get('user_email') == 'alooo@example.com'
        assert url_for('home') in responce.location
        cur.close()

def test_logout_get_successful(client, setup_database):
    with patch('project.main.verify_password', return_value='hashed_password') as mock_verify_password :
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", ('Mozambik', 'Mizake', 'aloooooo@example.com', '123456789', '12588523'))
        cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", ('12588523',))

        conn.commit()

        cur.close()
        conn.close()

        client.post('/login', data = {
            'email': 'aloooooo@example.com',
            'password': '123456789'
        })

        responce = client.get('/logout')

        assert session.get('user_email') != 'aloooooo@example.com'
        assert url_for('home') in responce.location
def test_settings_get_successful(client, setup_database):
    with patch('project.main.verify_password', return_value=True) as mock_verify_password :
        prepare_settings()

        client.post('/login', data = {
            'email': 'aloooo@example.com',
            'password': '123456789'
        })

        responce = client.get('/profile')

        assert responce.status_code == 200
        assert session.get('user_email') == 'aloooo@example.com'
        assert b'Settings' in responce.data

def test_delete_account_successful(client):
    responce = client.post('/delete_account')

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()

    is_deleted = cur.execute("SELECT verification_status FROM users WHERE email = %s", ('alooooooo@example.com',))

    conn.commit()
    
    assert is_deleted == None
    assert session.get('user_email') != 'alooooooo@example.com'
    url_for('login') in responce.location

    cur.close()
    conn.close()

def test_delete_account_not_successful(client):
    client.get('/logout')
    responce = client.post('/delete_account')

    assert responce.status_code == 200
    # assert 'method_not_allowed' in responce.headers['Location'] 

def test_settings_get_not_successful(client):
    client.get('/logout')
    responce = client.get('/profile')   

    assert responce.status_code == 302
    assert '/login' in responce.headers['Location']

def prepare_settings():
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", ('Mozambik', 'Mizake', 'aloooo@example.com', '123456789', '12588523'))
        cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", ('12588523',))

        conn.commit()

        cur.close()
        conn.close()

def test_update_settings_successful(client):
    with patch('project.main.verify_password') as mock_verify_password:
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code, verification_status) VALUES (%s, %s, %s, %s, %s, %s)", ('Jonni', 'Sins', 'keleme@abv.bg', '123456789', '12588523', 'true'))
        conn.commit()

        client.post('/login', data={
           'email': 'keleme@abv.bg',
            'password': '123456789'
        })

        assert session.get('user_email') == 'keleme@abv.bg'

        cur.execute("SELECT first_name FROM users WHERE email = %s", ('keleme@abv.bg',))
        first_name = cur.fetchone()[0]
        cur.execute("SELECT last_name FROM users WHERE email = %s", ('keleme@abv.bg',))
        last_name = cur.fetchone()[0]
        cur.execute("SELECT password FROM users WHERE email = %s", ('keleme@abv.bg',))
        password_ = cur.fetchone()[0]

        responce = client.post('/update_profile', data = {
            'first-name': 'UPDATE',
            'last-name': 'SETTINGS',
            'email': 'UPDATEEMAIL@GMAIL.COM',
            'password': '123456'
        })   

        cur.execute("SELECT first_name FROM users WHERE email = %s", ('UPDATEEMAIL@GMAIL.COM',))
        changed_first_name = cur.fetchone()[0]
        cur.execute("SELECT last_name FROM users WHERE email = %s", ('UPDATEEMAIL@GMAIL.COM',))
        changed_last_name = cur.fetchone()[0]
        cur.execute("SELECT password FROM users WHERE email = %s", ('UPDATEEMAIL@GMAIL.COM',))
        changed_password = cur.fetchone()[0]

        assert session.get('user_email') == 'UPDATEEMAIL@GMAIL.COM'  
        assert first_name != changed_first_name
        assert last_name != changed_last_name
        assert password_ != changed_password
        assert '/home' in responce.headers['Location']

def test_home_authenticated(client):
    with client.session_transaction() as sess:
        sess['user_email'] = 'test@example.com'
    
    response = client.get('/home')

    assert response.status_code == 200
    assert b'Home Page' in response.data

def test_home_not_authenticated(client):
    response = client.get('/home', follow_redirects=True)

    assert response.status_code == 200
    # assert response.location == 'http://localhost/login'

