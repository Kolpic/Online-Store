import pytest
import bcrypt
from project.main import app as flask_app
from project.main import app
from project import sessions
import os
from datetime import timedelta, datetime
from project import utils
import uuid
from project.main import add_to_cart_meth, add_to_cart, get_cart_items_count, get_cart_items_count

from flask import render_template, request
from project.utils import hash_password
from project.main import registration, send_verification_email, mail, send_recovey_password_email
# from project.exception import CustomError
from project import config
from flask import session, url_for
from unittest.mock import patch, MagicMock
import psycopg2

database = config.test_database
user = config.user
password = config.password
host = config.host
  
# @pytest.fixture
# def app():
#     """Fixture for creating the Flask application instance."""
#     yield flask_app

# @pytest.fixture
# def client(app):
#     """Fixture for creating the Flask test client."""
#     return app.test_client()

# @pytest.fixture
# def runner(app):
#     """Fixture for creating the Flask CLI runner."""
#     return app.test_cli_runner()

# @pytest.fixture
# def mock_conn():
#     """Fixture for mocking the database connection."""
#     with patch('project.main.psycopg2.connect') as mock_connect:
#         mock_conn = MagicMock()
#         mock_connect.return_value = mock_conn
#         yield mock_conn

# @pytest.fixture
# def mock_cur(mock_conn):
#     """Fixture for mocking the database cursor."""
#     mock_cur = MagicMock()
#     mock_conn.cursor.return_value.__enter__.return_value = mock_cur
#     yield mock_cur

# @pytest.fixture
# def mock_session():
#     """Fixture for mocking the Flask session."""
#     with patch('flask.session', dict()) as mock_session:
#         yield mock_session

def test_registration_get(client):

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    first_captcha_number = 5
    second_captcha_number = 5

    cur.execute("INSERT INTO captcha(first_number, second_number, result) VALUES (%s, %s, %s) RETURNING *", 
        (first_captcha_number, second_captcha_number, first_captcha_number + second_captcha_number))

    result_captcha = cur.fetchone()
    captcha = {'first': result_captcha['first_number'], 'second': result_captcha['second_number']}

    cur.execute("INSERT INTO country_codes (name, code) VALUES (%s, %s) RETURNING *", ("Bulgaria", "+359"))
    result_country_codes = cur.fetchall()

    response = client.get('/registration')

    assert len(result_country_codes) == 1
    assert response.status_code == 200  

    assert captcha['first'] == 5
    assert captcha['second'] == 5

    assert b"Register" in response.data  
    assert b"Captcha" in response.data

    with app.test_request_context():
        rendered_template = render_template('registration.html', captcha=captcha, country_codes=result_country_codes)

        assert 'first' in rendered_template
        assert 'second' in rendered_template
        assert 'Solve the following:' in rendered_template

def test_get_home_page_without_authenticated_user(client):
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM products")
    result_products = cur.fetchall()

    response = client.get('/home/1')

    assert len(result_products) == 0
    assert response.status_code == 200

