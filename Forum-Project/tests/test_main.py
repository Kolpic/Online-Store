import pytest
import bcrypt
from unittest.mock import patch, MagicMock
import psycopg2

import os, io
import re

from decimal import Decimal
from datetime import timedelta, datetime
from project import utils
import uuid

from project.front_office import prepare_registration_data, registration, verify, login, \
prepare_home_data, prepare_profile_data, update_profile, add_to_cart, get_cart_items_count, remove_from_cart, view_cart, merge_cart, \
prepare_cart_data, cart, prepare_finish_payment_data, payment_method

from project.back_office import staff_login, prepare_error_logs_data, prepare_settings_data, captcha_settings, post_update_limitation_rows, vat_for_all_products, \
report_sales, prepare_crud_products_data, prepare_crud_add_product_data, crud_add_product, prepare_edit_product_data, edit_product, delete_product, prepare_crud_staff_data, \
prepare_add_role_staff_data, add_role_staff, add_staff, delete_crud_staff_role, prepare_crud_orders_data, prepare_crud_orders_add_order_data, crud_orders_add_order, \
prepare_crud_orders_edit_order_data, crud_orders_edit_order, delete_crud_orders_edit_order, prepare_crud_users_data, prepare_crud_users_add_user_data, \
crud_users_add_user, prepare_crud_users_edit_user_data, crud_users_edit_user, delete_crud_users_user, prepare_template_email_data, edit_email_template, \
prepare_role_permissions_data, role_permissions, download_report, edit_email_table

from project.utils import check_request_form_fields_post_method

from project.exception import WrongUserInputException
from project.sessions import create_session, get_current_user
from project import sessions
from project import config

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

    response_get = prepare_registration_data(cur, first_captcha_number, second_captcha_number)

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
    response_post = registration(cur=cur, first_name=user['first_name'], last_name=user['last_name'], 
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

    responce_post_verify = verify(cur=cur, email=user['email'], verification_code=verification_code)

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (user['email'],))
    assert cur.fetchone()['verification_status'] == True

    # POST LOGIN

    with patch('project.utils.verify_password', return_value=True):
        login(cur=cur, email=user['email'], password_=hashed_password)

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

    assert response_get_current_user['user_row']['data'] == user['email']

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
        response_get_home = prepare_home_data(cur=cur, sort_by=fields['sort_by'], sort_order=fields['sort_order'], products_per_page=fields['products_per_page'], 
                                            page=fields['page'], offset=fields['offset'], product_name=fields['product_name'], 
                                            product_category=fields['product_category'], price_min=fields['price_min'], price_max=fields['price_max'])

        assert len(response_get_home['products']) == 2
        assert response_get_home['total_pages'] == 1

    # GET USER PROFILE

    response_get_user_profile = prepare_profile_data(cur, user['email'])

    assert response_get_user_profile['country_codes'] == result_country_codes
    assert response_get_user_profile['first_name'] == user['first_name']
    assert response_get_user_profile['last_name'] == user['last_name']

    # POST UPDATE PROFILE 

    response_post_profile = update_profile(
        cur=cur, 
        first_name=user['first_name'], 
        last_name=user['last_name'], 
        email = "", 
        password_= "", 
        address=user['address'], 
        phone="", 
        country_code="", 
        gender="", 
        authenticated_user=response_get_current_user['user_row']['data'], 
        conn=conn)

    assert response_post_profile['updated_fields_message'] == 'first name, last name, address'

    # ADD ITEM IN CART (CART WILL BE CREATED)

    # Not created cart for this user
    cur.execute("SELECT * FROM carts WHERE user_id = %s", (registered_user_row[0]['id'],))

    assert cur.fetchone() == None

    # Create cart and add item
    response_add_to_cart = add_to_cart(
        conn=conn, 
        cur=cur, 
        user_id=registered_user_row[0]['id'], 
        product_id=product_one_row['id'], 
        quantity=2, 
        authenticated_user=response_get_current_user)

        # Response message
    assert response_add_to_cart == "You successfully added item."

        # Created cart with items

    cur.execute("SELECT * FROM carts WHERE user_id = %s", (registered_user_row[0]['id'],))

    assert cur.fetchone() != None

    # ADD SAME ITEM IN CART (CART IS CREATED, JUST INCREASE THE QUANTITY FOR THE SAME PRODUCT)

    response_add_to_cart_same_item = add_to_cart(
        conn=conn, 
        cur=cur, 
        user_id=registered_user_row[0]['id'], 
        product_id=product_one_row['id'], 
        quantity=3, 
        authenticated_user=response_get_current_user)

    assert response_add_to_cart_same_item == "You successfully added same item, quantity was increased."

    # CHECK CART ITEMS COUNT AFTER ADDING ITEMS

    response_get_cart_items_count = get_cart_items_count(cur=cur, conn=conn, user_id=registered_user_row[0]['id'])

    assert response_get_cart_items_count == 1

    # REMOVE FROM CART

        # ADD SECOND PRODUCT TO THE CART
    response_add_to_cart_second_item = add_to_cart(
        conn=conn, 
        cur=cur, 
        user_id=registered_user_row[0]['id'], 
        product_id=product_two_row['id'], 
        quantity=2, 
        authenticated_user=response_get_current_user)

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

    response_get_cart_interface = prepare_cart_data(cur=cur, conn=conn, authenticated_user=response_get_current_user)

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

    response_post_cart = cart(cur=cur, email=user['email'], first_name=user['first_name'], 
                                        last_name=user['last_name'], town="Plovdiv", address=user['address'], 
                                        country_code=result_country_codes[0]['code'], phone=user['phone'], 
                                        authenticated_user = response_get_current_user)

        # Check for decreasment in db quantity
    cur.execute("SELECT quantity FROM products WHERE id = %s", (product_one_row['id'],))

    assert cur.fetchone()[0] == 10

        # Check for deleted cart_items
    cur.execute("SELECT cart_id FROM carts WHERE user_id = %s", (registered_user_row[0]['id'],))
    cart_id = cur.fetchone()[0]

    cur.execute("SELECT * FROM cart_items WHERE cart_id = %s", (cart_id,))

    assert cur.fetchone() == None

        # Check if order was made from the cart_items
    cur.execute("SELECT * FROM order_items")
    order_items_row = cur.fetchone()

    assert order_items_row != None

    # GET PAYMENT DETAILS

    utils.trace("order_items_row")
    utils.trace(order_items_row)
    utils.trace("order_items_row['id']")
    utils.trace(order_items_row['id'])

    response_get_payment = prepare_finish_payment_data(cur=cur, authenticated_user=response_get_current_user, order_id=order_items_row['id'])

    assert response_get_payment != None

    # POST PAYMENT

    response_post_payment_method = payment_method(cur=cur, payment_amount=62.5, order_id=order_items_row['order_id'])

