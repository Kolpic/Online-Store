from flask import Flask, request, render_template, redirect, url_for, session, abort, Response, jsonify, flash, make_response, request, stream_with_context, send_file
from flask_mail import Mail, Message
from flask_migrate import Migrate
from decimal import Decimal
import psycopg2, os, re, secrets, psycopg2.extras, uuid
from psycopg2 import sql
import json
from werkzeug.utils import secure_filename
import csv
from PIL import Image
import io
import bcrypt
import datetime, random, calendar
from datetime import timedelta, datetime
import logging
from openpyxl import Workbook
from io import BytesIO
# import os
from project import config, exception
from flask_session_captcha import FlaskSessionCaptcha
# from flask_sessionstore import Session
from flask_session import Session
from project import utils
from project import front_office, back_office
from project import send_mail
from project import sessions
from project import cache_impl
from .models import User
from sqlalchemy import or_
import traceback
import itertools
import time
import uuid

# https://stackoverflow.com/questions/23327293/flask-raises-templatenotfound-error-even-though-template-file-exists
app = Flask(__name__)
# MAIL Configuration
app.secret_key = secrets.token_hex(16)
app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USE_SSL'] = config.MAIL_USE_SSL

mail = Mail(app)

# Database configuration migration
app.config['SQLALCHEMY_DATABASE_URI'] = config.postgres_db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from .models import db
db.init_app(app)
migrate = Migrate(app, db)

# Dev database
database = config.database
user = config.user
password = config.password
host = config.host

ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # Maximum file size in bytes (e.g., 10MB)

app.add_url_rule("/", defaults={'path':''}, endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])  
app.add_url_rule("/<path:path>", endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])
app.add_url_rule("/<username>/<path:path>", endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])

def assertIsProvidedMethodsTrue(*args):
    if len(args) == 2:
        if not request.method == 'GET' and not request.method == 'POST': raise exception.MethodNotAllowed("You tried to asscess resources, you don't have permission for")
    else:
        method_type = str(args[0]).upper()
        if not request.method == method_type: raise exception.MethodNotAllowed("You tried to asscess resources, you don't have permission for")

def refresh_captcha(conn, cur):
    first_captcha_number = random.randint(0, 100)
    second_captcha_number = random.randint(0, 100)
    cur.execute("INSERT INTO captcha(first_number, second_number, result) VALUES (%s, %s, %s) RETURNING id", 
                (first_captcha_number, second_captcha_number, first_captcha_number + second_captcha_number))
    # conn.commit()
    captcha_id = cur.fetchone()[0]
    session["captcha_id"] = captcha_id

    return jsonify({'first': first_captcha_number, 'second': second_captcha_number, 'captcha_id': captcha_id})

def handle_image_field(image_data):
    print("image_data.filename.split('.')[-1]", flush=True)
    print(image_data.filename.split('.')[-1], flush=True)

    utils.AssertUser(image_data.filename.split('.')[-1] in FIELD_CONFIG['CRUD Products']['create']['image']['conditions_image'], "Invalid image file extension (must be one of jpg, jpeg, png)")
    filename = secure_filename(image_data.filename)
    image_data = validate_image_size(image_data.stream)
    return image_data

# Configuration for each field
FIELD_CONFIG = {
    'CRUD Products': {
        'create': {
            'name': {'type': str, 'required': True},
            'price': {'type': float, 'required': True, 'conditions': [(lambda x: x > 0, "Price must be a positive number")]},
            'quantity': {'type': int, 'required': True, 'conditions': [(lambda x: x > 0, "Quantity must be a positive number")]},
            'category': {'type': str, 'required': True},
            'image': {'type': 'file', 'required': True, 'conditions_image': ALLOWED_EXTENSIONS,'handler': handle_image_field},
            'currency_id': {'type': int, 'required': True},
        },
        'edit': {
            'name': {'type': str, 'required': True},
            'price': {'type': float, 'required': True, 'conditions': [(lambda x: x > 0, "Price must be a positive number")]},
            'quantity': {'type': int, 'required': True, 'conditions': [(lambda x: x >= 0, "Quantity must not be negative")]},
            'category': {'type': str, 'required': True},
            'currency': {'type': int, 'required': True},
        }
    },
    'Staff roles': {
        'create_staff_roles': {
            'staff_id': {'type': str, 'required': True},
            'role_id': {'type': str, 'required': True}
        },
        'create_staff':{
            'username': {'type': str, 'required': True, 'conditions': [(lambda x: len(x.split(' ')) == 1, "You have to type name without intervals")]},
            'password': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) <= 20, "Password must be below 20 symbols")]},
        }
    },
    'CRUD Orders': {
        'create': {
            'orders': {
                'user_id': {'type': int, 'required': True, 'conditions': [(lambda x: x > 0, "User id must be possitive")]},
                'status': {'type': str, 'required': True},
                'order_date': {'type': datetime, 'required': True, 'conditions': [(lambda x: datetime.strptime(x, '%Y-%m-%dT%H:%M') <= datetime.now(), "You can't make orders with future date")]},
            },
            'order_items': {
                'product_id': {'type': int, 'required': True, 'conditions': [(lambda x: x > 0, "Product id must be possitive")]},
                'price': {'type': float, 'required': True, 'conditions': [(lambda x: x > 0, "Price must be possitive")]},
                'quantity': {'type': int, 'required': True, 'conditions': [(lambda x: x > 0, "Quantity must be possitive")]},
            }
        },
        'edit': {
            'status': {'type': str, 'required': True},
            'order_date': {'type': datetime, 'required': True},
        }
    },
    'CRUD Users': {
        'create': {
            'first_name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=4 and len(x) <= 15, "First name must be al least 4 symbols long and under 16 symbols")]},
            'last_name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >= 4 and len(x) <= 15, "Last name must be al least 4 symbols long and under 16 symbols")]},
            'email': {'type': str, 'required': True, 'conditions': [(lambda x: '@' in x, "Invalid email")]},
            'password': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=4 and len(x) <= 20, "Password must be between 4 and 20 symbols")]},
            # 'confirm_password': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=4 and len(x) <= 20, "Password must be between 4 and 20 symbols")]},
            'verification_code': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=10 and len(x) <= 20, "Verification code must be between 10 and 20 symbols")] },
            'verification_status': {'type': bool, 'required': True, 'conditions': [(lambda x: x == True or x == False, "The status can be only true or false")]}
        },
        'edit': {
            'first_name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=4 and len(x) <= 15, "First name must be al least 4 symbols long and under 16 symbols")]},
            'last_name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >= 4 and len(x) <= 15, "Last name must be al least 4 symbols long and under 16 symbols")]},
            'email': {'type': str, 'required': True, 'conditions': [(lambda x: '@' in x, "Invalid email")]},
            'verification_status': {'type': bool, 'required': True, 'conditions': [(lambda x: x == True or x == False, "The status can be only true or false")]}
        }
    },
    'Template email': {
        'edit': {
            'subject': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 5 and len(x) <= 30, "Email subject should be between 5 and 30 symbols")]},
            'body': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 10 and len(x) <= 255, "Email subject should be under 255 symbols")]},
        }
    },
    'Template email purchase': {
        'edit': {
            'subject_purchase': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 5 and len(x) <= 30, "Email subject should be between 5 and 30 symbols")]},
            'body_purchase': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 10 and len(x) <= 255, "Email subject should be under 255 symbols")]},
        }
    },
    'Template email payment': {
        'edit': {
            'subject_payment': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 5 and len(x) <= 30, "Email subject should be between 5 and 30 symbols")]},
            'body_payment': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 10 and len(x) <= 255, "Email subject should be under 255 symbols")]},
        }
    }
}

# special_field_handlers = {
#     'image': lambda field_data: handle_image_field(field_data)
# }

def get_field_config(interface, method):
    return FIELD_CONFIG.get(interface, {}).get(method, {}) # return the right fields for the interface with the metod we provided

def validate_field(field_name, value, config):

    print("==== Entered validate_field method ======",flush=True)
    print(isinstance(value, str), flush=True)

    utils.AssertUser(config['required'] and value, f"You must add information in every field: {field_name}")

    if 'type' in config and config['type'] in [float, int, bool]:
        print("==== Entered type validation ======",flush=True)
        try:
            value = config['type'](value)
        except ValueError:
            raise ValueError(f"{field_name} is not a valid {config['type'].__name__}")

    if 'conditions' in config:
        print("==== Entered conditions validation ======",flush=True)
        for condition, message in config['conditions']:
            print("==== Entered conditions validation ======",flush=True)
            print("condition", flush=True)
            print(condition, flush=True)
            print("value", flush=True)
            print(value, flush=True)
            utils.AssertUser(condition(value), message)

    if field_name == 'password':
        value = utils.hash_password(value)

    return value

def process_form(interface, method):
    form_data = {}
    nested_data = {}
    nested_flag = False

    field_config = get_field_config(interface, method)

    print("field_config", flush=True)
    print(field_config, flush=True)

    for section, config_dict in field_config.items():
        nested_data[section] = {}

        print("section", flush=True)
        print(section, flush=True)
        print("config_dict", flush=True)
        print(config_dict, flush=True)
        print("field_config.items()", flush=True)
        print(field_config.items(), flush=True)

        if section != 'orders' and section != 'order_items':
            print("No nested for", flush=True)
            value = None

            if config_dict['type'] == 'file':
                value = request.files.get(section)
                value = config_dict['handler'](value)
            else:
                value = request.form.get(section)

            print("section", flush=True)
            print(section, flush=True)
            print("value", flush=True)
            print(value, flush=True)
            print("config_dict", flush=True)
            print(config_dict, flush=True)

            validated_value = validate_field(section, value, config_dict)
            form_data[section] = validated_value

            print("form_data[section]", flush=True)
            print(form_data[section], flush=True)
        else:
            print("Nested for", flush=True)
            for field, config in config_dict.items():

                value = None

                if config['type'] == 'file':
                    value = request.files.get(field)
                    value = special_field_handlers['image'](value) if field == 'image' else value
                else:
                    value = request.form.get(field)

                validated_value = validate_field(field, value, config)
                nested_data[section][field] = validated_value

            form_data.update(nested_data)
            nested_flag = True

    values_to_insert_db = {}

    print("form_data", flush=True)
    print(form_data, flush=True)
    print("nested_flag", flush=True)
    print(nested_flag, flush=True)

    if nested_flag == False:
        print("YES", flush=True)
        values_to_insert_db = {
            'fields': ', '.join(form_data.keys()),
            'placeholders': ', '.join(['%s'] * len(form_data)),
            'values': tuple(form_data.values())
        }

        print("values_to_insert_db", flush=True)
        print(values_to_insert_db, flush=True)
    else:
        print("NO", flush=True)
        for table_name, fields_data in form_data.items():

            fields = ', '.join(fields_data.keys())
            placeholders = ', '.join(['%s'] * len(fields_data))
            values = tuple(fields_data.values())

            table_data = {
                'fields': fields,
                'placeholders': placeholders,
                'values': values
            }

            values_to_insert_db[table_name] = table_data

            print("values_to_insert_db", flush=True)
            print(values_to_insert_db, flush=True)
    
    return values_to_insert_db

def prepare_get_registration_return_data(cur, first_captcha_number, second_captcha_number):

    cur.execute("INSERT INTO captcha(first_number, second_number, result) VALUES (%s, %s, %s) RETURNING *", (first_captcha_number, second_captcha_number, first_captcha_number + second_captcha_number))
    captcha_row = cur.fetchone()
    captcha_id = captcha_row['id']

    country_codes = cache_impl.get_country_codes(cur=cur)

    prepared_data = {
        'first_captcha_number': first_captcha_number,
        'second_captcha_number': second_captcha_number,
        'captcha_result': captcha_row['result'],
        'country_codes': country_codes,
        'captcha_id': captcha_id
    }

    return prepared_data