def test_get_home_page_with_authenticated_user(client):
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        INSERT INTO users (first_name, last_name, email)
        VALUES (%s, %s, %s)
        RETURNING *
    """, ("Galin", "Petrov", "example@gmail.com"))

    user_row = cur.fetchone()

    cur.execute("SELECT * FROM users WHERE id = %s", (user_row['id'],))
    result_user = cur.fetchone()

    session_id = sessions.create_session(os=os, datetime=datetime, timedelta=timedelta, session_data=result_user['email'], cur=cur, conn=conn, is_front_office=True)

    utils.trace(session_id)

    client.set_cookie('session_id', f'{session_id}')

    # with client.session_transaction() as session:
    #     authenticated_user = sessions.get_current_user(request=session, cur=cur, conn=conn)

    cur.execute("SELECT * FROM products")
    result_products = cur.fetchall()

    response = client.get('/home/1')

    assert result_user['email'] == 'example@gmail.com'
    assert len(result_products) == 0
    assert response.status_code == 200

def test_add_to_cart_new_cart_unauthenticated_user(client,setup_database):
    conn, cur = setup_database

    utils.trace("conn")
    utils.trace(conn)
    utils.trace("cur")
    utils.trace(cur)

    cur.execute("""
        INSERT INTO settings (
            vat, 
            report_limitation_rows, 
            send_email_template_background_color, 
            send_email_template_text_align, 
            send_email_template_border, 
            send_email_template_border_collapse) 
        VALUES (
            25, 
            10001, 
            '#19bcc8', 
            'right', 
            4, 
            'collapse') 
        RETURNING *
    """)
    settings_row = cur.fetchone()

    utils.trace("settings_row")
    utils.trace(settings_row)

    settings_id = settings_row['id']

    cur.execute("""
                INSERT INTO products (
                    name, 
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (
                    'Test', 
                    10, 
                    5, 
                    'Tools',
                    1, 
                    %s) 
                RETURNING *
            """, (settings_id, ))
    product_row = cur.fetchone()

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    utils.trace("products")
    utils.trace(products)
    assert len(products) == 1

    cur.execute("SELECT * FROM settings")
    sett = cur.fetchall()
    utils.trace("sett")
    utils.trace(sett)
    assert len(sett) == 1

    product_id = product_row['id']
    user_id = "test_session1234"
    quantity = 1

    response_message = add_to_cart(conn, cur, user_id, product_id, quantity)
    assert response_message == "You successfully added item."

    cur.execute("SELECT * FROM cart_itmes WHERE product_id = %s", (product_id,))
    cart_item_row = cur.fetchone()

    assert cart_item_row is not None
    assert cart_item_row['quantity'] == quantity

def test_add_to_cart_new_cart_and_increase_quantity_unauthenticated(client,setup_database):
    conn, cur = setup_database

    utils.trace("conn")
    utils.trace(conn)
    utils.trace("cur")
    utils.trace(cur)

    cur.execute("""
        INSERT INTO settings (
            vat, 
            report_limitation_rows, 
            send_email_template_background_color, 
            send_email_template_text_align, 
            send_email_template_border, 
            send_email_template_border_collapse) 
        VALUES (
            25, 
            10001, 
            '#19bcc8', 
            'right', 
            4, 
            'collapse') 
        RETURNING *
    """)
    settings_row = cur.fetchone()

    utils.trace("settings_row")
    utils.trace(settings_row)

    settings_id = settings_row['id']

    cur.execute("""
                INSERT INTO products (
                    name, 
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (
                    'Test', 
                    10, 
                    5, 
                    'Tools',
                    1, 
                    %s) 
                RETURNING *
            """, (settings_id, ))
    product_row = cur.fetchone()

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    utils.trace("products")
    utils.trace(products)
    assert len(products) == 1

    cur.execute("SELECT * FROM settings")
    sett = cur.fetchall()
    utils.trace("sett")
    utils.trace(sett)
    assert len(sett) == 1

    product_id = product_row['id']
    user_id = "test_session1234"
    quantity_first_adding = 1
    quantity_second_adding = 3

    response_message = add_to_cart(conn, cur, user_id, product_id, quantity_first_adding)
    assert response_message == "You successfully added item."

    response_message = add_to_cart(conn, cur, user_id, product_id, quantity_second_adding)
    assert response_message == "You successfully added same item, quantity was increased."

    cur.execute("SELECT * FROM cart_itmes WHERE product_id = %s", (product_id,))
    cart_item_row = cur.fetchone()

    assert cart_item_row is not None
    assert cart_item_row['quantity'] == quantity_first_adding + quantity_second_adding

def test_add_to_cart_new_cart_authenticated_user(client,setup_database):
    conn, cur = setup_database

    utils.trace("conn")
    utils.trace(conn)
    utils.trace("cur")
    utils.trace(cur)

    cur.execute("""
        INSERT INTO settings (
            vat, 
            report_limitation_rows, 
            send_email_template_background_color, 
            send_email_template_text_align, 
            send_email_template_border, 
            send_email_template_border_collapse) 
        VALUES (
            25, 
            10001, 
            '#19bcc8', 
            'right', 
            4, 
            'collapse') 
        RETURNING *
    """)
    settings_row = cur.fetchone()

    utils.trace("settings_row")
    utils.trace(settings_row)

    settings_id = settings_row['id']

    cur.execute("""
                INSERT INTO products (
                    name, 
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (
                    'Test', 
                    10, 
                    5, 
                    'Tools',
                    1, 
                    %s) 
                RETURNING *
            """, (settings_id, ))
    product_row = cur.fetchone()

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    utils.trace("products")
    utils.trace(products)
    assert len(products) == 1

    cur.execute("SELECT * FROM settings")
    sett = cur.fetchall()
    utils.trace("sett")
    utils.trace(sett)
    assert len(sett) == 1

    cur.execute("INSERT INTO users (first_name, last_name, email) VALUES ('Galin', 'Petrov', 'exapleemail@gmail.com') RETURNING *")
    user_row = cur.fetchone()

    utils.trace("user_row")
    utils.trace(user_row)

    user_id = user_row['id']

    cur.execute("INSERT INTO custom_sessions (session_id, expires_at, is_active, user_id) VALUES ('test-session-id', %s, True, %s) RETURNING *", (datetime.now() - timedelta(minutes=30),user_row['id']))
    custom_sessions_row = cur.fetchone()

    product_id = product_row['id']
    quantity = 1

    with patch('project.sessions.get_current_user') as mocked_user_session:
        response_message = add_to_cart(conn, cur, user_id, product_id, quantity)


    assert response_message == "You successfully added item."

    cur.execute("SELECT * FROM cart_itmes WHERE product_id = %s", (product_id,))
    cart_item_row = cur.fetchone()

    assert cart_item_row is not None
    assert cart_item_row['quantity'] == quantity

def test_add_to_cart_new_cart_and_increase_quantity_authenticated_user(client,setup_database):
    conn, cur = setup_database

    utils.trace("conn")
    utils.trace(conn)
    utils.trace("cur")
    utils.trace(cur)

    cur.execute("""
        INSERT INTO settings (
            vat, 
            report_limitation_rows, 
            send_email_template_background_color, 
            send_email_template_text_align, 
            send_email_template_border, 
            send_email_template_border_collapse) 
        VALUES (
            25, 
            10001, 
            '#19bcc8', 
            'right', 
            4, 
            'collapse') 
        RETURNING *
    """)
    settings_row = cur.fetchone()

    utils.trace("settings_row")
    utils.trace(settings_row)

    settings_id = settings_row['id']

    cur.execute("""
                INSERT INTO products (
                    name, 
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (
                    'Test', 
                    10, 
                    5, 
                    'Tools',
                    1, 
                    %s) 
                RETURNING *
            """, (settings_id, ))
    product_row = cur.fetchone()

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    utils.trace("products")
    utils.trace(products)
    assert len(products) == 1

    cur.execute("SELECT * FROM settings")
    sett = cur.fetchall()
    utils.trace("sett")
    utils.trace(sett)
    assert len(sett) == 1

    cur.execute("INSERT INTO users (first_name, last_name, email) VALUES ('Galin', 'Petrov', 'exapleemail@gmail.com') RETURNING *")
    user_row = cur.fetchone()

    utils.trace("user_row")
    utils.trace(user_row)

    user_id = user_row['id']

    cur.execute("INSERT INTO custom_sessions (session_id, expires_at, is_active, user_id) VALUES ('test-session-id', %s, True, %s) RETURNING *", (datetime.now() - timedelta(minutes=30),user_row['id']))
    custom_sessions_row = cur.fetchone()

    product_id = product_row['id']
    quantity_first_item = 1
    quantity_second_item = 3

    with patch('project.sessions.get_current_user') as mocked_user_session:
        response_message_one = add_to_cart(conn, cur, user_id, product_id, quantity_first_item)
        response_message_two = add_to_cart(conn, cur, user_id, product_id, quantity_second_item)


    assert response_message_one == "You successfully added item."
    assert response_message_two == "You successfully added same item, quantity was increased."

    cur.execute("SELECT * FROM cart_itmes WHERE product_id = %s", (product_id,))
    cart_item_row = cur.fetchone()

    assert cart_item_row is not None
    assert cart_item_row['quantity'] == quantity_first_item + quantity_second_item


def test_get_cart_items_count_unauthenticated_user(client,setup_database):
    conn, cur = setup_database

    session_id = "anonym-session-id"

    cur.execute("""
        INSERT INTO settings (
            vat, 
            report_limitation_rows, 
            send_email_template_background_color, 
            send_email_template_text_align, 
            send_email_template_border, 
            send_email_template_border_collapse) 
        VALUES (
            25, 
            10001, 
            '#19bcc8', 
            'right', 
            4, 
            'collapse') 
        RETURNING *
    """)
    settings_row = cur.fetchone()

    cur.execute("""
                INSERT INTO products (
                    name, 
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (
                    'Test', 
                    10, 
                    5,  
                    'Tools',
                    1, 
                    %s) 
                RETURNING *
            """, (settings_row['id'], ))
    product_row = cur.fetchone()

    cur.execute("INSERT INTO carts (created_at, session_id) VALUES (%s, %s) RETURNING *", (datetime.now(), session_id))
    cart_row = cur.fetchone()

    cur.execute("INSERT INTO cart_itmes (cart_id, product_id, quantity, added_at, vat) VALUES (%s, %s, %s, %s, %s)", (cart_row['cart_id'], product_row['id'], 5, datetime.now(), settings_row['vat']))

    result = get_cart_items_count(conn, cur, session_id)

    assert result == 1

def test_get_cart_items_count_authenticated_user(client,setup_database):
    conn, cur = setup_database

    cur.execute("""
        INSERT INTO settings (
            vat, 
            report_limitation_rows, 
            send_email_template_background_color, 
            send_email_template_text_align, 
            send_email_template_border, 
            send_email_template_border_collapse) 
        VALUES (
            25, 
            10001, 
            '#19bcc8', 
            'right', 
            4, 
            'collapse') 
        RETURNING *
    """)
    settings_row = cur.fetchone()

    cur.execute("""
                INSERT INTO products (
                    name, 
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (
                    'Test', 
                    10, 
                    5,  
                    'Tools',
                    1, 
                    %s) 
                RETURNING *
            """, (settings_row['id'], ))
    product_row = cur.fetchone()

    cur.execute("INSERT INTO users (first_name, last_name, email) VALUES ('Galin', 'Petrov', 'exapleemail@gmail.com') RETURNING *")
    user_row = cur.fetchone()

    cur.execute("INSERT INTO carts (created_at, user_id) VALUES (%s, %s) RETURNING *", (datetime.now(), user_row['id']))
    cart_row = cur.fetchone()

    cur.execute("INSERT INTO cart_itmes (cart_id, product_id, quantity, added_at, vat) VALUES (%s, %s, %s, %s, %s)", (cart_row['cart_id'], product_row['id'], 5, datetime.now(), settings_row['vat']))

    result = get_cart_items_count(conn, cur, user_row['id'])

    assert result == 1

def test_add_to_cart_without_authenticated_user(client,setup_database):
    conn, cur = setup_database

    utils.trace("conn")
    utils.trace(conn)
    utils.trace("cur")
    utils.trace(cur)

    cur.execute("""
        INSERT INTO settings (
            vat, 
            report_limitation_rows, 
            send_email_template_background_color, 
            send_email_template_text_align, 
            send_email_template_border, 
            send_email_template_border_collapse) 
        VALUES (
            25, 
            10001, 
            '#19bcc8', 
            'right', 
            4, 
            'collapse') 
        RETURNING *
    """)
    settings_row = cur.fetchone()

    utils.trace("settings_row")
    utils.trace(settings_row)

    settings_id = settings_row['id']

    cur.execute("""
                INSERT INTO products (
                    name, 
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (
                    'Test', 
                    10, 
                    5, 
                    'Tools',
                    1, 
                    %s) 
                RETURNING *
            """, (settings_id, ))
    product_row = cur.fetchone()

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    utils.trace("products")
    utils.trace(products)
    assert len(products) == 1

    cur.execute("SELECT * FROM settings")
    sett = cur.fetchall()
    utils.trace("sett")
    utils.trace(sett)
    assert len(sett) == 1

    utils.trace("client.post")
    # response = client.post('/add_to_cart', data={'conn': conn, 'cur': cur, 'user_id': 'test4me4', 'product_id': product_row['id'], 'quantity': 1})

    # with patch('project.sessions.get_current_user', return_value=None):  # Mocking the session method
    #     response = client.post('/add_to_cart', data={
    #         'conn': conn,
    #         'cur': cur,
    #         'user_id': 'test4me4',
    #         'product_id': product_row['id'],
    #         'quantity': 1
    #     })

    with patch('project.sessions.get_current_user', return_value=None), \
    patch.object(request, 'form', {'product_id': '123', 'quantity': '2'}):
        response = add_to_cart_meth(conn,cur)

    assert response.status_code == 200
    json_data = response.get_json()
    utils.trace("json_data")
    utils.trace(json_data)
    assert json_data['message'] == "You successfully added item."
    assert 'session_id_unauthenticated_user' in response.headers['Set-Cookie']

# def test_registartion_success(client, setup_database):
#     # Ако не мокна изпращането на мейл се изпраща реален имейл от тест кейса
#     with patch('project.main.send_verification_email') as mock_send_email, \
#     patch('project.main.captcha.validate', return_value=True) as mock_validate:
#         response=client.post('/registration', data={
#         'first_name': 'Test',
#         'last_name': 'User',
#         'email': 'testuseerqq@example.com',
#         'password': 'password123',
#         'captcha': 'valid_captcha'
#     })
#         conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#         cur = conn.cursor()
#         cur.execute("SELECT * FROM users WHERE email = %s", ('testuseerqq@example.com',))

#         row = cur.fetchone()

#         assert row is not None, "No record found for the user"
#         assert cur.fetchone() is None, "More than one record found for the user" 
#         assert response.status_code == 302
#         assert url_for('verify') in response.location

#         cur.close()
#         conn.close()

# def test_invalid_email_registration(client):
#     with patch('project.main.captcha.validate', return_value=True) as mock_validate:
#         response = client.post('/registration', data={
#             'first_name': 'Test',
#             'last_name': 'User',
#             'email': 'notAValidEmail',
#             'password': 'password123',
#             'captcha': 'valid_captcha'
#         })
#     conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#     cur = conn.cursor()
#     cur.execute("SELECT * FROM users WHERE email = %s", ('notAValidEmail',))

#     row = cur.fetchone()
#     assert row is None, "No record found for the user"
#     assert response.status_code == 200
#     response_data = response.data.decode('utf-8') # decode response data from bytes to str
#     assert 'Email is not valid' in response_data

# def test_invalid_first_name_registration(client):
#     with patch('project.main.captcha.validate', return_value=True) as mock_validate:
#         response=client.post('/registration', data={
#             'first_name': 'A',
#             'last_name': 'User',
#             'email': 'gfhdughfduhgjdf@example.com',
#             'password': 'password123',
#             'captcha': 'valid_captcha'
#     })
        
#     conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#     cur = conn.cursor()
#     cur.execute("SELECT * FROM users WHERE email = %s", ('gfhdughfduhgjdf@example.com',))

#     row = cur.fetchone()
#     assert row is None, "No record found for the user"
#     assert response.status_code == 200
#     response_data = response.data.decode('utf-8') # decode response data from bytes to str
#     assert 'First name is must be between 3 and 50 symbols' in response_data

# def test_invalid_last_name_registration(client):
#     with patch('project.main.hash_password', return_value='hashed_password') as mock_hash_password, \
#     patch('project.main.captcha.validate', return_value=True) as mock_validate:
#         response = client.post('/registration', data={
#             'first_name': 'Amber',
#             'last_name': 'U',
#             'email': 'gfhdughfduhgjdf@example.com',
#             'password': 'password123',
#             'captcha': 'valid_captcha'
#     })
        
#     conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#     cur = conn.cursor()
#     cur.execute("SELECT * FROM users WHERE email = %s", ('gfhdughfduhgjdf@example.com',))

#     row = cur.fetchone()
#     assert row is None, "No record found for the user"
#     assert response.status_code == 200
#     response_data = response.data.decode('utf-8') # decode response data from bytes to str
#     assert 'Last name must be between 3 and 50 symbols' in response_data
        
# def test_verification_email_sends_enail_successful(client):
#     user_email = 'user@example.com'
#     verification_code = 'dsafdsfsafasgagjyt[;h]df'

#     with app.app_context():
#         with patch.object(mail, 'send') as mock_send:
#             send_verification_email(user_email, verification_code)

#             mock_send.assert_called_once()

#             args, kwargs = mock_send.call_args
#             message = args[0]

#             assert message.subject == 'Email Verification'
#             assert message.recipients == [user_email]
#             assert 'Please insert the verification code in the form: ' + verification_code

# def test_hash_password_successful(client):
#     password = '123456789'

#     hashed_password = hash_password(password)

#     assert password != hashed_password
#     assert bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

# def test_verify_get(client):
#     response = client.get('/verify')

#     assert response.status_code == 200  
#     assert b"Verify" in response.data  
#     assert render_template('verify.html')

# def test_verify_post_successful(client, setup_database):
#     with patch('project.main.send_verification_email') as mock_send_email, \
#     patch('project.main.captcha.validate', return_value=True) as mock_validate:
#         verification_code = '56156565454565644'
#         client.post('/registration', data={
#         'first_name': 'Test',
#         'last_name': 'User',
#         'email': 'alooooooo@example.com',
#         'password': 'password123',
#         'captcha': 'valid_captcha'
#     })
#         conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#         cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

#         cur.execute("UPDATE users SET verification_code = '56156565454565644' WHERE email = %s", ('alooooooo@example.com',))
#         conn.commit()
        
#         responce = client.post('/verify', data = {
#             'email': 'alooooooo@example.com',
#             'verification_code': verification_code
#         })

#         cur.execute("SELECT verification_status FROM users WHERE email = %s", ('alooooooo@example.com',))
#         conn.commit()

#         verification_status = cur.fetchone()['verification_status']

#         assert verification_status
#         assert responce.status_code == 302
#         assert url_for('login') in responce.headers['Location']
#         cur.close()

# def test_login_get_successful(client, setup_database):
#     responce = client.get('/login')

#     assert responce.status_code == 200
#     assert b"Login" in responce.data
#     assert render_template('login.html')

# def test_login_post_successful(client, setup_database):
#     with patch('project.main.send_verification_email') as mock_send_email, \
#     patch('project.main.captcha.validate', return_value=True) as mock_validate, \
#     patch('project.main.verify_password', return_value='hashed_password') as mock_verify_password :
#         verification_code = '561565644'
#         client.post('/registration', data={
#         'first_name': 'Test',
#         'last_name': 'User',
#         'email': 'alooo@example.com',
#         'password': 'password123',
#         'captcha': 'valid_captcha'
#     })
#         conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#         cur = conn.cursor()

#         cur.execute("UPDATE users SET verification_code = '561565644' WHERE email = %s", ('alooooooo@example.com',))
#         conn.commit()

#         client.post('/verify', data = {
#             'email': 'alooo@example.com',
#             'verification_code': '561565644'
#         })

#         cur.execute("UPDATE users SET verification_status = true WHERE email = %s", ('alooo@example.com',))
#         conn.commit()

#         responce = client.post('/login', data = {
#            'email': 'alooo@example.com',
#            'password': 'password123'
#         })
        
#         assert responce.status_code == 302
#         assert session.get('user_email') == 'alooo@example.com'
#         assert url_for('home') in responce.location
#         cur.close()

# def test_logout_get_successful(client, setup_database):
#     with patch('project.main.verify_password', return_value='hashed_password') as mock_verify_password :
#         conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#         cur = conn.cursor()
#         cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", ('Mozambik', 'Mizake', 'aloooooo@example.com', '123456789', '12588523'))
#         cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", ('12588523',))

#         conn.commit()

#         cur.close()
#         conn.close()

#         client.post('/login', data = {
#             'email': 'aloooooo@example.com',
#             'password': '123456789'
#         })

#         responce = client.get('/logout')

#         assert session.get('user_email') != 'aloooooo@example.com'
#         assert url_for('home') in responce.location
# def test_settings_get_successful(client, setup_database):
#     with patch('project.main.verify_password', return_value=True) as mock_verify_password :
#         prepare_settings()

#         client.post('/login', data = {
#             'email': 'aloooo@example.com',
#             'password': '123456789'
#         })

#         responce = client.get('/profile')

#         assert responce.status_code == 200
#         assert session.get('user_email') == 'aloooo@example.com'
#         assert b'Settings' in responce.data

# def test_delete_account_successful(client):
#     responce = client.post('/delete_account')

#     conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#     cur = conn.cursor()

#     is_deleted = cur.execute("SELECT verification_status FROM users WHERE email = %s", ('alooooooo@example.com',))

#     conn.commit()
    
#     assert is_deleted == None
#     assert session.get('user_email') != 'alooooooo@example.com'
#     url_for('login') in responce.location

#     cur.close()
#     conn.close()

# def test_delete_account_not_successful(client):
#     client.get('/logout')
#     responce = client.post('/delete_account')

#     assert responce.status_code == 200
#     # assert 'method_not_allowed' in responce.headers['Location'] 

# def test_settings_get_not_successful(client):
#     client.get('/logout')
#     responce = client.get('/profile')   

#     assert responce.status_code == 302
#     assert '/login' in responce.headers['Location']

# def prepare_settings():
#         conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#         cur = conn.cursor()
#         cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", ('Mozambik', 'Mizake', 'aloooo@example.com', '123456789', '12588523'))
#         cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", ('12588523',))

#         conn.commit()

#         cur.close()
#         conn.close()

# def test_update_settings_successful(client):
#     with patch('project.main.verify_password') as mock_verify_password:
#         conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#         cur = conn.cursor()
#         cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code, verification_status) VALUES (%s, %s, %s, %s, %s, %s)", ('Jonni', 'Sins', 'keleme@abv.bg', '123456789', '12588523', 'true'))
#         conn.commit()

#         client.post('/login', data={
#            'email': 'keleme@abv.bg',
#             'password': '123456789'
#         })

#         assert session.get('user_email') == 'keleme@abv.bg'

#         cur.execute("SELECT first_name FROM users WHERE email = %s", ('keleme@abv.bg',))
#         first_name = cur.fetchone()[0]
#         cur.execute("SELECT last_name FROM users WHERE email = %s", ('keleme@abv.bg',))
#         last_name = cur.fetchone()[0]
#         cur.execute("SELECT password FROM users WHERE email = %s", ('keleme@abv.bg',))
#         password_ = cur.fetchone()[0]

#         responce = client.post('/update_profile', data = {
#             'first-name': 'UPDATE',
#             'last-name': 'SETTINGS',
#             'email': 'UPDATEEMAIL@GMAIL.COM',
#             'password': '123456'
#         })   

#         cur.execute("SELECT first_name FROM users WHERE email = %s", ('UPDATEEMAIL@GMAIL.COM',))
#         changed_first_name = cur.fetchone()[0]
#         cur.execute("SELECT last_name FROM users WHERE email = %s", ('UPDATEEMAIL@GMAIL.COM',))
#         changed_last_name = cur.fetchone()[0]
#         cur.execute("SELECT password FROM users WHERE email = %s", ('UPDATEEMAIL@GMAIL.COM',))
#         changed_password = cur.fetchone()[0]

#         assert session.get('user_email') == 'UPDATEEMAIL@GMAIL.COM'  
#         assert first_name != changed_first_name
#         assert last_name != changed_last_name
#         assert password_ != changed_password
#         assert '/home' in responce.headers['Location']

# def test_home_authenticated(client):
#     with client.session_transaction() as sess:
#         sess['user_email'] = 'test@example.com'
    
#     response = client.get('/home')

#     assert response.status_code == 200
#     assert b'Home Page' in response.data

# def test_home_not_authenticated(client):
#     response = client.get('/home', follow_redirects=True)

#     assert response.status_code == 200
#     # assert response.location == 'http://localhost/login'

# def test_recover_password_successful(client):
#     with patch('project.main.send_recovey_password_email') as mock_send_recovery_password:
#         conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#         cur = conn.cursor()
#         cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code, verification_status) VALUES (%s, %s, %s, %s, %s, %s)", ('Jonni', 'Sins', 'illbe@abv.bg', '123456789', '12588523', 'true'))
#         conn.commit()

#         cur.execute("SELECT password FROM users WHERE email = %s", ('illbe@abv.bg',))
#         initial_password = cur.fetchone()[0]
#         conn.commit()

#         responce = client.post('/recover_password', data = {
#             'recovery_email': 'illbe@abv.bg'
#         })
        
#         cur.execute("SELECT password FROM users WHERE email = %s", ('illbe@abv.bg',))
#         changed_password = cur.fetchone()[0]

#         assert responce.status_code == 302
#         assert initial_password!= changed_password
#         assert '/login' in responce.headers['Location']

# def test_recover_password_sends_new_password_successful(client):
#     user_email = 'user@example.com'
#     new_passowrd = 'dsafdsfsafasgagjyt[;h]df'

#     with app.app_context():
#         with patch.object(mail, 'send') as mock_send:
#             send_recovey_password_email(user_email, new_passowrd)

#             mock_send.assert_called_once()

#             args, kwargs = mock_send.call_args
#             message = args[0]

#             assert message.subject == 'Recovery password'
#             assert message.recipients == [user_email]
#             assert 'Your recovery password: ' + new_passowrd

# def test_resend_verf_code_successful(client):
#     with patch('project.main.send_verification_email') as mock_send_email:
#         conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
#         cur = conn.cursor()
#         cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code, verification_status) VALUES (%s, %s, %s, %s, %s, %s)", ('Pedel', 'Sinsssss', 'ifabe@abv.bg', '123456789', '12588523', 'true'))
#         conn.commit()

#         cur.execute("SELECT verification_code FROM users WHERE email = %s", ('ifabe@abv.bg',))
#         initial_verification_code = cur.fetchone()[0]
#         conn.commit()

#         responce = client.post('/resend_verf_code', data = {
#             'resend_verf_code': 'ifabe@abv.bg'
#         })

#         cur.execute("SELECT verification_code FROM users WHERE email = %s", ('ifabe@abv.bg',))
#         changed_verification_code = cur.fetchone()[0]

#         assert responce.status_code == 302
#         assert initial_verification_code != changed_verification_code
#         assert '/verify' in responce.headers['Location']
