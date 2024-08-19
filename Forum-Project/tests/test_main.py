<<<<<<< HEAD
=======
import pytest
import bcrypt
from project.main import app as flask_app
from project.main import app
from project import sessions
import os
from decimal import Decimal
from datetime import timedelta, datetime
from project import utils
import uuid
from project.front_office import prepare_get_registration_return_data, check_post_registration_fields_data, post_verify_method, post_login_method, \
get_home_query_data, get_profile_data, post_update_profile, add_to_cart, get_cart_items_count, remove_from_cart, view_cart, merge_cart, \
get_cart_method_data, post_cart_method

# from project.main import add_to_cart_meth, add_to_cart, get_cart_items_count, get_cart_items_count, registration

from project.sessions import create_session, get_current_user

from werkzeug.datastructures import ImmutableMultiDict

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


def test_user_flow(setup_database):
    conn, cur = setup_database

    utils.trace("conn setup_database")
    utils.trace(conn)
    utils.trace("cur setup_database")
    utils.trace(cur)

    #GET PREPARE REGISTRATION

    first_captcha_number = 5
    second_captcha_number = 5

    cur.execute("INSERT INTO country_codes (name, code) VALUES (%s, %s) RETURNING *", ("Bulgaria", "+359"))
    result_country_codes = cur.fetchall()

    response_get = prepare_get_registration_return_data(cur, first_captcha_number, second_captcha_number)

    assert response_get['first_captcha_number'] == first_captcha_number
    assert response_get['second_captcha_number'] == second_captcha_number
    assert response_get['captcha_result'] == first_captcha_number + second_captcha_number
    assert response_get['captcha_id'] != None
    assert response_get['country_codes'] == result_country_codes

    # POEST PREPARE REGISTRATION

    cur.execute("INSERT INTO captcha_settings (name, value) VALUES (%s, %s)", ('max_captcha_attempts',2))
    cur.execute("INSERT INTO captcha_settings (name, value) VALUES (%s, %s)", ('captcha_timeout_minutes',10))

    user = {
        'first_name': 'Galin',
        'last_name': 'Petrov',
        'email': 'example@gmail.com',
        'password': '123456789',
        'confirm_password': '123456789',
        'address': 'Georgi Kirkov 56',
        'phone': '89403986',
        'gender': 'male',
        'captcha_id': response_get['captcha_id'],
        'captcha_': response_get['captcha_result'],
        'user_ip': '10.20.30.40'
    }
    hashed_password = "$GRT%#$3484fafsd*9v(ad"
    verification_code = "test_verification_code"

