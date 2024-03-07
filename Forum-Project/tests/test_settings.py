from flask import session, url_for, render_template, redirect
from project import config
from unittest.mock import patch
import psycopg2

database = config.test_database
user = config.user
password = config.password
host = config.host

def test_settings_get_successful(client, setup_database):
    with patch('project.main.verify_password', return_value=True) as mock_verify_password :
        prepare_settings()

        client.post('/login', data = {
            'email': 'alooooooo@example.com',
            'password': '123456789'
        })

        responce = client.get('/settings')

        assert responce.status_code == 200
        assert session.get('user_email') == 'alooooooo@example.com'
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

    assert responce.status_code == 302
    assert '/registration' in responce.headers['Location']

def test_settings_get_not_successful(client):
    client.get('/logout')
    responce = client.get('/settings')   

    assert responce.status_code == 302
    assert '/login' in responce.headers['Location']

def prepare_settings():
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", ('Mozambik', 'Mizake', 'alooooooo@example.com', '123456789', '12588523'))
        cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", ('12588523',))

        conn.commit()

        cur.close()
        conn.close()