def test_user_updates_profiles_all_fails(setup_database):
    conn, cur = setup_database

    # PEPARE DATA

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

    cur.execute("""

                INSERT INTO users (
                    first_name,
                    last_name,
                    email,
                    password,
                    verification_status,
                    verification_code
                    )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """, ('Galin', 'Petrov', 'example@gmail.com', '123456', True, '489498efs6e4fsv46s4vsdv'))

    registered_user_row = cur.fetchone()

    assert cur.rowcount == 1

    session_id = sessions.create_session(session_data=registered_user_row['email'], cur=cur, conn=conn, is_front_office=True)

    assert session_id != None

    response_get_current_user = get_current_user(session_id=session_id, cur=cur, conn=conn)

    # POST UPDATE PROFILE WITH INVALID FIELDS 

    with pytest.raises(WrongUserInputException, match=r"First name must be between 3 and 50 letters and contain no special characters or digits"):
        update_profile(
            cur=cur,
            first_name="Pe",  # Invalid first name
            last_name="", 
            email="", 
            password_="", 
            address="", 
            phone="", 
            country_code="", 
            gender="", 
            authenticated_user=response_get_current_user, 
            conn=conn
        )

    with pytest.raises(WrongUserInputException, match=r"Last name must be between 3 and 50 letters"):
        update_profile(
            cur=cur,
            first_name="",  
            last_name="Pe", # Invalid last name
            email="", 
            password_="", 
            address="", 
            phone="", 
            country_code="", 
            gender="", 
            authenticated_user=response_get_current_user, 
            conn=conn
        )

    with pytest.raises(WrongUserInputException, match=r"Invalid email"):
        update_profile(
            cur=cur,
            first_name="",  
            last_name="", 
            email="example-gmail.com", # Invalid email name without @
            password_="", 
            address="", 
            phone="", 
            country_code="", 
            gender="", 
            authenticated_user=response_get_current_user, 
            conn=conn
        )

    with pytest.raises(WrongUserInputException, match=r"Password must be between 8 and 20 symbols"):
        update_profile(
            cur=cur,
            first_name="",  
            last_name="", 
            email="", 
            password_="1236", # Invalid password 
            address="", 
            phone="", 
            country_code="", 
            gender="", 
            authenticated_user=response_get_current_user, 
            conn=conn
        )

    with pytest.raises(WrongUserInputException, match=r"Address must be between 3 and 50 letters"):
        update_profile(
            cur=cur,
            first_name="",  
            last_name="", 
            email="", 
            password_="", 
            address="AZS", # Invalid address
            phone="", 
            country_code="", 
            gender="", 
            authenticated_user=response_get_current_user, 
            conn=conn
        )

    with pytest.raises(WrongUserInputException, match=r"Phone must be between 7 and 15 digits"):
        update_profile(
            cur=cur,
            first_name="",  
            last_name="", 
            email="", 
            password_="", 
            address="", 
            phone="123456", # Invalid phone
            country_code="", 
            gender="", 
            authenticated_user=response_get_current_user, 
            conn=conn
        )

    with pytest.raises(WrongUserInputException, match=r"Gender must be between male, female or other"):
        update_profile(
            cur=cur,
            first_name="",  
            last_name="", 
            email="", 
            password_="", 
            address="", 
            phone="",
            country_code="", 
            gender="Bee",  # Invalid gender
            authenticated_user=response_get_current_user, 
            conn=conn
        )

def test_user_updates_profiles_all_success(setup_database):
    conn, cur = setup_database

    # PEPARE DATA
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

    cur.execute("""
                INSERT INTO users (
                    first_name,
                    last_name,
                    email,
                    password,
                    verification_status,
                    verification_code
                    )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """, ('Galin', 'Petrov', 'example@gmail.com', '123456', True, '489498efs6e4fsv46s4vsdv'))

    registered_user_row = cur.fetchone()

    assert cur.rowcount == 1

    cur.execute("INSERT INTO country_codes (name, code) VALUES (%s, %s)", ("United Kingdom", "+44"))

    session_id = sessions.create_session(session_data=registered_user_row['email'], cur=cur, conn=conn, is_front_office=True)

    assert session_id != None

    response_get_current_user = get_current_user(session_id=session_id, cur=cur, conn=conn)

    # POST UPDATE PROFILE WITH VALID FIELDS 

    response_post_profile = update_profile(cur=cur, first_name="", 
                                                last_name="", email = "galin@gmail.com", 
                                                password_= "12345678910", address="Georgi KIrkov 56", 
                                                phone="8947039866", country_code="+44", 
                                                gender="male", authenticated_user=response_get_current_user['user_row']['data'], conn=conn)

    assert response_post_profile['updated_fields_message'] == 'email, password, address, phone, country code, gender'

