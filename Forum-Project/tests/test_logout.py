from flask import session, url_for
from project import config
from unittest.mock import patch
import psycopg2

database = config.test_database
user = config.user
password = config.password
host = config.host

def test_logout_get_successful(client, setup_database):
    with patch('project.main.verify_password', return_value='hashed_password') as mock_verify_password :
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", ('Mozambik', 'Mizake', 'alooooooo@example.com', '123456789', '12588523'))
        cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", ('12588523',))

        conn.commit()

        cur.close()
        conn.close()

        client.post('/login', data = {
            'email': 'alooooooo@example.com',
            'password': '123456789'
        })

        responce = client.get('/logout')

        assert session.get('user_email') != 'alooooooo@example.com'
        assert url_for('home') in responce.location