# todo
    response_post = check_post_registration_fields_data(cur=cur, first_name=user['first_name'], last_name=user['last_name'], 
                                                        email=user['email'], password_=user['password'], confirm_password_=user['confirm_password'], 
                                                        phone=user['phone'], gender=user['gender'], captcha_id=user['captcha_id'], captcha_=user['captcha_'],
                                                        user_ip=user['user_ip'],hashed_password=hashed_password, verification_code = verification_code, 
                                                        country_code=result_country_codes[0]['code'], address=user['address'])

    cur.execute("SELECT * FROM users WHERE email = %s", (user['email'],))
    registered_user_row = cur.fetchall()

    assert len(registered_user_row) == 1
    assert registered_user_row[0]['email'] == user['email']
    assert registered_user_row[0]['first_name'] == user['first_name']

    # POST VERIFICATION
    cur.execute("SELECT verification_status FROM users WHERE email = %s", (user['email'],))
    assert cur.fetchone()['verification_status'] == False

    responce_post_verify = post_verify_method(cur=cur, email=user['email'], verification_code=verification_code)

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (user['email'],))
    assert cur.fetchone()['verification_status'] == True

    # POST LOGIN

    with patch('project.utils.verify_password', return_value=True):
        post_login_method(cur=cur, email=user['email'], password_=hashed_password)

    # CREATE SESSION

    session_id = sessions.create_session(session_data=user['email'], cur=cur, conn=conn, is_front_office=True)

    assert session_id != None

    cur.execute("SELECT * FROM custom_sessions WHERE session_id = %s", (session_id,))
    custom_session_user_row = cur.fetchone()

    assert cur.rowcount == 1 

    assert custom_session_user_row['is_active'] == True
    assert custom_session_user_row['user_id'] == registered_user_row[0]['id']
    assert custom_session_user_row['expires_at'] != None

    # GET get_cart_items_count FOR LOGGED USER (doesn't have cart)

    cur.execute("INSERT INTO currencies (code, name, symbol) VALUES (%s, %s , %s) RETURNING *", ('BGN', 'Bulgarian lev', 'лв'))
    currencies_row = cur.fetchone()
    assert cur.rowcount == 1 

    cur.execute("""
                INSERT INTO settings (
                    vat, 
                    report_limitation_rows, 
                    send_email_template_background_color, 
                    send_email_template_text_align, 
                    send_email_template_border, 
                    send_email_template_border_collapse) 
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """, (25, 1000, '#19bcc8', 'right', 4, 'collapse'))

    settings_row = cur.fetchone()

    assert cur.rowcount == 1 

    cur.execute("""
                INSERT INTO products (
                    name,
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """, ('Product 1', 10, 15, 'Tools', currencies_row['id'], settings_row['id']))

    product_one_row = cur.fetchone()

    cur.execute("""
                INSERT INTO products (
                    name,
                    price, 
                    quantity, 
                    category, 
                    currency_id, 
                    vat_id) 
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """, ('Product 2', 20, 15, 'Garden', currencies_row['id'], settings_row['id']))

    product_two_row = cur.fetchone()

    response_get_cart_items_count = get_cart_items_count(cur=cur, conn=conn, user_id=registered_user_row[0]['id'])

    assert response_get_cart_items_count == 0

    # GET get_current_user FOR LOGGED USER

    response_get_current_user = get_current_user(session_id=custom_session_user_row['session_id'], cur=cur, conn=conn)

    assert response_get_current_user == user['email']

    # GET HOME PAGE

    fields = {
        'sort_by': 'id',
        'sort_order': 'asc',
        'price_min': '',
        'price_max': '',
        'page': 1,
        'per_page': 10,
        'product_name': '',
        'product_category': '',
        'products_per_page': 10,
        'offset': 0,
        'offset_front_office': 0,
    }

    with patch('project.utils.check_request_arg_fields', return_value=fields):
        response_get_home = get_home_query_data(cur=cur, sort_by=fields['sort_by'], sort_order=fields['sort_order'], products_per_page=fields['products_per_page'], 
                                            page=fields['page'], offset=fields['offset'], product_name=fields['product_name'], 
                                            product_category=fields['product_category'], price_min=fields['price_min'], price_max=fields['price_max'])

        assert len(response_get_home['products']) == 2
        assert response_get_home['total_pages'] == 1

    # GET USER PROFILE

    response_get_user_profile = get_profile_data(cur, user['email'])

    assert response_get_user_profile['country_codes'] == result_country_codes
    assert response_get_user_profile['first_name'] == user['first_name']
    assert response_get_user_profile['last_name'] == user['last_name']

    # POST UPDATE PROFILE 

    response_post_profile = post_update_profile(cur=cur, first_name=user['first_name'], 
                                                last_name=user['last_name'], email = "", 
                                                password_= "", address=user['address'], 
                                                phone="", country_code="", 
                                                gender="", session_id=session_id, conn=conn)

    assert response_post_profile['updated_fields_message'] == 'first name, last name, address'

    # ADD ITEM IN CART (CART WILL BE CREATED)

        # Not created cart for this user
    cur.execute("SELECT * FROM carts WHERE user_id = %s", (registered_user_row[0]['id'],))

    assert cur.fetchone() == None

        # Create cart and add item
    response_add_to_cart = add_to_cart(conn=conn, cur=cur, user_id=registered_user_row[0]['id'], 
                                        product_id=product_one_row['id'], quantity=2, 
                                        session_cookie_id=session_id)

        # Response message
    assert response_add_to_cart == "You successfully added item."

        # Created cart with items

    cur.execute("SELECT * FROM carts WHERE user_id = %s", (registered_user_row[0]['id'],))

    assert cur.fetchone() != None

    # ADD SAME ITEM IN CART (CART IS CREATED, JUST INCREASE THE QUANTITY FOR THE SAME PRODUCT)

    response_add_to_cart_same_item = add_to_cart(conn=conn, cur=cur, user_id=registered_user_row[0]['id'], 
                                        product_id=product_one_row['id'], quantity=3, 
                                        session_cookie_id=session_id)

    assert response_add_to_cart_same_item == "You successfully added same item, quantity was increased."

    # CHECK CART ITEMS COUNT AFTER ADDING ITEMS

    response_get_cart_items_count = get_cart_items_count(cur=cur, conn=conn, user_id=registered_user_row[0]['id'])

    assert response_get_cart_items_count == 1

    # REMOVE FROM CART

        # ADD SECOND PRODUCT TO THE CART
    response_add_to_cart_second_item = add_to_cart(conn=conn, cur=cur, user_id=registered_user_row[0]['id'], 
                                        product_id=product_two_row['id'], quantity=2, 
                                        session_cookie_id=session_id)

    response_get_cart_items_count = get_cart_items_count(cur=cur, conn=conn, user_id=registered_user_row[0]['id'])

    assert response_get_cart_items_count == 2

        # DELETE PRODUCT 2
    response_delete_items_from_cart = remove_from_cart(conn=conn, cur=cur, item_id=product_two_row['id'])

    assert response_delete_items_from_cart == "You successfully deleted item."

    response_delete = get_cart_items_count(cur=cur, conn=conn, user_id=registered_user_row[0]['id'])

    assert response_delete == 1

    # GET VIEW CART ITEMS

    response_get_view_cart = view_cart(conn=conn, cur=cur, user_id=registered_user_row[0]['id'])

        # WE HAVE PRODUCT 1 WITH QUANTITY -> 5
    assert response_get_view_cart == [[product_one_row['name'], product_one_row['price'], 5, product_one_row['id'], currencies_row['symbol'], settings_row['vat']]]

    # GET CART INTERFACE

    response_get_cart_interface = get_cart_method_data(cur=cur, conn=conn, authenticated_user=registered_user_row[0]['email'])

        # ALGORITHM FOR TOTAL SUM AND TOTAL SUM WITH VAT

    total_sum = 0

    total_sum_with_vat = 0

    for item in response_get_cart_interface['items']:
        vat_float = (Decimal(item['vat']) / 100)
        items_sum_without_vat = item['price'] * item['quantity']
        total_sum += items_sum_without_vat
        vat = items_sum_without_vat * vat_float
        total_sum_with_vat += items_sum_without_vat + vat

    assert response_get_cart_interface['items'] == [[product_one_row['name'], product_one_row['price'], 5, product_one_row['id'], currencies_row['symbol'], settings_row['vat']]]
    assert response_get_cart_interface['total_sum_with_vat'] == total_sum_with_vat
    assert response_get_cart_interface['total_sum'] == total_sum

    # POST CART

    response_post_cart = post_cart_method(cur=cur, email=user['email'], first_name=user['first_name'], 
                                        last_name=user['last_name'], town="Plovdiv", address=user['address'], 
                                        country_code=result_country_codes['code'], phone=user['phone'])

    utils.trace("response_post_cart")
    utils.trace(response_post_cart)

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
>>>>>>> dev