def test_unauthenticated_user_flow(setup_database):
    conn, cur = setup_database

    # cur.execute("INSERT INTO country_codes (name, code) VALUES (%s, %s) RETURNING *", ("United Kingdom", "+44"))
    # currencies_row = cur.fetchone()

    cur.execute("INSERT INTO currencies (code, name, symbol) VALUES (%s, %s , %s) RETURNING *", ('BGN', 'Bulgarian lev', 'лв'))
    currencies_row = cur.fetchone()

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

    # ADD ITEM IN CART (CART WILL BE CREATED)

        # Not created cart 
    cur.execute("SELECT * FROM carts")

    assert cur.fetchone() == None

        # Create cart and add item
    response_add_to_cart = add_to_cart(conn=conn, cur=cur, user_id="TEST_SESSION_ID_UNAUTH_USER", 
                                        product_id=product_one_row['id'], quantity=2, 
                                        authenticated_user=None)

        # Response message
    assert response_add_to_cart == "You successfully added item."

        # Created cart with items

    cur.execute("SELECT * FROM carts WHERE session_id = %s", ('TEST_SESSION_ID_UNAUTH_USER',))

    assert cur.fetchone() != None

    response_add_to_cart_again = add_to_cart(conn=conn, cur=cur, user_id="TEST_SESSION_ID_UNAUTH_USER", 
                                        product_id=product_two_row['id'], quantity=1, 
                                        authenticated_user=None)

    assert response_add_to_cart == "You successfully added item."

    cur.execute("SELECT * FROM carts")
    cart_row = cur.fetchone()

    assert cart_row['user_id'] == None
    assert cart_row['session_id'] == 'TEST_SESSION_ID_UNAUTH_USER'

    # PEPARE DATA AFTER CLICKING CART -> USER HAVE TO LOG IN
    cur.execute("""
                INSERT INTO users (
                    first_name,
                    last_name,
                    email,
                    password,
                    verification_status,
                    verification_code
                    )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """, ('Galin', 'Petrov', 'example@gmail.com', '123456', True, '489498efs6e4fsv46s4vsdv'))

    registered_user_row = cur.fetchone()

    assert cur.rowcount == 1

    cur.execute("INSERT INTO country_codes (name, code) VALUES (%s, %s)", ("United Kingdom", "+44"))

    session_id = sessions.create_session(session_data=registered_user_row['email'], cur=cur, conn=conn, is_front_office=True)

    assert session_id != None

    response_merge_cart = merge_cart(conn=conn, cur=cur, user_id=registered_user_row['id'], session_id="TEST_SESSION_ID_UNAUTH_USER")

    cur.execute("SELECT * FROM carts")
    cart_row_after_login = cur.fetchone()

    assert cart_row_after_login['user_id'] == registered_user_row['id']
    assert cart_row_after_login['session_id'] == None

def test_registration_user_tries_too_many_times_to_register(setup_database):
    conn, cur = setup_database

    #GET PREPARE REGISTRATION

    first_captcha_number = 5
    second_captcha_number = 5

    cur.execute("INSERT INTO country_codes (name, code) VALUES (%s, %s) RETURNING *", ("Bulgaria", "+359"))
    result_country_codes = cur.fetchall()

    response_get = prepare_registration_data(cur, first_captcha_number, second_captcha_number)

    assert response_get['first_captcha_number'] == first_captcha_number
    assert response_get['second_captcha_number'] == second_captcha_number
    assert response_get['captcha_result'] == first_captcha_number + second_captcha_number
    assert response_get['captcha_id'] != None
    # assert response_get['country_codes'] == result_country_codes

    # POEST PREPARE REGISTRATION

    cur.execute("INSERT INTO captcha_settings (name, value) VALUES (%s, %s)", ('max_captcha_attempts', 2))
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
        'captcha_': 1,
        'user_ip': '10.20.30.40'
    }
    hashed_password = "$GRT%#$3484fafsd*9v(ad"
    verification_code = "test_verification_code"

    # FIRST ATTEMPTS FAILS

    with pytest.raises(WrongUserInputException, match=r"Invalid CAPTCHA. Please try again"):
        registration(
            cur=cur, 
            first_name=user['first_name'], 
            last_name=user['last_name'], 
            email=user['email'], 
            password_=user['password'], 
            confirm_password_=user['confirm_password'], 
            phone=user['phone'], 
            gender=user['gender'], 
            captcha_id=user['captcha_id'], 
            captcha_=user['captcha_'],
            user_ip=user['user_ip'],
            hashed_password=hashed_password, 
            verification_code = verification_code, 
            country_code=result_country_codes[0]['code'], 
            address=user['address'])

    # SECOND ATTEMPTS FAILS

    with pytest.raises(WrongUserInputException, match=r"Invalid CAPTCHA. Please try again"):
        registration(
            cur=cur, 
            first_name=user['first_name'], 
            last_name=user['last_name'], 
            email=user['email'], 
            password_=user['password'], 
            confirm_password_=user['confirm_password'], 
            phone=user['phone'], 
            gender=user['gender'], 
            captcha_id=user['captcha_id'], 
            captcha_=user['captcha_'],
            user_ip=user['user_ip'],
            hashed_password=hashed_password, 
            verification_code = verification_code, 
            country_code=result_country_codes[0]['code'], 
            address=user['address'])

    # THIRD ATTEMPT IS TIMEOUT

    with pytest.raises(WrongUserInputException, match=r"You typed wrong captcha several times, now you have timeout " + str(10) + " minutes"):
        registration(
            cur=cur, 
            first_name=user['first_name'], 
            last_name=user['last_name'], 
            email=user['email'], 
            password_=user['password'], 
            confirm_password_=user['confirm_password'], 
            phone=user['phone'], 
            gender=user['gender'], 
            captcha_id=user['captcha_id'], 
            captcha_=user['captcha_'],
            user_ip=user['user_ip'],
            hashed_password=hashed_password, 
            verification_code = verification_code, 
            country_code=result_country_codes[0]['code'], 
            address=user['address'])

class TestFile:
    def __init__(self, content, filename):
        self.stream = io.BytesIO(content)
        self.filename = filename