def check_post_registration_fields_data(cur, first_name, last_name, email, password_, confirm_password_, phone, gender, captcha_id, captcha_,user_ip, hashed_password, verification_code, country_code, address):    
    regex_phone = r'^\d{7,15}$'

    utils.AssertUser(password_ == confirm_password_, "Password and Confirm Password fields are different")
    utils.AssertUser(re.fullmatch(regex_phone, phone), "Phone number format is not valid. The number should be between 7 and 15 digits")
    utils.AssertUser(gender == 'male' or gender == 'female', "Gender must be Male of Female")
    utils.AssertUser(len(first_name) >= 3 and len(first_name) <= 50, "First name is must be between 3 and 50 symbols")
    utils.AssertUser(len(last_name) >= 3 and len(last_name) <= 50, "Last name must be between 3 and 50 symbols")
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    utils.AssertUser(re.fullmatch(regex, email), "Email is not valid")

    cur.execute("SELECT id, last_attempt_time, attempts FROM captcha_attempts WHERE ip_address = %s", (user_ip,))
    attempt_record = cur.fetchone()

    attempts = 0
    max_attempts = int(utils.get_captcha_setting_by_name(cur, 'max_captcha_attempts'))
    timeout_minutes = int(utils.get_captcha_setting_by_name(cur,'captcha_timeout_minutes'))

    if attempt_record:
        attempt_id, last_attempt_time, attempts = attempt_record
        time_since_last_attempt = datetime.now() - last_attempt_time
        utils.AssertUser(not(attempts >= max_attempts and time_since_last_attempt < timedelta(minutes=timeout_minutes)), "You typed wrong captcha several times, now you have timeout " + str(timeout_minutes) + " minutes")
        if time_since_last_attempt >= timedelta(minutes=timeout_minutes):
            attempts = 0
            
    # captcha_id = session.get("captcha_id")
    cur.execute("SELECT result FROM captcha WHERE id = %s", (captcha_id,))
    result = cur.fetchone()[0]

    if captcha_ != result:
        utils.add_recovery_data_in_session(recovery_data)
        new_attempts = attempts + 1
        if attempt_record:
            cur.execute("UPDATE captcha_attempts SET attempts = %s, last_attempt_time = CURRENT_TIMESTAMP WHERE id = %s", (new_attempts, attempt_id))
        else:
            cur.execute("INSERT INTO captcha_attempts (ip_address, attempts, last_attempt_time) VALUES (%s, 1, CURRENT_TIMESTAMP)", (user_ip,))
        raise exception.WrongUserInputException("Invalid CAPTCHA. Please try again")
    else:
        if attempt_record:
            cur.execute("DELETE FROM captcha_attempts WHERE id = %s", (attempt_id,))

    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user_row = cur.fetchone()

    utils.AssertUser(user_row is None, "There is already registration with this email")

    cur.execute("SELECT * FROM country_codes WHERE code = %s", (country_code,))
    country_code_row = cur.fetchone()
    country_code_id = country_code_row['id']

    cur.execute("""
        INSERT INTO users 
            (first_name, last_name, email, password, verification_code, address, gender, phone, country_code_id) 
        VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, 
        (first_name, last_name, email, hashed_password, verification_code, address, gender, phone,country_code_id))

def registration(conn, cur):
    user_ip = request.remote_addr

    if request.method == 'GET':
        recovery_data = None

        if 'recovery_data_stack' in session:
            recovery_data_stack = session.get('recovery_data_stack', [])
            if len(recovery_data_stack) == 1:
                utils.trace("len(recovery_data_stack)")
                utils.trace(len(recovery_data_stack))
                recovery_data = recovery_data_stack.pop()
        else:
            recovery_data = None

        first_captcha_number = random.randint(0,100)
        second_captcha_number = random.randint(0,100)

        prepared_data = front_office.prepare_get_registration_return_data(cur=cur, 
                                                                        first_captcha_number=first_captcha_number, 
                                                                        second_captcha_number=second_captcha_number)

        rendered_template =  render_template('registration.html', 
            country_codes=prepared_data['country_codes'], 
            recovery_data=recovery_data, 
            captcha = {"first": prepared_data['first_captcha_number'], "second": prepared_data['second_captcha_number']}, 
            captcha_id = prepared_data['captcha_id'])

        return make_response(rendered_template, 200)

    elif request.method == 'POST':

        recovery_data = request.form.to_dict()
        session['recovery_data'] = recovery_data
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password_ = request.form['password']
        confirm_password_ = request.form['confirm_password']

        address = request.form['address']
        country_code = request.form['country_code']
        phone = request.form['phone']
        gender = request.form['gender']

        captcha_ = int(request.form['captcha'])

        captcha_id = request.form.get('captcha_id')

        hashed_password = utils.hash_password(password_)
        verification_code = os.urandom(24).hex()

        front_office.check_post_registration_fields_data(cur, first_name, last_name, email, password_, confirm_password_, 
                                                phone, gender, captcha_id, captcha_,user_ip, hashed_password, 
                                                verification_code, country_code, address)

        send_verification_email(email, verification_code, cur)

        session['verification_message'] = 'Successful registration, we send you a verification code on the provided email'
        return redirect("/verify")

    else:
        utils.AssertPeer(False, "Invalid method")

def send_verification_email(user_email, verification_code, cur):

    cur.execute("""
                SELECT 
                    email_template.*,
                    users.*
                FROM 
                    email_template,
                    users
                WHERE 
                    email_template.name = %s 
                    AND 
                    users.email = %s
        """, ('Verification Email', user_email))

    email_template_user_rows = cur.fetchone()

    if email_template_user_rows:
        subject = email_template_user_rows['subject']
        sender = email_template_user_rows['sender']
        body = email_template_user_rows['body']
        first_name = email_template_user_rows['first_name']
        last_name = email_template_user_rows['last_name']

        body_filled = body.format(
            first_name=first_name,
            last_name=last_name,
            verification_code=verification_code
        )

        with app.app_context():
            msg = Message(subject,
                    sender = sender,
                    recipients = [user_email])
        msg.body = body_filled
        mail.send(msg)
    else:
        utils.AssertDev(False, "No information in the database")

def post_verify_method(cur, email, verification_code):

    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user_row = cur.fetchone()
    utils.AssertUser(user_row is not None, "There is no registration with this mail")

    email_from_database = user_row['email']
    is_verified = user_row['verification_status']
    verification_code_database = user_row['verification_code']

        utils.AssertUser(email_from_database == email, "You entered different email")
        utils.AssertUser(not is_verified, "The account is already verified")
        utils.AssertUser(verification_code_database == verification_code, "The verification code you typed is different from the one we send you")
        
        cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", (verification_code,))

def verify(conn, cur):

    if request.method == 'GET':

        recovery_data = None

        if 'recovery_data_stack' in session:
            recovery_data_stack = session.get('recovery_data_stack', [])
            if len(recovery_data_stack) == 1:
                recovery_data = recovery_data_stack.pop()
        else:
            recovery_data = None

        return render_template('verify.html', recovery_data=recovery_data)

    elif request.method == 'POST':

        recovery_data = request.form.to_dict()
        session['recovery_data'] = recovery_data
        email = request.form['email']
        verification_code = request.form['verification_code']
        
        front_office.post_verify_method(cur=cur, email=email, verification_code=verification_code)

        session['login_message'] = 'Successful verification'
        return redirect("/login")

    else:
        utils.AssertPeer(False, "Invalid method")

def post_login_method(cur, email, password_):
    cur.execute("""
                    SELECT 
                        *
                    FROM 
                        users
                    WHERE 
                        email = %s
                    """, (email,))
    user_data = cur.fetchone()


def login(conn, cur):

    if request.method == 'GET':

        recovery_data = None

        if 'recovery_data_stack' in session:
            recovery_data_stack = session.get('recovery_data_stack', [])
            if len(recovery_data_stack) == 1:
                recovery_data = recovery_data_stack.pop()
        else:
            recovery_data = None

        return render_template('login.html', recovery_data=recovery_data)

    elif request.method == 'POST':

        recovery_data = request.form.to_dict()
        session['recovery_data'] = recovery_data
        email = request.form['email']
        password_ = request.form['password']

        user_data = front_office.post_login_method(cur=cur, email=email, password_=password_)

        session_id = sessions.create_session(session_data=email, cur=cur, conn=conn, is_front_office=True)

        session_id_unauthenticated_user = request.cookies.get('session_id_unauthenticated_user')
        if session_id_unauthenticated_user:
            if user_data:
                user_id = user_data['id']

                front_office.merge_cart(conn, cur, user_id, session_id_unauthenticated_user)

                session['cart_message_unauth_user'] = "You logged in successfully, this are the items you selected before you logged"
                response = make_response(redirect('/cart'))
                response.set_cookie('session_id_unauthenticated_user', '', expires=0)
        else:
            response = make_response(redirect('/home/1'))

        response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')

        return response
    else:
        utils.AssertPeer(False, "Invalid method")

def home(conn, cur, page = 1):

    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       # return redirect('/login') 
        cur.execute("SELECT DISTINCT(category) FROM products")
        categories = cur.fetchall()

        cart_count = 0
        first_name = ""
        last_name = ""
        email = ""
    else:
        query = """
            WITH categories AS (
                SELECT DISTINCT(category) FROM products
            )
            SELECT *
            FROM categories 
            CROSS JOIN (SELECT * FROM users WHERE email = %s) u
        """
        
        cur.execute(query, (authenticated_user,))
        results = cur.fetchall()

        categories = [row[0] for row in results]
        user_id = results[0][1]
        first_name = results[0][2]
        last_name = results[0][3]

        cart_count = front_office.get_cart_items_count(conn, cur, user_id)

    validated_fields = utils.check_request_arg_fields(cur, request)

    sort_by = validated_fields['sort_by']
    sort_order = validated_fields['sort_order']

    products_per_page = validated_fields['products_per_page']
    page = validated_fields['page_front_office']
    offset = validated_fields['offset_front_office']

    product_name = validated_fields['product_name']
    product_category = validated_fields['product_category']
    price_min = validated_fields['price_min']
    price_max = validated_fields['price_max']

    results_from_home_page_query = front_office.get_home_query_data(cur=cur, sort_by=sort_by, sort_order=sort_order, products_per_page=products_per_page, 
                                                        page=page, offset=offset, product_name=product_name, 
                                                        product_category=product_category, price_min=price_min, price_max=price_max)

    products = results_from_home_page_query['products']
    total_pages = results_from_home_page_query['total_pages']

    data_to_return = {
        'products': products,
        'total_pages': total_pages,
    }

    return data_to_return

def home(conn, cur, page = 1):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       # return redirect('/login') 
        cur.execute("SELECT DISTINCT(category) FROM products")
        categories = cur.fetchall()

        cart_count = 0
        first_name = ""
        last_name = ""
        email = ""
    else:
        query = """
            WITH categories AS (
                SELECT DISTINCT(category) FROM products
            )
            SELECT *
            FROM categories 
            CROSS JOIN (SELECT * FROM users WHERE email = %s) u
        """
        
        cur.execute(query, (authenticated_user,))
        results = cur.fetchall()

        categories = [row[0] for row in results]
        user_id = results[0][1]
        first_name = results[0][2]
        last_name = results[0][3]

        cart_count = front_office.get_cart_items_count(conn, cur, user_id)

    validated_fields = utils.check_request_arg_fields(cur, request)

    sort_by = validated_fields['sort_by']
    sort_order = validated_fields['sort_order']

    products_per_page = validated_fields['products_per_page']
    page = validated_fields['page_front_office']
    offset = validated_fields['offset_front_office']

    product_name = validated_fields['product_name']
    product_category = validated_fields['product_category']
    price_min = validated_fields['price_min']
    price_max = validated_fields['price_max']

    results_from_home_page_query = front_office.get_home_query_data(cur=cur, sort_by=sort_by, sort_order=sort_order, products_per_page=products_per_page, 
                                                        page=page, offset=offset, product_name=product_name, 
                                                        product_category=product_category, price_min=price_min, price_max=price_max)

    products = results_from_home_page_query['products']
    total_pages = results_from_home_page_query['total_pages']

    return render_template('home.html', first_name=first_name, last_name=last_name, 
                                email = authenticated_user, products=products, products_per_page=products_per_page, 
                                price_min=price_min, price_max=price_max,page=page, total_pages=total_pages, 
                                sort_by=sort_by, sort_order=sort_order, product_name=product_name, 
                                product_category=product_category, cart_count=cart_count, categories=categories)

def logout(conn, cur):
    session_id = request.cookies.get('session_id')

    cur.execute("DELETE FROM custom_sessions WHERE session_id = %s", (session_id,))

    response = make_response(redirect('/login'))
    response.set_cookie('session_id', '', expires=0)
    return response

def profile(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/login') 
    
    if request.method == 'GET':

        result_data = front_office.get_profile_data(cur=cur, authenticated_user=authenticated_user)

        if result_data:
            return render_template('profile.html', first_name=result_data['first_name'], last_name=result_data['last_name'],
                                     email=result_data['email'], address=result_data['address'], phone=result_data['phone'],
                                     gender=result_data['gender'], country_codes=result_data['country_codes'], country_code=result_data['code'])
        
        return render_template('profile.html')
    else:
        utils.AssertPeer(False, "Invalid method")

def update_profile(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/login')

    if request.method == 'POST':

        validated_fields = utils.check_request_form_fields(request)

        first_name = validated_fields['first_name']
        last_name = validated_fields['last_name']
        email = validated_fields['email']
        password_ = validated_fields['password']
        address = validated_fields['address']
        phone = validated_fields['phone']
        country_code = validated_fields['country_code']
        gender = validated_fields['gender']

        result_data = front_office.post_update_profile(cur=cur, conn=conn,first_name=first_name, last_name=last_name,
                                        email=email, password_=password_, 
                                        address=address, phone=phone, 
                                        country_code=country_code, gender=gender, 
                                        session_id=session_id)

        session['home_message'] = f"You successfully updated your {result_data['updated_fields_message']}."

        return redirect('/home/1')
    else:
        utils.AssertPeer(False, "Invalid method")

def delete_account(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/login')

    cur.execute("DELETE FROM users WHERE email = %s", (authenticated_user,))

    cur.execute("DELETE FROM custom_sessions WHERE session_id = %s", (session_id,))
    response = make_response(redirect('/login'))
    response.set_cookie('session_id', '', expires=0)
    session['login_message'] = 'You successful deleted your account'
    return response
# 
def recover_password(conn, cur):

    if request.method == 'POST':
        email = request.form['recovery_email']
        new_password = os.urandom(10).hex()

        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user_row = cur.fetchone()

        utils.AssertUser(user_row is not None, "You entered non existent email")

        hashed_password = utils.hash_password(new_password)

        cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))

        send_recovey_password_email(email, new_password)
        
        session['login_message'] = 'A recovery password has been sent to your email.'
        return redirect('/login')
    else:
        utils.AssertPeer(False, "Invalid method")

def send_recovey_password_email(user_email, recovery_password):
    with app.app_context():
        msg = Message('Recovery password',
                sender = 'galincho112@gmail.com',
                recipients = [user_email])
    msg.body = 'Your recovery password: ' + recovery_password
    mail.send(msg)

# TODO: Този метод се замести със send_login_link 
def resend_verf_code(conn, cur):
    assertIsProvidedMethodsTrue('POST')
    
    email = request.form['resend_verf_code']

    new_verification_code = os.urandom(24).hex()

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))

    utils.AssertUser(not cur.rowcount == 0, "There is no registration with this email")
    
    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_verified = cur.fetchone()[0]

    utils.AssertUser(not is_verified, "The account is already verified")

    cur.execute("UPDATE users SET verification_code = %s WHERE email = %s", (new_verification_code, email))

    send_verification_email(email, new_verification_code)

    session['verification_message'] = 'A new verification code has been sent to your email.'
    return redirect('/verify')

def send_login_link(conn, cur):

    if request.method == 'POST':

        email = request.form['resend_verf_code']
        
        login_token = os.urandom(24).hex()

        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user_row = cur.fetchone()

        utils.AssertUser(user_row is not None, "There is no registration with this email")

        # cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
        is_verified = user_row['verification_status']

        utils.AssertUser(not is_verified, "The account is already verified")
        
        expiration_time = datetime.now() + timedelta(hours=1)

        cur.execute("INSERT INTO tokens(login_token, expiration) VALUES (%s, %s) RETURNING id", (login_token, expiration_time))
        token_id = cur.fetchone()['id']

        # cur.execute("SELECT id FROM tokens WHERE login_token = %s", (login_token,))
        # token_id = cur.fetchone()[0]
        cur.execute("UPDATE users SET token_id = %s WHERE email = %s", (token_id, email))

        login_link = f"http://10.20.3.101:5000/log?token={login_token}"

        send_verification_link(email, login_link)

        session['login_message'] = 'A login link has been sent to your email.'

        return redirect('/login')
    else:
        utils.AssertPeer(False, "Invalid method")

def send_verification_link(user_email, verification_link):
    with app.app_context():
        msg = Message('Email Verification',
                sender = 'galincho112@gmail.com',
                recipients = [user_email])
    msg.body = 'Click the link to go directly to your profile: ' + verification_link
    mail.send(msg)

def login_with_token(conn, cur):

    if request.method == 'GET':
    
        token = request.args.get('token')

        if not token:
            session['registration_error'] = 'Invalid login token'
            return redirect('/registration')

        cur.execute("SELECT * FROM tokens WHERE login_token = %s", (token,))
        token_row = cur.fetchone()

        token_id = token_row['id']
        expiration = token_row['expiration']

        if not token_row or expiration < datetime.now():
            session['login_error'] = 'Invalid login token'
            return redirect('/login')
        
        cur.execute("SELECT * FROM users WHERE token_id = %s", (token_id,))
        user_row = cur.fetchone()

        if not user_row:
            session['registration_error'] = 'Invalid user'
            return redirect('/login')
        
        email = user_row['email']

        cur.execute("UPDATE users SET token_id = NULL, verification_status = true WHERE email = %s", (email,))

        cur.execute("DELETE FROM tokens WHERE id = %s", (token_id,))

        session_id = sessions.create_session(session_data= email, cur=cur, conn=conn, is_front_office=True)

        response = make_response(redirect('/home/1'))
        response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')

        return response
    else:
        utils.AssertPeer(False, "Invalid method")

def log_exception(exception_type, message ,email):
    conn_new = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur_new = conn_new.cursor()

    cur_new.execute("INSERT INTO exception_logs (user_email, exception_type, message) VALUES (%s, %s, %s)", (email, exception_type, message))

    conn_new.commit()
    conn_new.close()
    cur_new.close()

def add_product(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/login')

    if request.method == 'GET':
        cur.execute("SELECT DISTINCT(category) FROM products")
        categories = [row[0] for row in cur.fetchall()]  # Extract categories from tuples
        return render_template('add_product_staff.html', categories=categories)

    name = request.form['name']
    price = request.form['price']
    quantity = request.form['quantity']
    category = request.form['category']
    image = request.files['image']

    utils.AssertUser(name and price and quantity and category and image, "You must add information in every field.")
    utils.AssertUser(isinstance(float(price), float), "Price is not a number")
    utils.AssertUser(isinstance(int(quantity), int), "Quantity is not a number")
    utils.AssertUser(float(price) > 0, "Price must be possitive number")
    utils.AssertUser(int(quantity) > 0, "Quantity must be possitive")
    
    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image_data = image.stream
        image_ = validate_image_size(image_data)

    cur.execute("INSERT INTO products (name, price, quantity, category, image) VALUES (%s, %s, %s, %s, %s)", (name, price, quantity, category, image_))

    session['crud_message'] = "Item was added successful"
    return redirect('/crud')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image_size(image_stream):
    image_stream.seek(0, io.SEEK_END) # Seek to the end of the file
    file_size = image_stream.tell() # Get the current position, which is the file size
    image_stream.seek(0) # Reset the stream position to the start
    utils.AssertUser(file_size < MAX_FILE_SIZE, "The image file size must not exceed 10MB.")
    return image_stream.read()

def serve_image(product_id, cur):
    pr_id = request.path.split("/")[2]
    cur.execute("SELECT * FROM products WHERE id = %s", (pr_id,))
    image_blob = cur.fetchone()['image']
    return Response(image_blob, mimetype='jpeg')

def add_to_cart_meth(conn, cur):
    session_cookie_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_cookie_id, cur=cur, conn=conn)

        if session_id_unauthenticated_user == None:

            session_id = str(uuid.uuid4())

    if authenticated_user == None:

        session_id_unauthenticated_user = request.cookies.get('session_id_unauthenticated_user')

        if session_id_unauthenticated_user == None:

            session_id = str(uuid.uuid4())

            response_message = front_office.add_to_cart(conn, cur, session_id, product_id, quantity, session_cookie_id)
            newCartCount = front_office.get_cart_items_count(conn, cur, session_id)

            response = make_response(jsonify({'message': response_message, 'newCartCount': newCartCount}))
            response.set_cookie('session_id_unauthenticated_user', session_id, httponly=True, samesite='Lax')

        else:
            response_message = front_office.add_to_cart(conn, cur, session_id_unauthenticated_user, product_id, quantity, session_cookie_id)
            newCartCount = front_office.get_cart_items_count(conn, cur, session_id_unauthenticated_user)

            response = make_response(jsonify({'message': response_message, 'newCartCount': newCartCount}))
    else:
        cur.execute("SELECT * FROM users WHERE email = %s", (authenticated_user,))
        user_row = cur.fetchone()
        user_id = user_row['id']

        response_message = front_office.add_to_cart(conn, cur, user_id, product_id, quantity, session_cookie_id)
        newCartCount = front_office.get_cart_items_count(conn, cur, user_id)

        response = make_response(jsonify({'message': response_message, 'newCartCount': newCartCount}))

    return response

def cart(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user = sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
        session['login_message_unauth_user'] = "You have to login to see your cart"
        return redirect("/login")
    
    if request.method == 'GET':
        recovery_data = None

        if 'recovery_data_stack' in session:
            recovery_data_stack = session.get('recovery_data_stack', [])
            if len(recovery_data_stack) == 1:
                recovery_data = recovery_data_stack.pop()
                #TODO assert
            else:
                utils.AssertDev(False, "Too many values in recovery_data_stack")
        else:
            recovery_data = None 

        result_data = front_office.get_cart_method_data(cur=cur, conn=conn,authenticated_user=authenticated_user)

        return render_template('cart.html', items=result_data['items'], total_sum_with_vat=round(result_data['total_sum_with_vat'],2), 
                                total_sum=round(result_data['total_sum'],2),country_codes=result_data['country_codes'], recovery_data=recovery_data, 
                                first_name=result_data['first_name'], last_name=result_data['last_name'], email=authenticated_user, vat=result_data['vat_in_persent'])
   
    elif request.method == 'POST':
        recovery_data = request.form.to_dict()
        session['recovery_data'] = recovery_data

        email = request.form['email'].strip()
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        town = request.form['town'].strip()
        address = request.form['address'].strip()
        country_code = request.form['country_code']
        phone = request.form['phone'].strip()

        regex_phone = r'^\d{7,15}$'
        regex_email = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

        # Check fields 
        utils.AssertUser(len(first_name) >= 3 and len(first_name) <= 50, "First name is must be between 3 and 50 symbols")
        utils.AssertUser(len(last_name) >= 3 and len(last_name) <= 50, "Last name must be between 3 and 50 symbols")
        utils.AssertUser(re.fullmatch(regex_email, email), "Email is not valid")
        utils.AssertUser(re.fullmatch(regex_phone, phone), "Phone number format is not valid. The number should be between 7 and 15 digits")
        utils.AssertUser(phone[0] != "0", "Phone number format is not valid.")

        # Retrieve cart items for the user
        cur.execute("""
                    SELECT 
                        *
                    FROM users      
                    JOIN carts ON users.id = carts.user_id
                    WHERE users.email = %s
                    """, 
                    (authenticated_user,))

        users_carts_row = cur.fetchone()
        user_id = users_carts_row['id']
        user_first_name = users_carts_row['first_name']
        user_last_name = users_carts_row['last_name']
        cart_id = users_carts_row['cart_id']

        #------------------------------------------------ edna zaqvka
        cur.execute("""
                    SELECT 
                        cart_items.product_id, 
                        products.name, 
                        cart_items.quantity, 
                        products.price, 
                        currencies.symbol, 
                        cart_items.vat 
                    FROM cart_items
                    JOIN products   ON cart_items.product_id = products.id
                    JOIN currencies ON products.currency_id  = currencies.id
                    WHERE cart_items.cart_id = %s
                    """,
                    (cart_id,))

        cart_items = cur.fetchall()

        db_items_quantity = []

        for item in cart_items:
            cur.execute("""
                        SELECT 
                            quantity 
                        FROM products 
                        WHERE id = %s
                        """, 
                        (item['product_id'],))

            item_quantity_db = cur.fetchone()[0]

            db_items_quantity.append(item_quantity_db)

        #------------------------------------------------
        # TODO: CODE REVIEW - I/O read - write
        # Check and change quantity 
        for item in cart_items:

            product_id_, name, quantity, price, symbol, vat = item
            quantity_db = db_items_quantity.pop(0)

            if quantity > quantity_db:
                session['cart_error'] = "We don't have " + str(quantity) + " from product: " + str(name) + " in our store. You can purchase less or to remove the product from your cart"
                utils.add_recovery_data_in_session(session.get('recovery_data'))
                return redirect('/cart')

            cur.execute("UPDATE products SET quantity = quantity - %s WHERE id = %s", (quantity, product_id_))

        price_mismatch = False
        for item in cart_items:

            product_id, name, quantity, cart_price, symbol, vat = item

            cur.execute("SELECT price FROM products WHERE id = %s", (product_id,))
            current_price = cur.fetchone()['price']

            if current_price != cart_price:
                # Price can be updated here
                price_mismatch = True
                break

        utils.AssertUser(not price_mismatch, "The price on some of your product's in the cart has been changed, you can't make the purchase")

        # First make order, then make shipping_details #
        formatted_datetime = datetime.now().strftime('%Y-%m-%d')
        cur.execute("""
                    INSERT INTO orders (
                        user_id, 
                        status, 
                        order_date) 
                    VALUES (%s, %s, CURRENT_TIMESTAMP) 
                    RETURNING order_id
                    """, 
                    (user_id, "Ready for Paying")) #formatted_datetime

        order_id = cur.fetchone()['order_id']

        # Insert order products into order_items table
        for item in cart_items:

            item_id = item['product_id']
            item_quantity = item['quantity']
            item_price = item['price']
            item_vat = item['vat']

            cur.execute("""
                        INSERT INTO order_items (
                            order_id, 
                            product_id, 
                            quantity, 
                            price, 
                            vat) 
                        VALUES (%s, %s, %s, %s, %s)
                        """, 
                        (order_id, item_id, item_quantity, item_price, item_vat))

        cur.execute("""
                    SELECT 
                        * 
                    FROM country_codes 
                    WHERE code = %s
                    """, 
                    (country_code,))

        country_code_row = cur.fetchone()
        country_code_id = country_code_row['id']

        cur.execute("""
                    INSERT INTO shipping_details (
                            order_id, 
                            email, 
                            first_name, 
                            last_name, town, 
                            address, phone, 
                            country_code_id  ) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, 
                    (order_id, email, first_name, last_name, town, address, phone, country_code_id))

        # Total sum to be passed to the payment.html
        # Total sum with vat to be passed to the payment.html
        total_sum = 0

        total_sum_with_vat = 0

        for item in cart_items:
            vat_float = (float(item['vat']) / 100)
            items_sum_without_vat = float(item['quantity'] * item['price'])
            total_sum += items_sum_without_vat
            vatt = items_sum_without_vat * vat_float
            total_sum_with_vat += items_sum_without_vat + vatt

        # When the purchase is made we empty the user cart
        # TODO: cart_items -> CART_ITEMS 
        cur.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))

        cur.execute("""
                    SELECT 
                        shipping_details.*, 
                        country_codes.code 
                    FROM shipping_details
                        JOIN orders        ON shipping_details.order_id        = orders.order_id 
                        JOIN country_codes ON shipping_details.country_code_id = country_codes.id 
                    WHERE orders.order_id = %s
                    """, 
                    (order_id,))

        shipping_details = cur.fetchall()

        cur.execute("SELECT * FROM settings")
        settings_row = cur.fetchone()

        #TODO: Move into job queue -> pattern 
        send_email = False
        try:
            utils.trace("ENTERED TRY BLOCK")

            send_mail_data = {
                "products": cart_items,
                "shipping_details": shipping_details[0],
                "total_sum": total_sum,
                "total_with_vat": total_sum_with_vat,
                "provided_sum": 0,
                "user_email": authenticated_user,
                "cur": cur,
                "conn": conn,
                "email_type": 'purchase_mail',
                "app": app,
                "mail": mail,
            }

            session['send_email'] = True
            session['send_mail_data'] = send_mail_data

            session['payment_message'] = "You successful made an order with id = " + str(order_id)

            return render_template('payment.html', order_id=order_id, order_products=cart_items, 
                                    shipping_details=shipping_details, total_sum_with_vat=round(total_sum_with_vat, 2 ),
                                    total_sum=round(total_sum, 2), first_name=user_first_name, 
                                    last_name=user_last_name, email=authenticated_user, vat_in_persent = settings_row['vat'])
        except Exception as e:
            conn.rollback()
            raise e
    else:
        utils.AssertPeer(False, "Invalid method")