def test_back_office_staff_work_flow(setup_database):
    conn, cur = setup_database

    # GET STAFF LOGIN DATA

        # Try to log with non existing account
    with pytest.raises(WrongUserInputException, match=r"There is no registration with this staff username and password"):
        staff_login(
            cur=cur, 
            username="Galin", 
            password="123456789")

        # Insert new account 
    cur.execute("INSERT INTO staff (username, password) VALUES (%s, %s)", ("Galin", "123456789"))

        # Log with new account
    response_get_staff_login = staff_login(cur=cur, username="Galin", password="123456789")

    assert response_get_staff_login['username'] == "Galin"

    # GET EXCAPTION LOGS

    response_get_excaption_logs = prepare_error_logs_data(cur=cur, sort_by="id", sort_order="desc")

    assert cur.rowcount == 0

    cur.execute("""

                INSERT INTO exception_logs(
                    user_email,
                    exception_type,
                    message
                    )
                VALUES (%s, %s, %s)

                """, ("example@gmail.com", "WrongUserInputException", "Invalid CAPTCHA. Please try again"))

    response_get_excaption_logs = prepare_error_logs_data(cur=cur, sort_by="id", sort_order="desc")

    assert cur.rowcount == 1

    # GET SETTINGS 

    cur.execute("""

                INSERT INTO settings (
                    vat,
                    report_limitation_rows,
                    send_email_template_background_color,
                    send_email_template_text_align,
                    send_email_template_border, 
                    send_email_template_border_collapse
                    )
                VALUES (%s, %s, %s, %s, %s , %s)
                RETURNING *
                """, (25, 100, '#19bcc8', 'right', 4, 'collapse'))
    settings_row = cur.fetchone()

    response_get_settings = prepare_settings_data(cur)

    assert cur.rowcount == 1
    assert response_get_settings['limitation_rows'] == 100

    # POST CAPTCHA SETTINGS

    cur.executemany("""
                    INSERT INTO captcha_settings(
                        name,
                        value
                    )
                    VALUES (%s, %s)
                    """, [
                        ('max_captcha_attempts', 2),
                        ('captcha_timeout_minutes', 10)
                    ])

    response_post_captcha_attempts = captcha_settings(cur=cur, new_max_attempts=3, new_timeout_minutes=11)

    assert response_post_captcha_attempts['message'] == "You updated captcha attempts. You updated timeout minutes."

    cur.execute("SELECT * FROM captcha_settings")
    updated_captcha_settings_row = cur.fetchall()

    assert int(updated_captcha_settings_row[0]['value']) == 3
    assert int(updated_captcha_settings_row[1]['value']) == 11

    # POST LIMITATION ROWS

    response_post_limitation_rows = post_update_limitation_rows(cur=cur, limitation_rows=1000)

    cur.execute("SELECT report_limitation_rows FROM settings")

    assert response_post_limitation_rows['message'] == "You changed the limitation number of every report to: " + str(1000)
    assert cur.fetchone() == [1000]

    # POST VAT FOR ALL PRODUCTS

    response_post_vat = vat_for_all_products(cur=cur, vat_for_all_products=20)

    assert response_post_vat['message'] == "You changed the VAT for all products successfully"

    cur.execute("SELECT vat FROM settings")

    assert cur.fetchone() == [20]

    # POST REPORT SALES 

        # Add information to be generated report
    cur.execute("""

                INSERT INTO users (
                    first_name,
                    last_name,
                    email
                    )
                VALUES (%s, %s ,%s)
                RETURNING *

                """, ("Galin", "PETROV", "example@gmail.com"))
    registered_user_row = cur.fetchone()

    cur.execute("INSERT INTO currencies (code, name, symbol) VALUES (%s, %s , %s) RETURNING *", ('BGN', 'Bulgarian lev', 'лв'))
    currencies_row = cur.fetchone()

    cur.execute("""
                INSERT INTO products(
                    name,
                    price,
                    quantity,
                    category,
                    currency_id,
                    vat_id
                )
                VALUES 
                    (%s, %s, %s, %s, %s, %s),
                    (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """, (
                    "Product 1", 10.00, 100, 'Tools', currencies_row['id'], settings_row['id'],
                    "Product 2", 20.00, 100, 'Tools', currencies_row['id'], settings_row['id']
                ))

    products_rows = cur.fetchall()

    cur.execute("INSERT INTO orders (user_id, status, order_date) VALUES (%s, %s, %s) RETURNING *", (registered_user_row['id'], "Ready for Paying", datetime.now()))
    order_row = cur.fetchone()

    utils.trace("order_row")
    utils.trace(order_row)
    utils.trace("products_rows[0]")
    utils.trace(products_rows[0])
    utils.trace("products_rows[1]")
    utils.trace(products_rows[1])


    cur.executemany("""
                INSERT INTO order_items(
                    order_id,
                    product_id,
                    quantity,
                    price,
                    vat
                )
                VALUES (%s, %s, %s, %s, %s)
                """, [
                    (order_row[0], products_rows[0]['id'], 10, products_rows[0]['price'], settings_row['vat']),
                    (order_row[0], products_rows[1]['id'], 10, products_rows[1]['price'], settings_row['vat'])
                ])

    response_post_report = report_sales(
        cur=cur, 
        date_from="2024-01-01", 
        date_to="2024-10-01", 
        group_by="day", 
        status="Ready for Paying", 
        filter_by_status="Ready for Paying", 
        order_id="", 
        page="")

    assert response_post_report != None

    response_post_report_two = report_sales(
        cur=cur, 
        date_from="2024-01-01", 
        date_to="2025-10-01", 
        group_by="", 
        status="", 
        filter_by_status="", 
        order_id="", 
        page="")

    assert response_post_report_two != None

    # GET CRUD PRODUCTS

    response_get_crud_products = prepare_crud_products_data(
        cur=cur, 
        sort_by="id", 
        sort_order="desc", 
        price_min=5, 
        price_max=100)

    assert response_get_crud_products != None

    # GET ADD PRODUCT

    response_get_add_product = prepare_crud_add_product_data(cur)

    assert response_get_add_product['all_currencies'] != None
    assert response_get_add_product['categories'] == ['Tools']

    # POST ADD PRODUCT

    form_data = {
        'name': 'Added product',
        'price': 15.15,
        'currency_id': currencies_row['id'],
        'quantity': 100,
        'category': 'Tools',
    }

    image_file = TestFile(b"image content", 'ffrfrfrfrrfrfr.jpg')

    files_data = {
        'image' : image_file,
    }

    response_post_add_product = crud_add_product(cur=cur, form_data=form_data, files_data=files_data)

    assert response_post_add_product['message'] == "Item was added successfully"
    assert response_post_add_product['new_item_row'] != None

    cur.execute("SELECT id FROM products")

    assert len(cur.fetchall()) == 3

    # GET EDIT PRODUCT

    response_get_edit_product = prepare_edit_product_data(cur=cur, product_id=products_rows[0]['id'])

    cur.execute("SELECT * FROM products WHERE id = %s", (products_rows[0]['id'],))
    product_one_row = cur.fetchone()

    assert response_get_edit_product['product'] == product_one_row

    # POST EDIT PRODUCT 

    form_data = {
        'name': 'Product 1 Modified',
        'price': 10.11,
        'currency': currencies_row['id'],
        'quantity': 100,
        'category': 'Tools',
    }

    response_post_edit_product = edit_product(cur=cur, form_data=form_data, files_data="", product_id=products_rows[0]['id'])

    cur.execute("SELECT * FROM products WHERE id = %s", (products_rows[0]['id'],))
    modified_product_one = cur.fetchone()

    assert product_one_row != modified_product_one

    # DELETE PRODUCT 

    last_added_item = response_post_add_product['new_item_row']
    last_added_item_id = last_added_item['id']

    response_delete_product = delete_product(cur=cur, product_id=last_added_item_id)

    assert response_delete_product['message'] == "Product was set to be unavailable successful with id = " + str(last_added_item_id)

    cur.execute("SELECT * FROM products WHERE id = %s", (last_added_item_id,))
    deleted_product = cur.fetchone()

    assert deleted_product['quantity'] == 0

    # GET CRUD STAFF

    response_get_crud_staff = prepare_crud_staff_data(cur)

    assert response_get_crud_staff['relations'] == []

    # cur.execute("""

    #             INSERT INTO roles (
    #                 role_name
    #                 )
    #             VALUES (%s)
    #             RETURNING *

    #             """, ("Admin",))

        # cur.executemany("""
        #             INSERT INTO captcha_settings(
        #                 name,
        #                 value
        #             )
        #             VALUES (%s, %s)
        #             """, [
        #                 ('max_captcha_attempts', 2),
        #                 ('captcha_timeout_minutes', 10)
        #             ])

    cur.executemany("""

                INSERT INTO roles (
                    role_name
                    )
                VALUES (%s)

                """, [
                    ("Admin",),
                    ("Editor",),
                    ("Viwer",)
                ])

    cur.execute("SELECT * FROM roles")
    roles_row = cur.fetchall() # list of tuples -> [0][0]

    cur.execute("SELECT * FROM staff")
    staff_row = cur.fetchone() 

    cur.execute("""

            INSERT INTO staff_roles (
                staff_id,
                role_id
                )
            VALUES (%s, %s)
            RETURNING *

            """, (staff_row[0], roles_row[0][0]))

    response_get_crud_staff = prepare_crud_staff_data(cur)

    assert response_get_crud_staff['relations'] != []

    # GET ADD ROLE STAFF 

    response_get_add_role_staff = prepare_add_role_staff_data(cur=cur)

    assert response_get_add_role_staff['staff'] != []
    assert response_get_add_role_staff['roles'] != []

    # POST ADD ROLE STAFF

        # Give staff with id, role with id

    form_data = {
        'staff_id': staff_row[1],
        'role_id': roles_row[1][1],
    }

    response_post_add_staff_role = add_role_staff(cur=cur, form_data=form_data, files_data="")

    assert response_post_add_staff_role['message'] == "You successful gave a role: " + 'Editor' + " to user: " + 'Galin'

    # POST ADD STAFF

    form_data = {
        'username': "TEST_STAFF",
        'password': "123456789",
    }

    response_post_add_staff = add_staff(cur=cur, form_data=form_data, files_data="")

    assert response_post_add_staff['message'] == "You successful made new user with name: " + "TEST_STAFF"

    cur.execute("SELECT * FROM staff")
    all_staff_rows = cur.fetchall()

    assert cur.rowcount == 2

    # DELETE USER ROLE 

    cur.execute("SELECT * FROM staff_roles")
    staff_roles_row = cur.fetchall()

    assert cur.rowcount == 2

    response_delete_user_role = delete_crud_staff_role(cur=cur, staff_id=staff_row[0], role_id=roles_row[1][0])

    assert response_delete_user_role['message'] == "You successful deleted a role"

    cur.execute("SELECT * FROM staff_roles")
    staff_roles_row = cur.fetchall()

    assert cur.rowcount == 1

    # GET CRUD ORDERS 

    response_get_crud_orders = prepare_crud_orders_data(
        cur=cur, 
        sort_by="id", 
        sort_order="asc", 
        price_min=5, 
        price_max=500, 
        order_by_id="", 
        date_from="2023-01-01", 
        date_to="2025-01-01", 
        status="Ready for Paying", 
        page=1, 
        per_page=50, 
        offset=0)

    utils.trace("response_get_crud_orders")
    utils.trace(response_get_crud_orders['orders'])

    assert response_get_crud_orders['orders'] != None

    # GET CRUD ORDERS ADD

    response_get_crud_orders_add = prepare_crud_orders_add_order_data(cur)

    assert response_get_crud_orders_add['statuses'] == [['Ready for Paying']]

    # POST CRUD ORDERS ADD

    form_data = {
        'user_id': registered_user_row['id'],
        'status': 'Ready for Paying',
        'order_date': datetime.now().strftime("%Y-%m-%dT%H:%M"),
        'product_id': products_rows[0]['id'],
        'price': 22.22,
        'quantity': 2,
        'vat': 20,
    }

    response_post_crud_add_order = crud_orders_add_order(cur=cur, form_data=form_data, files_data="")

    cur.execute("SELECT * FROM orders")
    all_orders = cur.fetchall()

    assert cur.rowcount == 2

    cur.execute("SELECT * FROM order_items")
    all_order_items = cur.fetchall()

    assert cur.rowcount == 3

    # GET EDIT ORDER

    # cur.execute("SELECT * FROM order_items WHERE order_id = %s", (all_orders[0][0],))
    cur.execute("""

            SELECT 
                p.id, 
                p.name, 
                oi.quantity, 
                oi.price, 
                sum(oi.quantity * oi.price) AS total_price,
                c.symbol,
                oi.vat
            FROM order_items                AS oi 
                JOIN products               AS p ON oi.product_id = p.id 
                JOIN currencies             AS c ON p.currency_id = c.id
            WHERE order_id = %s 
            GROUP BY 
                p.id, 
                p.name, 
                oi.quantity, 
                oi.price, 
                c.symbol,
                oi.vat

            """, (all_orders[0][0],))

    order_items_row = cur.fetchall()

    response_get_edit_order = prepare_crud_orders_edit_order_data(cur=cur, order_id=all_orders[0][0])

    assert response_get_edit_order['products_from_order'] == order_items_row

    # POST EDIT ORDER 

    form_data = {
        'status': 'Paid',
        'order_date': datetime.now(),
    }

    response_post_edit_order = crud_orders_edit_order(cur=cur, order_id=all_orders[0][0], form_data=form_data, files_data="")

    assert response_post_edit_order['message'] == "Order was updated successfully with id = " + str(all_orders[0][0])

    cur.execute("SELECT * FROM orders WHERE order_id = %s", (all_orders[0][0],))
    edited_order_row = cur.fetchone()

    assert edited_order_row['status'] == 'Paid'

    # DELETE ORDER

    response_delete_order = delete_crud_orders_edit_order(cur=cur, order_id=all_orders[0][0])

    assert response_delete_order['message'] == "You successful deleted a  order with id: " + str(all_orders[0][0])

    cur.execute("SELECT * FROM orders")
    all_orders_after_delete = cur.fetchall()

    assert cur.rowcount == 1

    # GET CRUD USERS

    response_get_crud_users = prepare_crud_users_data(cur=cur, email="", user_by_id="", status="", sort_by="id", sort_order="asc")

    assert response_get_crud_users != None

    # GET CRUD USERS ADD USER

    response_get_crud_users_add_user = prepare_crud_users_add_user_data(cur=cur)

    assert response_get_crud_users_add_user['statuses'] != None

    # POST CRUD USERS ADD USER

    form_data = {
        'first_name': 'Galin',
        'last_name': 'Petrov',
        'email': 'galin@gmail.com',
        'password': '123456789',
        'verification_code': 'daefff4r58ea4gferg',
        'verification_status': True,
    }

    response_post_crud_add_user = crud_users_add_user(cur=cur, form_data=form_data, files_data="")

    cur.execute("SELECT * FROM  users")
    users_row = cur.fetchall()
    created_user_id = users_row[1]['id']

    assert cur.rowcount == 2

    assert response_post_crud_add_user['message'] == "You successfully added new user with id: " + str(created_user_id)

    # GET CRUD USERS EDIT USER

    response_get_crud_users_edit_user = prepare_crud_users_edit_user_data(cur=cur, user_id=created_user_id)

    assert response_get_crud_users_edit_user['first_name'] == form_data['first_name']
    assert response_get_crud_users_edit_user['last_name'] == form_data['last_name']
    assert response_get_crud_users_edit_user['email'] == form_data['email']

    # POST CRUD USERS EDIT USER

    form_data = {
        'first_name': 'Galinn',
        'last_name': 'Petrovv',
        'email': 'galinCHooo@gmail.com',
        'verification_status': True,
    }

    response_post_crud_users_edit_user = crud_users_edit_user(cur=cur, form_data=form_data, files_data="", user_id=created_user_id)

    cur.execute("SELECT * FROM users WHERE id = %s", (created_user_id,))
    current_user = cur.fetchone()

    assert current_user['first_name'] == form_data['first_name']
    assert current_user['last_name'] == form_data['last_name']
    assert current_user['email'] == form_data['email']

    assert response_post_crud_users_edit_user['message'] == "You successfully edited user with id: " + str(created_user_id)

    # DELETE CRUD USERS USER

    response_delete_crud_users = delete_crud_users_user(cur=cur, user_id=created_user_id)

    assert response_delete_crud_users['message'] == "You successfully deleted user with id: " + str(created_user_id)

    cur.execute("SELECT * FROM users")
    users_row = cur.fetchall()

    assert cur.rowcount == 1

    # GET TEMPLATE TABLES

    cur.executemany("""

            INSERT INTO email_template (
                name,
                subject,
                body,
                sender
                )
            VALUES (%s, %s, %s, %s)

            """, [
                ("Payment Email", "Completed Payment Email", "Hello {first_name} {last_name}, you just bought: {products} and the information about the order is : {shipping_details}", "galincho112@gmail.com"),
                ("Verification Email", "Email Verification", "Hello {first_name} {last_name} ! Please insert the verification code in the form: {verification_code}", " galincho112@gmail.com"),
                ("Purchase Email", "Completed Purchase Email", "Hi again {first_name}  {last_name}. You just purchased: {cart} and the details you provided for shipment are: {shipping_details}","galincho112@gmail.com")
            ])

    response_get_template_tables = prepare_template_email_data(cur)

    assert response_get_template_tables != None

    # POST TEMPLATE TABLES

    form_data = {
        'subject': 'Email Verification',
        'body': 'Hello {first_name} {last_name} ! Please insert the verification code in the form: {verification_code} FHSUOFVUHOSVHSDOIVJHSDI',
    }

    response_post_email_template = edit_email_template(cur=cur, template_name='Verification Email', form_data=form_data, files_data="")

    cur.execute("SELECT * FROM email_template WHERE name = %s", ("Verification Email",))
    email_template_row_verification_email = cur.fetchone()

    assert email_template_row_verification_email['body'] == form_data['body']

    # GET ROLE PERMISSIONS

    # utils.trace("roles_row")
    # utils.trace(roles_row)
    # utils.trace("staff_row")
    # utils.trace(staff_row)

    cur.executemany("""

            INSERT INTO permissions (
                permission_name,
                interface
                )
            VALUES (%s, %s)

            """, [
                ("create", "CRUD Products"),
                ("update", "CRUD Products"),
                ("delete", "CRUD Products"),
                ("read", "CRUD Products"),
                ("create", "Logs"),
                ("update", "Logs"),
                ("delete", "Logs"),
                ("read", "Logs")
            ])

    cur.execute("SELECT * FROM permissions")
    permissions_row = cur.fetchall()

    # utils.trace("permissions_row")
    # utils.trace(permissions_row)

    cur.executemany("""

            INSERT INTO role_permissions (
                role_id,
                permission_id
                )
            VALUES (%s, %s)

            """, [
                (roles_row[0][0], permissions_row[0][0]),
                (roles_row[0][0], permissions_row[1][0])
            ])

    cur.execute("SELECT * FROM role_permissions")
    role_permissions_row = cur.fetchall()

    # utils.trace("role_permissions_row")
    # utils.trace(role_permissions_row)

    cur.execute("SELECT * FROM staff_roles")
    staff_roles_row = cur.fetchall()

    # utils.trace("staff_roles_row")
    # utils.trace(staff_roles_row)

    cur.execute("SELECT DISTINCT interface FROM permissions ORDER BY interface ASC")
    interfaces = []
    for interface in cur.fetchall():
        interfaces.append(interface[0])

    response_get_role_permissions = prepare_role_permissions_data(cur=cur, role="role_permissions", selected_role=roles_row[0][0], interfaces=interfaces)

    assert response_get_role_permissions != None

    # POST ROLE PERMISSIONS

    form_data = {
        'role': '1',
        'Logs_read': 'on',
        'Logs_update': 'on',
        'CRUD Products_read': 'on',
        'CRUD Products_update': 'on',
    }

    response_post_role_permissions = role_permissions(cur=cur, role_id=roles_row[0][0], form_data=form_data, interfaces=interfaces)

    assert response_post_role_permissions['message'] == f'You successfully updated permissions for role: {roles_row[0][1]}'

    # POST EDIT EMAIL TABLE
    # '#19bcc8', 'right', 4, 'collapse'

    cur.execute("SELECT * FROM settings")
    settings_row = cur.fetchall()

    response_post_edit_email_table = edit_email_table(
        cur = cur, 
        background_color = "#19bcc7", 
        text_align = "left", 
        border = 5, 
        border_collapse = "collapse")

    cur.execute("SELECT * FROM settings")
    settings_row_after_edit = cur.fetchall()

    assert settings_row[0][3] != settings_row_after_edit[0][3]
    assert settings_row[0][4] != settings_row_after_edit[0][4]
    assert settings_row[0][5] != settings_row_after_edit[0][5]

    # DOWNLOAD REPORT WITHOUT GENERATED GSON

    cur.execute("SELECT * FROM orders")
    orders_row = cur.fetchall()

    form_data = {
        'date_from': '',
        'date_to': '',
        'format': 'csv',
    }

    with patch('project.back_office.psycopg2.connect', return_value = conn):
        generator = download_report(form_data=form_data)()

        result = ''.join(generator)

    expected_output = (
        'Date,Order ID,Customer Name,Total Price,Status\r\n'                       # Header
        f'{datetime.now().strftime("%Y-%m-%d")},{orders_row[0][0]},Ready for Paying,Galin,44.44\r\n'    # First row
    )