def remove_from_cart_meth(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/login')

    item_id = request.form['item_id']

    response = front_office.remove_from_cart(conn, cur, item_id)

    session['cart_message'] = response
    return redirect('/cart')

def finish_payment(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/login')
    
    if request.method == 'GET':

        order_id = session.get('order_id')

        cur.execute("SELECT users.*, settings.vat FROM users, settings WHERE email = %s", (authenticated_user,))
        user_settings_row = cur.fetchone()

        cur.execute("""

                    SELECT 
                        order_items.product_id, 
                        products.name, 
                        order_items.quantity, 
                        order_items.price, 
                        currencies.symbol, 
                        order_items.vat 
                    FROM order_items  
                        JOIN products   ON order_items.product_id = products.id 
                        JOIN currencies ON products.currency_id   = currencies.id 
                        WHERE order_id = %s

                    """, (order_id,))

        order_products = cur.fetchall()

        utils.AssertDev(len(order_products) <= 1000, "More than 1000 products where fetched from the db in finish_payment method")

        total_summ = sum(int(product['quantity']) * Decimal(product['price']) for product in order_products)
        total_sum = round(total_summ, 2)

        total_with_vat = 0
        for product in order_products:

            total_with_vat += (int(product['quantity']) * float(product['price'])) + (((float(product['vat']) / 100)) * (int(product['quantity']) * float(product['price'])))

        cur.execute("SELECT * FROM shipping_details WHERE order_id = %s", (order_id,))
        shipping_details = cur.fetchall()

        session['order_id'] = order_id

        return render_template('payment.html', order_products=order_products, shipping_details=shipping_details, 
                                total_sum=total_sum, total_sum_with_vat=round(total_with_vat, 2), 
                                first_name = user_settings_row['first_name'], last_name = user_settings_row['last_name'], 
                                email = user_settings_row['email'], vat_in_persent=user_settings_row['vat'])

    elif request.method == 'POST':

        order_id = request.form.get('order_id')

        if order_id == "":
            order_id = session.get('order_id')

        utils.AssertUser(isinstance(float(request.form.get('payment_amount')), float), "You must enter a number")

        payment_amountt = float(request.form.get('payment_amount'))
        payment_amount = round(float(payment_amountt), 2)

        cur.execute("SELECT quantity, price, vat FROM order_items WHERE order_id = %s", (order_id,))
        all_products_from_the_order = cur.fetchall()

        cur.execute("""

                    SELECT
                        orders.*,
                        shipping_details.*,
                        country_codes.code AS country_codes_code
                    FROM 
                        orders,
                        shipping_details

                        JOIN country_codes ON shipping_details.country_code_id = country_codes.id
                    WHERE
                        orders.order_id = %s 
                        AND 
                        shipping_details.order_id = %s

            """, (order_id, order_id))

        orders_shipping_details_row = cur.fetchone()
        order_status = orders_shipping_details_row['status']
        # shipping_id, order_id, email, first_name, last_name, town, address, phone, country_code_id, country_codes_code  = shipping_details
        shipping_details = []
        shipping_details.append(orders_shipping_details_row['shipping_id'])
        shipping_details.append(orders_shipping_details_row['order_id'])
        shipping_details.append(orders_shipping_details_row['email'])
        shipping_details.append(orders_shipping_details_row['first_name'])
        shipping_details.append(orders_shipping_details_row['last_name'])
        shipping_details.append(orders_shipping_details_row['town'])
        shipping_details.append(orders_shipping_details_row['address'])
        shipping_details.append(orders_shipping_details_row['phone'])
        shipping_details.append(orders_shipping_details_row['country_code_id'])
        shipping_details.append(orders_shipping_details_row['country_codes_code'])

        utils.trace(shipping_details)

        total = 0
        for product in all_products_from_the_order:
            total += int(product[0]) * Decimal(product[1])

        total_with_vat = 0
        for product in all_products_from_the_order:
            total_with_vat += (int(product[0]) * float(product[1])) + (((float(product[2]) / 100)) * (int(product[0]) * float(product[1])))

        utils.AssertUser(order_status == 'Ready for Paying', "This order is not ready for payment or has already been paid")

        if payment_amount < round(total_with_vat, 2):
            session['order_id'] = order_id
            session['payment_error'] = "You entered amout, which is less than the order you have"
            return redirect('/finish_payment')
        if payment_amount > round(total_with_vat, 2):
            session['order_id'] = order_id
            session['payment_error'] = "You entered amout, which is bigger than the order you have"
            return redirect('/finish_payment')

        # formatted_datetime = datetime.now().strftime('%Y-%m-%d')
        cur.execute("UPDATE orders SET status = 'Paid' WHERE order_id = %s", (order_id,))

        cur.execute("""

            SELECT 
                products.name, 
                order_items.quantity, 
                order_items.price,
                currencies.symbol,
                order_items.vat
            FROM order_items      
                JOIN products   ON order_items.product_id = products.id
                JOIN currencies ON products.currency_id = currencies.id
            WHERE order_id = %s

            """, (order_id,))

        products_from_order = cur.fetchall()

        send_email = False
        try:
            utils.trace("ENTERED TRY BLOCK")

            send_mail_data = {
                "products": products_from_order,
                "shipping_details": shipping_details,
                "total_sum": total,
                "total_with_vat": total_with_vat,
                "provided_sum": payment_amount,
                "user_email": authenticated_user,
                "cur": cur,
                "conn": conn,
                "email_type": 'payment_mail',
                "app": app,
                "mail": mail,
            }

            session['send_email'] = True
            session['send_mail_data'] = send_mail_data

            session['home_message'] = "You paid the order successful"
            return redirect('/home/1')

        except Exception as e:
            conn.rollback()
            raise e
    else:
        utils.AssertPeer(False, "Invalid method")

def staff_login(conn, cur):

    if request.method == 'GET':
        return render_template('staff_login.html')

    elif request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        cur.execute("SELECT * FROM staff WHERE username = %s AND password = %s", (username, password))
        staff_row = cur.fetchone()
        utils.AssertUser(staff_row is not None, "There is no registration with this staff username and password")

        session['staff_username'] = username

        session_id = sessions.create_session(session_data=username, cur=cur, conn=conn, is_front_office=False)
        response = make_response(redirect('/staff_portal'))
        response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')

        return response
    else:
        utils.AssertPeer(False, "Invalid method")

def staff_portal(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/staff_login')

    if 'visited' not in session:
        session['visited'] = True
        session['first_visit'] = True
    else:
        session['first_visit'] = False

    if request.method == 'GET':
        username = request.path.split('/')[1]
        return render_template('staff_portal.html', username=username)
    
def logout_staff(conn, cur):
    session_id = request.cookies.get('session_id')

    cur.execute("DELETE FROM custom_sessions WHERE session_id = %s", (session_id,))
    response = make_response(redirect('/staff_login'))
    response.set_cookie('session_id', '', expires=0)
    return response

def add_products_from_file(conn, cur, string_path):
    with open(string_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            name = row['name']
            price = float(row['price'])
            quantity = int(row['quantity'])
            category = row['category']
            image_filename = row['image']
            
            image_path = os.path.join(os.path.dirname(string_path), image_filename)
            
            with open(image_path, 'rb') as img_file:
                image_data = img_file.read()

            cur.execute("INSERT INTO products (name, price, quantity, category, image) VALUES (%s, %s, %s, %s, %s)", (name, price, quantity, category, image_data))
        return "Imprted"

def generate_orders(conn, cur):
    number_products_to_import = 100
    utils.create_random_orders(number_products_to_import, cur, conn)

    return "Successfully imported products: " + str(number_products_to_import)
        
def update_cart_quantity(conn, cur):
    item_id = request.form['item_id']
    quantity = request.form['quantity']

    utils.AssertUser(isinstance(int(quantity), int), "You must enter number")

    quantity_ = int(quantity)
    utils.AssertUser(quantity_ > 0, "You can't enter quantity zero or below")

    cur.execute("SELECT price, settings.vat FROM products JOIN settings ON products.vat_id=settings.id WHERE products.id = %s ", (item_id,))
    price, vat_rate = cur.fetchone()
    new_total = price * quantity_

    cur.execute("UPDATE cart_items SET quantity = %s WHERE product_id = %s", (quantity_, item_id))

    return jsonify(success=True, new_total=new_total, vat_rate=vat_rate)

# def serve_image_crud_products_edit(conn, cur, product_id):
#     print("Entered get image for edit product", flush=True)

#     cur.execute("SELECT image FROM products WHERE id = %s", (product_id,))
#     image = cur.fetchone()[0]
#     if image:
#         return Response(
#             io.BytesIO(image).getvalue(),
#             mimetype='image/jpeg'
#         )
#     else:
#         return "No image found"

def user_orders(conn, cur):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/login')

    if request.method == 'GET':

        fields = utils.check_request_arg_fields(cur, request)

        sort_by = fields['sort_by']
        sort_order = fields['sort_order']
        price_min = fields['price_min']
        price_max = fields['price_max']
        order_by_id = fields['order_by_id']
        date_from = fields['date_from']
        date_to = fields['date_to']
        status = fields['status']

        cur.execute("SELECT DISTINCT status FROM orders")
        statuses = cur.fetchall()

        params = []
        query = """
            SELECT 
                o.order_id, 
                o.status, 
                to_char(o.order_date, 'MM-DD-YYYY HH:MI:SS')           AS o_date, 
                oi.product_id, 
                p.name,
                oi.price, 
                oi.quantity, 
                to_char(sum(oi.price * oi.quantity), 'FM999999990.00') AS total_price,
                c.symbol,
                settings.vat
            FROM orders      AS o 
            JOIN users       AS u  ON o.user_id     = u.id 
            JOIN order_items AS oi ON o.order_id    = oi.order_id 
            JOIN products    AS p  ON oi.product_id = p.id 
            JOIN currencies  AS c  ON p.currency_id = c.id 
            JOIN settings          ON p.vat_id      = settings.id
            WHERE u.email = %s 
            """

        params.append(authenticated_user)

        if order_by_id:
            query += " AND o.order_id = %s"
            params.append(order_by_id)

        if date_from and date_to:
            query += " AND o.order_date >= %s AND o.order_date <= %s"
            params.extend([date_from, date_to])

        if status:
            query += " AND o.status = %s"
            params.append(status)

        if price_min and price_max:
            query += "GROUP BY o.order_id, o.status, o_date, oi.product_id, oi.price, oi.quantity, p.name, c.symbol, settings.vat HAVING sum(oi.quantity * oi.price) >= %s AND sum(oi.quantity * oi.price) <= %s"
            params.extend([price_min, price_max])

        if price_min == '' and price_max == '':
            # o.order_id
            query += " GROUP BY o.order_id, o.status, o_date, oi.product_id, oi.price, oi.quantity, p.name, c.symbol, settings.vat"

        query += f" ORDER BY o.order_{sort_by} {sort_order}  LIMIT 100; "

        cur_name = "order_cursor"
        cur.execute(f"DECLARE {cur_name} SCROLL CURSOR FOR {query}", params)

        cur.execute("FETCH FORWARD 50 FROM order_cursor")

        fetch_size = 50

        def fetch_orders():
            while True:
                cur.execute(f"FETCH FORWARD {fetch_size} FROM {cur_name}")
                batch = cur.fetchall()

                if not batch:
                    break

                for row in batch:
                    yield row

            cur.execute(f"CLOSE {cur_name}") 

        orders_generator = fetch_orders()

        orders = list(orders_generator)

        cur.execute("SELECT first_name, last_name FROM users WHERE email = %s", (authenticated_user,))
        user_details = cur.fetchone()

        return render_template('user_orders.html', orders = orders, statuses = statuses, price_min=price_min, price_max=price_max, date_from=date_from, date_to=date_to, order_by_id=order_by_id, first_name=user_details[0], last_name=user_details[1], email=authenticated_user)
    else:
        utils.AssertUser(False, "Invalid method")


def get_active_users(sort_by='id', sort_order='desc', name=None, email=None, user_id=None):
    active_threshold = datetime.now() - timedelta(minutes=30)

    query = User.query.filter(User.last_active >= active_threshold)


    if name:
        name_filter = f"%{name}"
        query = query.filter(or_(User.first_name.ilike(name_filter), User.last_name.ilike(name_filter)))

    if email:
        email_filter = f"%{email}"
        query = query.filter(User.email.ilike(email_filter))

    if user_id:
        query = query.filter(User.id == user_id)

    if sort_by in ['id', 'last_active']:
        order_by_clause = getattr(User, sort_by).desc() if sort_order == 'desc' else getattr(User, sort_by).asc()
        query = query.order_by(order_by_clause)
    else:
        query = query.order_by(User.id.desc()) 

    active_users = query.all()
    return active_users

def back_office_manager(conn, cur, *params):
    session_id = request.cookies.get('session_id')
    authenticated_user =  sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)

    if authenticated_user == None:
       return redirect('/staff_login')

    print("back_office_manager request.path", flush=True)
    print(request.path, flush=True)

    print("len(request.path.split('/')", flush=True)
    print(len(request.path.split('/')), flush=True)

    if request.path == f'/active_users':

        if request.method == 'GET':

            validated_request_args_fields = utils.check_request_arg_fields(cur=cur, request=request)

            sort_by = validated_request_args_fields['sort_by']
            sort_order = validated_request_args_fields['sort_order']
            name = validated_request_args_fields['name']
            email = validated_request_args_fields['email']
            user_id = validated_request_args_fields['user_by_id']

            users = get_active_users(sort_by, sort_order, name, email, user_id)

            return render_template('active_users.html', users=users, name=name, email=email, user_id=user_id)
        else:
            utils.AssertPeer(False, "Invalid method")

    elif re.match(r'^/crud_products_edit_picture/\d+$', request.path) and len(request.path.split('/')) == 3:

        print("Entered get image for edit product", flush=True)

        product_id = request.path.split('/')[2]

        cur.execute("SELECT image FROM products WHERE id = %s", (product_id,))
        image = cur.fetchone()[0]
        if image:
            return Response(
                io.BytesIO(image).getvalue(),
                mimetype='image/jpeg'
            )
        else:
            return "No image found"

    elif request.path == f'/crud_products/upload_products':

        file = request.files['productFile']

        if file and  '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ['csv']:

            data = csv.reader(file.read().decode('utf-8').splitlines())

            print("data", flush=True)
            print(data, flush=True)

            headers = next(data)  # Skip the header row

            try:
                utils.batch_insert_import_csv(cur, data, os)
                session['crud_message'] = "Successfully inserted all products"
            except Exception as e:
                session['crud_error'] = "Something went wrong with the upload"
        else:
            utils.trace("Invalid file or file type extension. The extension needs to be .csv")
            session['crud_error'] = "Invalid file or file type extension. The extension needs to be .csv"

        return redirect(f'/crud_products')

    elif request.path == f'/error_logs':     
        utils.AssertUser(utils.has_permission(cur, request, 'Logs', 'read', authenticated_user), "You don't have permission to this resource")

        if request.method == 'GET':
        
            validated_request_args_fields = utils.check_request_arg_fields(cur=cur, request=request)

            sort_by = validated_request_args_fields['sort_by']
            sort_order = validated_request_args_fields['sort_order']

            query = "SELECT * FROM exception_logs"

            if sort_by and sort_order:
                query += f" ORDER BY {sort_by} {sort_order}"

            cur.execute(query)
            log_exceptions = cur.fetchall()

            utils.AssertDev(len(log_exceptions) <= 100000, "Too much fetched values from db /error_logs")

            return render_template('logs.html', log_exceptions = log_exceptions, sort_by=sort_by, sort_order=sort_order)
        else:
            utils.AssertPeer(False, "Invalid method")
    
    elif request.path == f'/update_captcha_settings':
        utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'read', authenticated_user), "You don't have permission to this resource")

        if request.method == 'GET':

            current_settings = utils.get_current_settings(cur)

            cur.execute("SELECT * FROM settings")
            settings_row = cur.fetchone()

            limitation_rows = settings_row['report_limitation_rows']
            vat = settings_row['vat']
            background_color = settings_row['send_email_template_background_color']
            text_align = settings_row['send_email_template_text_align']
            border = settings_row['send_email_template_border']
            border_collapse = settings_row['send_email_template_border_collapse']

            return render_template('captcha_settings.html', vat=vat,limitation_rows=limitation_rows, border_collapse=border_collapse,border=border,text_align=text_align,background_color=background_color,**current_settings)

        elif request.method == 'POST':
            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', authenticated_user), "You don't have permission to this resource")

            new_max_attempts = request.form['max_captcha_attempts']
            new_timeout_minutes = request.form['captcha_timeout_minutes']

            utils.AssertUser(not(new_max_attempts and int(new_max_attempts)) <= 0, "Captcha attempts must be possitive number")
            utils.AssertUser(not(new_timeout_minutes and int(new_timeout_minutes)) <= 0, "Timeout minutes must be possitive number")

            str_message = ""

            if new_max_attempts:
                cur.execute("UPDATE captcha_settings SET value = %s WHERE name = 'max_captcha_attempts'", (new_max_attempts,))
                str_message += 'You updated captcha attempts. '
            if new_timeout_minutes:
                cur.execute("UPDATE captcha_settings SET value = %s WHERE name = 'captcha_timeout_minutes'", (new_timeout_minutes,))
                str_message += 'You updated timeout minutes.'
        
            if str_message != "":
                session['staff_message'] = str_message

            return redirect(f'/staff_portal')
        else:
            utils.AssertPeer(False, "Invalid method")

    elif request.path == f'/update_report_limitation_rows':
        if request.method == 'POST':
            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', authenticated_user), "You don't have permission to this resource")

            limitation_rows = int(request.form['report_limitation_rows'])

            utils.AssertUser(limitation_rows >= 0 and limitation_rows <= 50000, "You can't enter zero or negative number. The maximum number is 50000")

            query = ("UPDATE settings SET report_limitation_rows = %s")
            cur.execute(query, (limitation_rows,))

            session['staff_message'] = "You changed the limitation number of every report to: " + str(limitation_rows)

            return redirect(f'/staff_portal')
        else:
            utils.AssertPeer(False, "Invalid method") 

    elif request.path == f'/update_email_templates_table':
        if request.method == 'POST':
            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', authenticated_user), "You don't have permission to this resource")

            background_color = request.form['background_color']
            text_align = request.form['text_align']
            border = request.form['border']
            border_collapse = request.form['border_collapse']

            utils.AssertUser(int(border) <= 10 and int(border) >= 1, "Border can be between 1 and 10")

            if background_color:
                cur.execute("UPDATE settings SET send_email_template_background_color = %s", (background_color,))
            if text_align:
                cur.execute("UPDATE settings SET send_email_template_text_align = %s", (text_align,))
            if border:
                cur.execute("UPDATE settings SET send_email_template_border = %s", (border,))
            if border_collapse:
                cur.execute("UPDATE settings SET send_email_template_border_collapse = %s", (border_collapse,))

            session['staff_message'] = "You changed the email template table look successfully"

            return redirect(f'/staff_portal')
        else:
            utils.AssertPeer(False, "Invalid method")

    elif request.path == f'/update_vat_for_all_products':
        if request.method == 'POST':
            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', authenticated_user), "You don't have permission to this resource")
            vat_for_all_products = request.form['vat_for_all_products']

            try:
                vat_for_all_products = int(vat_for_all_products)
            except:
                utils.AssertUser(False,"Enter a number !!!, Without the '%' sign")

            cur.execute("UPDATE settings SET vat = %s", (vat_for_all_products,))

            session['staff_message'] = "You changed the VAT for all products successfully"

            return redirect(f'/staff_portal')
        else:
            utils.AssertPeer(False, "Invalid method")      

    elif request.path == f'/report_sales':
        utils.AssertUser(utils.has_permission(cur, request, 'Report sales', 'read', authenticated_user), "You don't have permission to this resource")

        default_to_date = datetime.now()
        dafault_from_date = default_to_date - timedelta(days=90)

        default_to_date_str = default_to_date.strftime('%Y-%m-%d')
        default_from_date_str = dafault_from_date.strftime('%Y-%m-%d')

        if request.method == 'GET':

            return render_template('report.html', default_to_date=default_to_date_str, default_from_date=default_from_date_str)
        
        elif request.method == 'POST':

            cur.execute("SELECT * FROM settings")
            settings_rows = cur.fetchone()
            limitation_rows = settings_rows['report_limitation_rows']

            date_from = request.form.get('date_from')
            date_to = request.form.get('date_to')

            group_by = request.form.get('group_by')
            status = request.form.get('status')
            filter_by_status = request.form.get('filter_by_status', '')
            order_id = request.form.get('sale_id')

            page = request.args.get('page', 1, type=int)
            per_page = 1000  

            utils.AssertUser(date_from or date_to, "You have to select date from and date to")

            params = []

            query = "SELECT "

            if group_by == '':
                query += "users.id, orders.order_id, to_char(orders.order_date, 'YYYY-MM-DD HH24:MI:SS') AS order_date, users.first_name, "
            else:
                query += f"'-' AS id, '-' AS order_id, date_trunc('{group_by}', order_date) AS order_date, '-' AS first_name, "

            if status == '' and group_by == '':
                query += "orders.status, "
            elif status == '' and group_by != '':
                query += "'-' as status, "
            elif status != '' and group_by != '':
                query += "orders.status, "

            query += "sum(order_items.price * order_items.quantity) As total, "
            query += "round(sum(order_items.price * order_items.quantity * (CAST(order_items.vat as numeric) / 100)),2) as vat, "
            query += "round(sum(order_items.price * order_items.quantity) + sum(order_items.price * order_items.quantity * (cast(order_items.vat as numeric) / 100)),2) as total_with_vat "

            query += """
                    FROM orders 
                    JOIN order_items ON orders.order_id = order_items.order_id
                    JOIN users       ON users.id        = orders.user_id
                    WHERE order_date >= %s AND order_date <= %s 
            """

            params.append(date_from)
            params.append(date_to)

            if filter_by_status:
                query += "AND orders.status = %s "
                params.append(filter_by_status)

            if order_id:
                query += "AND orders.order_id = %s "
                params.append(order_id)

            query += "GROUP BY 1, 2, 3, 4, 5 ORDER BY order_date DESC LIMIT %s"

            query_for_total_rows = query[:len(query)-8]
            cur.execute(query_for_total_rows, params)
            total_records = len(cur.fetchall())

            params.append(limitation_rows)

            cur.execute(query, params)

            report = cur.fetchall()
            utils.trace(report)

            utils.AssertUser(report[0][0] != None and report[0][1] != None and report[0][2] != None and report[0][3] != None, "No result with this filter")

            # total_records = len(report)

            total_price = sum(row[5] for row in report)
            total_vat = sum(row[6] for row in report if row[6] is not None)
            total_price_with_vat = sum(row[7] for row in report if row[7] is not None)

            report_json = utils.serialize_report(report)

            return render_template('report.html', limitation_rows=int(limitation_rows), filter_by_status=filter_by_status,report=report, total_records=total_records, total_price_with_vat=total_price_with_vat,total_vat=total_vat,total_price=total_price, report_json=report_json, default_to_date=date_to, default_from_date=date_from)
        else:
            utils.AssertPeer(False, "Invalid url")

    elif request.path == f'/download_report_without_generating_rows_in_the_html':

        form_data = {key: request.form.get(key, '') for key in ['date_from', 'date_to', 'format']}

        if form_data['format'] == 'csv':
            def generate():
                conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

                si = io.StringIO()
                cw = csv.writer(si)
                headers = ['Date', 'Order ID', 'Customer Name', 'Total Price', 'Status']
                cw.writerow(headers)
                si.seek(0)
                yield si.getvalue()
                si.truncate(0)
                si.seek(0)
                
                offset = 0

                # while True:
                # rows_fetched = False
                batch = utils.fetch_batches(conn, form_data['date_from'], form_data['date_to'], offset)               

                for row in batch:
                    rows_fetched = True

                    for innerRow in row:
                    
                        cw.writerow(innerRow)
                        si.seek(0)
                        yield si.getvalue()
                        si.truncate(0)

                    # if not rows_fetched: 
                    #     break
                    offset += 10000

                si.close()
                conn.close()

            response = Response(stream_with_context(generate()), mimetype='text/csv')
            response.headers['Content-Disposition'] = f'attachment; filename=Sales_report.csv'
            return response


    elif request.path == f'/download_report':

        keys = ['date_from', 'date_to', 'group_by', 'status', 'filter_by_status', 'total_records', 'total_price', 'total_vat', 'total_price_with_vat','report_data', 'format']

        form_data = {key: request.form.get(key, '') for key in keys}

        report_data = json.loads(form_data['report_data'])

        headers = ['Date', 'User ID', 'Order ID', 'Price', 'VAT', 'Total order price with VAT', 'Buyer','Order Status',]

        if form_data['format'] == 'csv':

            def generate():
                si = io.StringIO()
                cw = csv.writer(si)

                cw.writerow(['Filters:'])
                filter_keys = ['Date From', 'Date To', 'Group By', 'Status', 'Filter By Status']
                for key in filter_keys:
                    cw.writerow([f'{key}:', form_data[key.lower().replace(' ', '_')]])

                cw.writerow(headers)
            
                for row in report_data:

                    date = row[0]
                    user_id = row[1]
                    order_id = row[2]
                    price = row[3]
                    vat = row[4]
                    price_with_vat = row[5]
                    name = row[6]
                    status = row[7]

                    row = [date, user_id, order_id, price, vat, price_with_vat,name, status]

                    cw.writerow(row)
                    si.seek(0)
                    yield si.getvalue()
                    si.truncate(0)
                    si.seek(0)

                cw.writerow("")
                cw.writerow(['Total Records:', form_data['total_records']])
                cw.writerow(['Total Price Without VAT:', form_data['total_price']])
                cw.writerow(['VAT:', form_data['total_vat']])
                cw.writerow(['Total Price With VAT:', form_data['total_price_with_vat']])
                si.seek(0)
                yield si.getvalue()
                si.close()

            response = Response(stream_with_context(generate()), mimetype= 'text/csv')
            response.headers['Content-Disposition'] = 'attachment; filename=report.csv'
            return response

        elif form_data['format'] == 'excel':
            wb = Workbook()
            ws = wb.active

            filter_keys = ['Date From', 'Date To', 'Group By', 'Status']
            for key in filter_keys:
                ws.append([f'{key}:', form_data[key.lower().replace(' ', '_')]])

            # headers = ['Date', 'Order IDs', 'Name of Buyers', 'Total Price', 'Order Status']
            ws.append(headers)

            # report_data = json.loads(form_data['report_data'])
            for row in report_data:
                if isinstance(row[1], list) and len(row[1]) == 1:
                    #TODO: row[1][0] -> PROMENLIVA S IME
                    row[1] = float(row[1][0])
                    row[2] = str(row[2][0])
                    row[4] = str(row[4][0])
                else:
                    row[1] = "-"
                    row[2] = "-"
                    row[4] = "-"
                ws.append(row)

            ws.append(['Total Records:', form_data['total_records'], 'Total:', form_data['total_price']])
            ws.append(['Filters:'])

            excel_bf = BytesIO()
            wb.save(excel_bf)
            excel_bf.seek(0)

            response = Response(excel_bf.getvalue(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response.headers['Content-Disposition'] = 'attachment; filename=report.xlsx'
            return response
        else:
            utils.AssertDev(False, "Invalid download format")

    elif request.path == f'/role_permissions':
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'read', authenticated_user), "You don't have permission to this resource")

        # interfaces = ['Logs', 'CRUD Products', 'Captcha Settings', 'Report sales', 'Staff roles', 'CRUD Orders', 'CRUD Users']

        cur.execute("SELECT DISTINCT interface FROM permissions ORDER BY interface ASC")

        interfaces = []
        for interface in cur.fetchall():
            interfaces.append(interface[0])

        if request.method == 'GET':
            role = request.path.split('/')[1]
            cur.execute('SELECT role_id, role_name FROM roles')
            roles = cur.fetchall()

            selected_role = int(request.args.get('role', roles[0][0] if roles else None))

            cur.execute('SELECT role_id, role_name FROM roles WHERE role_id = %s', (selected_role,))
            role_to_display = cur.fetchall()

            role_permissions = {role[0]: {interface: {'create': False, 'read': False, 'update': False, 'delete': False} for interface in interfaces} for role in role_to_display}

            cur.execute('SELECT rp.role_id, p.interface, p.permission_name FROM role_permissions AS rp JOIN permissions AS p ON rp.permission_id=p.permission_id')
            permissions = cur.fetchall()

            for role_id, interface, permission_name in permissions:
                if role_id in role_permissions and interface in role_permissions[role_id]:
                    role_permissions[role_id][interface][permission_name] = True

            return render_template('role_permissions.html', roles=roles,interfaces=interfaces, role_permissions=role_permissions, selected_role=selected_role, role_to_display=role)
    
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'update', authenticated_user), "You don't have permission to this resource")

        role_id = request.form['role']
        cur.execute('DELETE FROM role_permissions WHERE role_id = %s', (role_id,))
        for interface in interfaces:
            for action in ['create', 'read', 'update', 'delete']:
                if f'{interface}_{action}' in request.form:
                    cur.execute("SELECT permission_id FROM permissions WHERE permission_name = %s AND interface = %s", (action, interface))
                    permission_id = cur.fetchone()[0]
                    cur.execute('INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)', 
                                (role_id, permission_id))

        cur.execute("SELECT role_name FROM roles WHERE role_id = %s", (role_id,))
        role_name = cur.fetchone()[0]

        session['role_permission_message'] = f'You successfully updated permissions for role: {role_name}'

        return redirect(f'/role_permissions?role=' + role_id)

    elif request.path == f'/crud_products' and len(request.path.split('/')) == 2:

        print("Enterd crud_products read successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'read', authenticated_user), "You don't have permission to this resource")

        validated_request_args_fields = utils.check_request_arg_fields(cur=cur, request=request)

        sort_by = validated_request_args_fields['sort_by']
        sort_order = validated_request_args_fields['sort_order']
        price_min = validated_request_args_fields['price_min']
        price_max = validated_request_args_fields['price_max']

        base_query = """
                        SELECT 
                            products.id, 
                            products.name, 
                            products.price, 
                            products.quantity, 
                            products.category, 
                            currencies.symbol,
                            settings.vat,
                            products.price + (products.price * (CAST(settings.vat AS numeric) / 100)) AS product_vat_price
                        FROM products 
                            JOIN currencies ON products.currency_id = currencies.id
                            JOIN settings   ON products.vat_id      = settings.id
                        WHERE 1=1
                    """
        query_params = []

        if price_min is not '' and price_max is not '':
            base_query += " AND products.price + (products.price * (CAST(settings.vat AS numeric) / 100)) BETWEEN %s AND %s"
            query_params.extend([price_min, price_max])
        
        base_query += f"ORDER BY {sort_by} {sort_order} LIMIT 100"

        cur.execute(base_query, query_params)
        products = cur.fetchall()

        return render_template('crud.html', products=products, sort_by=sort_by, sort_order=sort_order, price_min=price_min or '', price_max=price_max or '')

    elif request.path == f'/crud_products/add_product' and len(request.path.split('/')) == 3:

        print("Enterd crud_products add successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'create', authenticated_user), "You don't have permission to this resource")

        if request.method == 'GET':

            cur.execute("SELECT symbol, id FROM currencies")
            all_currencies = cur.fetchall()


            cur.execute("SELECT DISTINCT(category) FROM products")
            categories = [row[0] for row in cur.fetchall()]  # Extract categories from tuples

            return render_template('add_product_staff.html', categories=categories, currencies=all_currencies)

        elif request.method == 'POST':
            data = process_form('CRUD Products', 'create')
            
            cur.execute(f"INSERT INTO products ({ data['fields'] }) VALUES ({ data['placeholders'] })", data['values'])

            session['crud_message'] = "Item was added successfully"

            return redirect(f'/crud_products')
        else:
            utils.AssertDev(False, "Different method")

    elif re.match(r'^/crud_products/edit_product/\d+$', request.path) and len(request.path.split('/')) == 4:

        print("Enterd crud_products edit successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'update', authenticated_user), "You don't have permission to this resource")

        product_id = request.path.split('/')[3]

        if request.method == 'GET':
            cur.execute("SELECT symbol, id FROM currencies")
            all_currencies = cur.fetchall()

            cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            product = cur.fetchone()

            print(product, flush=True)

            utils.AssertUser(product, "Invalid product")

            return render_template('edit_product.html', product=product, product_id=product_id, currencies = all_currencies)

        elif request.method == 'POST':
            data = process_form('CRUD Products', 'edit')

            print(data, flush=True)

            cur.execute("UPDATE products SET name = %s, price = %s, quantity = %s, category = %s, currency_id = %s WHERE id = %s", (data['values'][0], data['values'][1], data['values'][2], data['values'][3], data['values'][4],product_id))
            
            session['crud_message'] = "Product was updated successfully with id = " + str(product_id)

            return redirect(f'/crud_products')
        else:
            utils.AssertDev(False, "Different method")

    elif re.match(r'/crud_products/delete_product/\d+$', request.path) and len(request.path.split('/')) == 4:

        print("Enterd crud_products delete successfully", flush=True)
        
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'delete', authenticated_user), "You don't have permission to this resource")

        product_id = request.path.split('/')[3]
        cur.execute("UPDATE products SET quantity = 0 WHERE id = %s", (product_id,))

        session['crud_message'] = "Product was set to be unavailable successful with id = " + str(product_id)

        return redirect(f'/crud_products')

    elif request.path == f'/crud_staff' and len(request.path.split('/')) == 2:

        print("Enterd crud_staff read successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'read', authenticated_user), "You don't have permission to this resource")

        cur.execute("SELECT s.username, r.role_name, sr.staff_id, sr.role_id FROM staff_roles sr JOIN staff s ON s.id = sr.staff_id JOIN roles r ON r.role_id = sr.role_id")
        relations = cur.fetchall()

        return render_template('staff_role_assignment.html', relations=relations)

    elif request.path == f'/crud_staff/add_role_staff' and len(request.path.split('/')) == 3:

        print("Enterd crud_staff add successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'create', authenticated_user), "You don't have permission to this resource")

        if request.method == 'GET':
            cur.execute("SELECT id, username FROM staff")
            staff = cur.fetchall()

            cur.execute("SELECT role_id, role_name FROM roles")
            roles = cur.fetchall()

            return render_template('add_staff_role.html', staff=staff, roles=roles)

        elif request.method == 'POST':
            data = process_form('Staff roles', 'create_staff_roles')

            cur.execute("SELECT id FROM staff WHERE username = %s", (data['values'][0],))
            staff_id = cur.fetchone()[0]

            cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (data['values'][1],))
            role_id = cur.fetchone()[0]

            cur.execute(f"INSERT INTO staff_roles ({data['fields']}) VALUES ({data['placeholders']})", (staff_id, role_id))

            session['staff_message'] = "You successful gave a role: " + str(data['values'][1]) + " to user: " + str(data['values'][0])
            return redirect('/staff_portal')
        else:
            utils.AssertDev(False, "Different method")

    elif request.path == f'/crud_staff/add_staff' and len(request.path.split('/')) == 3:

        print("Enterd crud_staff add staff successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'create', authenticated_user), "You don't have permission to this resource")

        if request.method == 'GET':

            return render_template('add_staff.html')

        elif request.method == 'POST':
            data = process_form('Staff roles', 'create_staff')

            print(data, flush=True)

            cur.execute(f"INSERT INTO staff ({data['fields']}) VALUES ({data['placeholders']})", (data['values']))

            session['staff_message'] = "You successful made new user with name: " + str(data['values'][0]) 
            return redirect('/staff_portal')
        else:
            utils.AssertDev(False, "Different method")

    elif re.match(r'/crud_staff/delete_role/\d+/\d+$', request.path) and len(request.path.split('/')) == 5:

        print("Enterd crud_staff delete successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'delete', authenticated_user), "You don't have permission to this resource")

        staff_id = request.path.split('/')[3]
        role_id = request.path.split('/')[4]
        cur.execute('DELETE FROM staff_roles WHERE staff_id = %s AND role_id = %s', (staff_id, role_id))

        session['staff_message'] = "You successful deleted a role"
        return redirect(f'/staff_portal')

    elif request.path == f'/crud_orders' and len(request.path.split('/')) == 2:

        print("Enterd crud_orders read successful", flush=True)

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'read', authenticated_user), "You don't have permission for this resource")

        validated_fields = utils.check_request_arg_fields(cur, request)

        sort_by = validated_fields['sort_by']
        sort_order = validated_fields['sort_order']
        price_min = validated_fields['price_min']
        price_max = validated_fields['price_max']
        order_by_id = validated_fields['order_by_id']
        date_from = validated_fields['date_from']
        date_to = validated_fields['date_to']
        status = validated_fields['status']

        page = validated_fields['page']
        per_page = validated_fields['per_page']
        offset = validated_fields['offset']

        cur.execute("SELECT DISTINCT status FROM orders")
        statuses = cur.fetchall()

        query = """
            SELECT 
                o.order_id, 
                u.first_name || ' ' || u.last_name                    AS user_names, 
                array_agg(p.name)                                     AS product_names,
                to_char(sum(oi.quantity * oi.price),'FM999999990.00') AS order_price, 
                o.status, 
                to_char(o.order_date, 'MM-DD-YYYY HH:MI:SS')          AS formatted_order_date,
                c.symbol,
                oi.vat
            FROM orders      AS o 
            JOIN users       AS u  ON o.user_id     = u.id 
            JOIN order_items AS oi ON o.order_id    = oi.order_id 
            JOIN products    AS p  ON oi.product_id = p.id
            JOIN currencies  AS c  ON p.currency_id = c.id
            WHERE 1=1
        """

        params = []
        if order_by_id:
            query += " AND o.order_id = %s"
            params.append(order_by_id)

        if date_from and date_to:
            query += " AND o.order_date >= %s AND o.order_date <= %s"
            params.extend([date_from, date_to])
        else:
            default_to_date = datetime.now()
            dafault_from_date = default_to_date - timedelta(days=30)

            query += " AND o.order_date >= %s AND o.order_date <= %s"
            params.extend([dafault_from_date, default_to_date])

        if status:
            query += " AND o.status = %s"
            params.append(status)

        # AND products.price + (products.price * (CAST(settings.value AS numeric) / 100)) BETWEEN %s AND %s"
        if price_min and price_max:
            query += """
                        GROUP BY 
                            o.order_id, 
                            user_names, 
                            c.symbol, 
                            oi.vat 
                            HAVING sum((oi.quantity * oi.price) + ((oi.quantity * oi.price) * (CAST(oi.vat AS numeric) / 100))) >= %s AND sum((oi.quantity * oi.price) + ((oi.quantity * oi.price) * (CAST(oi.vat AS numeric) / 100))) <= %s
                    """
            params.extend([price_min, price_max])

        if price_min == '' and price_max == '':
            query += " GROUP BY o.order_id, user_names, c.symbol, oi.vat "

        query += f" ORDER BY o.order_{sort_by} {sort_order} "

        cur.execute("SELECT count(*) FROM orders")
        total_length_query = cur.fetchone()[0]

        query += "LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cur.execute(query, params)
        orders = cur.fetchall()

        loaded_orders = len(orders)

        return render_template('crud_orders.html', page=page,total_pages=total_length_query // per_page ,orders=orders, statuses=statuses, 
            current_status=status, price_min=price_min, price_max=price_max, order_by_id=order_by_id, 
            date_from=date_from, date_to=date_to, per_page=per_page, sort_by=sort_by, sort_order=sort_order)

    elif request.path == f'/crud_orders/add_order' and len(request.path.split('/')) == 3:

        print("Enterd crud_orders add successful", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'create', authenticated_user), "You don't have permission for this resource")

        if request.method == 'GET':
            cur.execute("SELECT DISTINCT status FROM orders")
            statuses = cur.fetchall()
            return render_template('add_order.html', statuses=statuses)

        elif request.method == 'POST':
            print("Enterd crud_orders add POST successful", flush=True)
            data = process_form('CRUD Orders', 'create')        

            order_data = data['orders']
            item_data = data['order_items']

            cur.execute("SELECT id FROM users WHERE id = %s", (order_data['values'][0],))

            utils.AssertUser(cur.fetchone() != None, "There is no such product with id " + str(order_data['values'][0]))
        
            try:
                #TODO: Insert da bude v otdelna fukciq i da se podavat parametrite, koito trqbva da se insertnat

                query_one = f"INSERT INTO orders ({ order_data['fields'] }) VALUES ({ order_data['placeholders'] }) RETURNING order_id"
                cur.execute(query_one, order_data['values'])
                order_id = cur.fetchone()[0]

                order_item_values = (order_id,) + item_data['values']
                query_two = f"INSERT INTO order_items (order_id, {item_data['fields']}) VALUES (%s, {item_data['placeholders']})"
                cur.execute(query_two, order_item_values)

                session['crud_message'] = "Successfully added new order with id: " + str(order_id)
                return redirect(f'/crud_orders')

            except Exception as e:
                session['crud_error'] = "Failed to add order. Please try again."
                return redirect(f'/crud_orders')
        else:
            utils.AssertUser(False, "Invalid operation")

    elif re.match(r'/crud_orders/edit_order/\d+$', request.path) and len(request.path.split('/')) == 4:

        print("Enterd crud_orders edit successful", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'update', authenticated_user), "You don't have permission for this resource")

        order_id = request.path.split('/')[3]

        if request.method == 'GET':

            # order_id = request.path.split('/')[5]

            cur.execute("SELECT DISTINCT status FROM orders")
            statuses = cur.fetchall()

            cur.execute("SELECT order_date FROM orders WHERE order_id = %s", (order_id,))
            order_date = cur.fetchone()[0]

            formatted_date = order_date.strftime('%Y-%m-%dT%H:%M:%S')

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
                """, (order_id,))

            products_from_order = cur.fetchall()

            all_products_sum_with_vat = 0
            for product in products_from_order:
                all_products_sum_with_vat += float(product[2] * product[3]) + (float(product[2] * product[3]) * (float(product[6]) / 100))

            return render_template('edit_order.html', order_id=order_id,statuses=statuses, order_date = formatted_date, products_from_order=products_from_order, all_products_sum=round(all_products_sum_with_vat,2))

        elif request.method == 'POST':

            print("Enterd crud_orders edit POST successful", flush=True)
            data = process_form('CRUD Orders', 'edit')

            cur.execute("UPDATE orders SET status = %s, order_date = %s WHERE order_id = %s", (data['values'][0], data['values'][1], order_id))
            
            session['crud_message'] = "Order was updated successfully with id = " + str(order_id)
            return redirect(f'/crud_orders')

        else:
            utils.AssertUser(False, "Invalid operation")

    elif re.match(r'/crud_orders/delete_order/\d+$', request.path) and len(request.path.split('/')) == 4:

        print("Enterd crud_orders delete successful", flush=True)

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'delete', authenticated_user), "You don't have permission to this resource")

        order_id = request.path.split('/')[3]

        cur.execute('DELETE FROM shipping_details WHERE order_id = %s', (order_id,))
        cur.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
        cur.execute('DELETE FROM orders WHERE order_id = %s', (order_id,))

        session['crud_message'] = "You successful deleted a  order with id: " + str(order_id)       

        return redirect(f'/crud_orders')

    elif request.path == f'/crud_users' and len(request.path.split('/')) == 2:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'read', authenticated_user), "You don't have permission for this resource")

        if request.method == 'GET':

            fields = utils.check_request_arg_fields(cur, request)

            cur.execute("SELECT DISTINCT verification_status FROM users")
            statuses = cur.fetchall()

            params = []
            query = """
                SELECT  id, 
                        first_name, 
                        last_name, 
                        email, 
                        verification_status, 
                        verification_code, 
                        last_active 
                FROM users
                WHERE 1=1
                """

            if fields['email']:
                query += " AND email = %s"
                params.append(fields['email'])

            if fields['user_by_id']:
                query += " AND id = %s"
                params.append(fields['user_by_id'])

            if fields['status']:
                query += " AND verification_status = %s"
                params.append(fields['status'])

            query += f" ORDER BY {fields['sort_by']} {fields['sort_order']}"

            cur.execute(query, params)
            users = cur.fetchall()

            return render_template('crud_users.html', users=users, statuses=statuses, email=fields['email'], user_by_id=fields['user_by_id'])

        elif request.method == 'POST':

            return redirect(f'/crud_users')

        else:
            utils.AssertUser(False, "Invalid method")


    elif request.path == f'/crud_users/add_user' and len(request.path.split('/')) == 3:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'create', authenticated_user), "You don't have permission for this resource")

        if request.method == 'GET':

            cur.execute("SELECT DISTINCT verification_status FROM users")
            statuses = cur.fetchall()

            return render_template("add_user.html", statuses=statuses) 

        elif request.method == 'POST':

            data = process_form('CRUD Users', 'create')

            # hashed_password = utils.hash_password(password_)

            sql_command = f"INSERT INTO users ({data['fields']}) VALUES ({data['placeholders']}) RETURNING id;"
            cur.execute(sql_command, data['values'])

            user_id = cur.fetchone()[0]

            session['crud_message'] = "You successfully added new user with id: " + str(user_id)

            return redirect(f'/crud_users')

        else:
            utils.AssertUser(False, "Invalid method")

    elif re.match(r'/crud_users/edit_user/\d+$', request.path) and len(request.path.split('/')) == 4:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'update', authenticated_user), "You don't have permission for this resource")

        if request.method == 'GET':

            user_id = request.path.split('/')[3]

            cur.execute("SELECT first_name, last_name, email, verification_status FROM users WHERE id = %s", (user_id,))
            first_name, last_name, email, verification_status = cur.fetchall()[0]

            return render_template('edit_user.html', first_name=first_name, last_name=last_name, email=email, verification_status=verification_status, user_id=user_id)

        elif request.method == 'POST':

            user_id = request.path.split('/')[3]
            data = process_form('CRUD Users', 'edit')

            cur.execute("""
                UPDATE users 
                SET 
                    first_name = %s, 
                    last_name = %s, 
                    email = %s, 
                    verification_status = %s 
                WHERE id = %s""", (data['values'][0], data['values'][1], data['values'][2], data['values'][3], user_id))

            session['crud_message'] = "You successfully edited user with id: " + str(user_id)

            return redirect(f'/crud_users')

        else:
            utils.AssertUser(False, "Invalid method")

    elif re.match(r'/crud_users/delete_user/\d+$', request.path) and len(request.path.split('/')) == 4:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'delete', authenticated_user), "You don't have permission to this resource")

        user_id = request.path.split('/')[3]

        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        # cur.execute("UPDATE users SET verification_status = False WHERE id = %s", (user_id,))

        session['crud_message'] = "You successfully deleted user with id: " + str(user_id)

        return redirect(f'/crud_users')

    elif request.path == f'/template_email':

        if request.method == 'GET':

            cur.execute("SELECT * FROM email_template")
            email_templates_rows = cur.fetchall()

            cur.execute("SELECT * FROM settings")
            settings_row = cur.fetchone()

            for template in email_templates_rows:
                if template['name'] == "Verification Email":
                    verification_email_values = [template['name'],template['subject'],template['body'], template['sender']]

                elif template['name'] == "Purchase Email":
                    purchase_email_values = [template['name'],template['subject'],template['body'], template['sender']]

                elif template['name'] == "Payment Email":
                    payment_email_values = [template['name'],template['subject'],template['body'], template['sender']]

                else:
                    utils.AssertDev(False, "No information in db for email_template")

            if verification_email_values and purchase_email_values and payment_email_values:
                name, subject, body, sender = verification_email_values
                name_purchase, subject_purchase, body_purchase, sender_purchase = purchase_email_values
                name_payment, subject_payment, body_payment, sender_payment = payment_email_values

                return render_template('template_email.html', subject=subject, body=body, tepmplate_subject_purchase=subject_purchase, 
                                        tepmplate_body_purchase=body_purchase, tepmplate_subject_payment=subject_payment, tepmplate_body_payment=body_payment,
                                        background_color=settings_row['send_email_template_background_color'], text_align=settings_row['send_email_template_text_align'],
                                        border=settings_row['send_email_template_border'], border_collapse=settings_row['send_email_template_border_collapse'])

        elif request.method == 'POST':
            
            data = process_form('Template email', 'edit')

            cur.execute("""
                UPDATE email_template 
                SET 
                    subject = %s, 
                    body = %s
                WHERE name = 'Verification Email'""", (data['values'][0], data['values'][1]))

            session['staff_message'] = "You successfully updated template for sending emails"

            return redirect(f'/staff_portal')

        else:
            utils.AssertUser(False, "Invalid method")

    elif request.path == f'/template_email_purchase':

        if request.method == 'POST':

            data_purchase = process_form('Template email purchase', 'edit')

            utils.trace(data_purchase)

            cur.execute("""
                UPDATE email_template 
                SET 
                    subject = %s,
                    body = %s 
                WHERE name = 'Purchase Email' """, (data_purchase['values'][0],data_purchase['values'][1]))
            session['staff_message'] = "You successfully updated template for sending purchase email"

            return redirect(f'/staff_portal')

        else:
           utils.AssertUser(False, "Invalid method")

    elif request.path == f'/template_email_payment':

        if request.method == 'POST':

            data_payment = process_form('Template email payment', 'edit')

            utils.trace(data_payment)

            cur.execute("""
                UPDATE email_template 
                SET 
                    subject = %s,
                    body = %s 
                WHERE name = 'Payment Email ' """, (data_payment['values'][0], data_payment['values'][1]))
            session['staff_message'] = "You successfully updated template for sending payment email"

            return redirect(f'/staff_portal')

        else:
           utils.AssertUser(False, "Invalid method")  

    else:
        utils.AssertPeer(False, "Invalid url")

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

url_to_function_map = [
    (r'(?:/[A-z]+)?/registration', registration),
    (r'(?:/[A-z]+)?/refresh_captcha', refresh_captcha),
    (r'(?:/[A-z]+)?/verify', verify),
    (r'/login', login),
    (r'/home(?:\?page=([1-9]+)\?[A-z,\=,\&]+)?', home),
    (r'(?:/[A-z]+)?/logout', logout),
    (r'(?:/[A-z]+)?/profile', profile),
    (r'(?:/[A-z]+)?/update_profile', update_profile),
    (r'(?:/[A-z]+)?/delete_account', delete_account),
    (r'(?:/[A-z]+)?/recover_password', recover_password),
    (r'(?:/[A-z]+)?/resend_verf_code', resend_verf_code),
    (r'(?:/[A-z]+)?/send_login_link', send_login_link),
    (r'/log', login_with_token),
    (r'(?:/[A-z]+)?/image/(\d+)', serve_image),
    # (r'(?:/[A-z]+)?(?:/back_office)?/crud_products_edit_picture/(\d+)', serve_image_crud_products_edit),
    (r'/generate_orders', generate_orders),
    (r'(?:/[A-z]+)?/add_to_cart', add_to_cart_meth),
    (r'(?:/[A-z]+)?/cart', cart),
    (r'(?:/[A-z]+)?/update_cart_quantity', update_cart_quantity),
    (r'(?:/[A-z]+)?/remove_from_cart', remove_from_cart_meth),
    (r'(?:/[A-z]+)?/finish_payment', finish_payment),
    (r'(?:/[A-z]+)?/user_orders', user_orders),
    (r'(?:/[A-z]+)?/staff_login', staff_login),
    (r'(?:/[A-z]+)?(?:/back_office)?/staff_portal', staff_portal),
    (r'(?:/[A-z]+)?(?:/back_office)?/logout_staff', logout_staff),
    (r'(?:/[A-z]+)?(?:/back_office)?/(crud_products_edit_picture|error_logs|update_captcha_settings|report_sales|crud_products|crud_staff|role_permissions|download_report|crud_orders|active_users|download_report_without_generating_rows_in_the_html|upload_products|crud_users)(?:/[\w\d\-_/]*)?', back_office_manager),
]


url_to_function_map_front_office = [
    (r'/registration', registration),
    (r'/refresh_captcha', refresh_captcha),
    (r'/verify', verify),
    (r'/login', login),
    (r'/home', home),
    (r'/home(?:\?page=([1-9]+)\?[A-z,\=,\&]+)?', home),
    (r'/logout', logout),
    (r'/profile', profile),
    (r'/update_profile', update_profile),
    (r'/delete_account', delete_account),
    (r'/recover_password', recover_password),
    (r'/resend_verf_code', resend_verf_code),
    (r'/send_login_link', send_login_link),
    (r'/log', login_with_token),
    (r'/image/(\d+)', serve_image),
    (r'/generate_orders', generate_orders),
    (r'/add_to_cart', add_to_cart_meth),
    (r'/cart', cart),
    (r'/update_cart_quantity', update_cart_quantity),
    (r'/remove_from_cart', remove_from_cart_meth),
    (r'/finish_payment', finish_payment),
    (r'/user_orders', user_orders),
]

url_to_function_map_back_office = [
    (r'/staff_login', staff_login),
    (r'/staff_portal', staff_portal),
    (r'/logout_staff', logout_staff),
    (r'/(crud_products_edit_picture|error_logs|update_captcha_settings|report_sales|crud_products|crud_staff|role_permissions|download_report|crud_orders|active_users|download_report_without_generating_rows_in_the_html|upload_products|crud_users|template_email|update_report_limitation_rows|update_email_templates_table|update_vat_for_all_products)(?:/[\w\d\-_/]*)?', back_office_manager),
]

def map_function(map_route):
    for pattern, function in map_route:
        match = re.match(pattern, request.path)
        if match:
            return function

@app.endpoint("handle_request")
def handle_request(username=None, path=''):
    conn = None
    cur = None
    session_id = request.cookies.get('session_id')
    try:
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # traceback.print_stack()
        utils.trace("conn main.py")
        utils.trace(conn)
        utils.trace("cur main.py")
        utils.trace(cur)

        utils.trace("request.path")
        utils.trace(request.path)

        #TODO Validaciq na cookie prez bazata + req.args
        authenticated_user = sessions.get_current_user(session_id, cur=cur, conn=conn)

        utils.trace("authenticated_user")
        utils.trace(authenticated_user)

        funtion_to_call = None
        match = None

        # True for front office, false for back office
        flag_office = None

        if authenticated_user is not None:
            flag_office = sessions.get_session_cookie_type(session_id, cur)
        else:
            flag_office = True

        if not flag_office or request.path == '/staff_login':
            utils.trace("Entered back office loop")
            funtion_to_call = map_function(url_to_function_map_back_office)
        else:
            utils.trace("Entered front office loop")
            funtion_to_call = map_function(url_to_function_map_front_office)

     
        if flag_office and authenticated_user is not None:
            cur.execute("SELECT last_active FROM users WHERE email = %s", (authenticated_user,))
            current_user_last_active = cur.fetchone()[0]
            cur.execute("UPDATE users SET last_active = now() WHERE email = %s", (authenticated_user,))
        else:
            pass

        utils.AssertDev(callable(funtion_to_call), "You are trying to invoke something that is not a function")

        if match:
            response = funtion_to_call(conn, cur, *match.groups())
        else:
            response = funtion_to_call(conn, cur)

        conn.commit()

        send_email = session.get('send_email', False)
        send_mail_data = session.get('send_mail_data', {})

        if send_email:
            utils.trace("ENTERED SEND MAIL TRUE")

            send_mail.send_mail(
                products=send_mail_data['products'],
                shipping_details=send_mail_data['shipping_details'],
                total_sum=send_mail_data['total_sum'],
                total_with_vat=send_mail_data['total_with_vat'], 
                provided_sum=send_mail_data['provided_sum'],                 
                user_email=send_mail_data['user_email'],
                cur=send_mail_data['cur'], 
                conn=send_mail_data['conn'], 
                email_type=send_mail_data['email_type'], 
                app=send_mail_data['app'],
                mail=send_mail_data['mail']
            )

            session['send_email'] = False
            session['send_mail_data'] = {}

        return response

    except Exception as message:

        user_email = sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)
        traceback_details = traceback.format_exc()

        log_exception(exception_type=message.__class__.__name__, message=str(message), email=user_email)

        print(f"Day: {datetime.now()} = ERROR by = {user_email} - {traceback_details} = error class name = {message.__class__.__name__} - Dev message: {message}", flush=True)

        # != 'WrongUSerInputException'
        if message.__class__.__name__ != 'WrongUserInputException':
            message = 'Internal error'
            print(f"User message: {message}", flush=True)

        # TODO: Change url for QA + remove
        if request.url == 'http://127.0.0.1:5000/staff_login':
            session['staff_login'] = "Yes"

        utils.add_recovery_data_in_session(session.get('recovery_data'))

        conn.rollback()

        return render_template("error.html", message = str(message), redirect_url = request.url)
    finally:

        if conn is not None:
            conn.close()
        if cur is not None:
            cur.close()

if __name__ == '__main__':
    app.run(debug=True)
    # flask run --host=0.0.0.0 --port=5000