def test_custom_request_form_fields_validator():

    form_data = {
        'first_name': 'J',
        'last_name': 'Petrov',
        'email': 'galin@example.com',
        'password': 'validPass123',
        'confirm_password': 'validPass123',
        'country_code': '+359',
        'phone': '1234567890',
        'gender': 'male'
    }

    path = '/registration'

    url_fields_mapper = {
        '/registration': {
            'first_name': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 50 and re.match(r'^[A-Za-z]+$', x)), "First name must be between 3 and 50 letters and contain no special characters or digits")]},
            'last_name': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 50 and re.match(r'^[A-Za-z]+$', x)), "Last name must be between 3 and 50 letters and contain no special characters or digits")]},
            'email': {'type': str, 'required': True, 'conditions': [((lambda x: re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', x)), "Email is not valid")]},
            'password': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 8 and len(x) <= 20), "Password must be between 8 and 20 symbols")]},
            'confirm_password': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 8 and len(x) <= 20), "Password and Confirm Password fields are different")]},
            'country_code': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 1 and len(x) <= 4), "Invalid country code")]},
            'phone': {'type': str, 'required': True, 'conditions': [((lambda x: re.fullmatch(r'^\d{7,15}$', x)), "Phone number format is not valid. The number should be between 7 and 15 digits")]},
            'gender': {'type': str, 'required': True, 'conditions': [((lambda x: x in ['male', 'female', 'other']), "Gender must be Male, Female, or Other")]},
        },
        r'/verify':{
            'email': {'type': str, 'required': True, 'conditions': [((lambda x: re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', x)), "Email is not valid")]},
            'verification_code': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) == 24), "Verification code is not valid")]},
        },
        r'/login': {
            'email': {'type': str, 'required': True, 'conditions': [((lambda x: re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', x)), "Email is not valid")]},
            'password': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 8 and len(x) <= 20), "Password must be between 8 and 20 symbols")]},
        },
        r'/update_profile': {
            'first_name': {'type': str, 'required': False, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 50 and re.match(r'^[A-Za-z]+$', x)), "First name must be between 3 and 50 symbols")]},
            'last_name': {'type': str, 'required': False, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 50 and re.match(r'^[A-Za-z]+$', x)), "Last name must be between 3 and 50 symbols")]},
            'email': {'type': str, 'required': False, 'conditions': [((lambda x: re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', x)), "Email is not valid")]},
            'password': {'type': str, 'required': False, 'conditions': [((lambda x: len(x) >= 8 and len(x) <= 20), "Password must be between 8 and 20 symbols")]},
            'address': {'type': str, 'required': False, 'conditions': [((lambda x: len(x) >= 5 and len(x) <= 50), "Address must be between 5 and 50 symbols")]},
            'phone': {'type': str, 'required': False, 'conditions': [((lambda x: re.fullmatch(r'^\d{7,15}$', x)), "Phone number format is not valid. The number should be between 7 and 15 digits")]},
            'country_code': {'type': str, 'required': False, 'conditions': [((lambda x: len(x) >= 1 and len(x) <= 4), "Invalid country code")]},
            'gender': {'type': str, 'required': False, 'conditions': [((lambda x: x == 'male' or x == 'female' or x == 'other'), "Gender must be Male of Female or Prefere not to say")]},
        },
        r'/cart': {
            'email': {'type': str, 'required': True, 'conditions': [((lambda x: re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', x)), "Email is not valid")]},
            'first_name': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 50 and re.match(r'^[A-Za-z]+$', x)), "First name must be between 3 and 50 symbols")]},
            'last_name': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 50 and re.match(r'^[A-Za-z]+$', x)), "Last name must be between 3 and 50 symbols")]},
            'town': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 20), "Town must be between 3 and 20 symbols")]},
            'address': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 5 and len(x) <= 50), "Address must be between 5 and 50 symbols")]},
            'country_code': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 1 and len(x) <= 4), "Invalid country code")]},
            'phone': {'type': str, 'required': True, 'conditions': [((lambda x: re.fullmatch(r'^\d{7,15}$', x)), "Phone number format is not valid. The number should be between 7 and 15 digits")]},
        }
    }

    with pytest.raises(WrongUserInputException, match=r"First name must be between 3 and 50 letters and contain no special characters or digits"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'first_name': 'Galin',
        'last_name': 'P',
        'email': 'galin@example.com',
        'password': 'validPass123',
        'confirm_password': 'validPass123',
        'country_code': '+359',
        'phone': '1234567890',
        'gender': 'male'
    }

    with pytest.raises(WrongUserInputException, match=r"Last name must be between 3 and 50 letters and contain no special characters or digits"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'first_name': 'Galin',
        'last_name': 'Petrov',
        'email': 'galinexample.com',
        'password': 'validPass123',
        'confirm_password': 'validPass123',
        'country_code': '+359',
        'phone': '1234567890',
        'gender': 'male'
    }

    with pytest.raises(WrongUserInputException, match=r"Email is not valid"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'first_name': 'Galin',
        'last_name': 'Petrov',
        'email': 'galin@example.com',
        'password': 'www',
        'confirm_password': 'validPass123',
        'country_code': '+359',
        'phone': '1234567890',
        'gender': 'male'
    }

    with pytest.raises(WrongUserInputException, match=r"Password must be between 8 and 20 symbols"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'first_name': 'Galin',
        'last_name': 'Petrov',
        'email': 'galin@example.com',
        'password': 'wwwwwwww',
        'confirm_password': 'vali',
        'country_code': '+359',
        'phone': '1234567890',
        'gender': 'male'
    }

    with pytest.raises(WrongUserInputException, match=r"Password and Confirm Password fields are different"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'first_name': 'Galin',
        'last_name': 'Petrov',
        'email': 'galin@example.com',
        'password': 'ds1dsds41d5s',
        'confirm_password': 'ds1dsds41d5s',
        'country_code': '+359894',
        'phone': '1234567890',
        'gender': 'male'
    }

    with pytest.raises(WrongUserInputException, match=r"Invalid country code"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'first_name': 'Galin',
        'last_name': 'Petrov',
        'email': 'galin@example.com',
        'password': 'ds1dsds41d5s',
        'confirm_password': 'ds1dsds41d5s',
        'country_code': '+359',
        'phone': '123456789012345678901234567890',
        'gender': 'male'
    }

    with pytest.raises(WrongUserInputException, match=r"Phone number format is not valid. The number should be between 7 and 15 digits"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'first_name': 'Galin',
        'last_name': 'Petrov',
        'email': 'galin@example.com',
        'password': 'ds1dsds41d5s',
        'confirm_password': 'ds1dsds41d5s',
        'country_code': '+359',
        'phone': '1234567890',
        'gender': 'bee'
    }

    with pytest.raises(WrongUserInputException, match=r"Gender must be Male, Female, or Other"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'first_name': "",
        'last_name': 'Petrov',
        'email': 'galin@example.com',
        'password': 'ds1dsds41d5s',
        'confirm_password': 'ds1dsds41d5s',
        'country_code': '+359',
        'phone': '1234567890',
        'gender': 'bee'
    }

    with pytest.raises(WrongUserInputException, match=r"first_name is required"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    path = '/verify'

    form_data = {
        'email': 'galinexample.com',
        'verification_code': '123456789ghjklazerty123',
    }

    with pytest.raises(WrongUserInputException, match=r"Email is not valid"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    form_data = {
        'email': 'galin@example.com',
        'verification_code': '123456789ghjklazerty',
    }

    with pytest.raises(WrongUserInputException, match=r"Verification code is not valid"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)

    path = '/login'

    form_data = {
        'email': 'galinexample.com',
        'password': '123456789',
    }

    with pytest.raises(WrongUserInputException, match=r"Email is not valid"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)
    
    form_data = {
        'email': 'galin@example.com',
        'password': '1234567',
    }

    with pytest.raises(WrongUserInputException, match=r"Password must be between 8 and 20 symbols"):
        check_request_form_fields_post_method(path, url_fields_mapper, form_data)