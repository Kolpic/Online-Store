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
from project import sessions
from .models import User
from sqlalchemy import or_
import traceback
import itertools
import time

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
# last_cleanup = 0

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
            'name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 5 and len(x) <= 30, "Template name should be between 5 and 30 symbols")]},
            'subject': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 5 and len(x) <= 30, "Email subject should be between 5 and 30 symbols")]},
            'body': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 10 and len(x) <= 255, "Email subject should be under 255 symbols")]},
            'sender': {'type': str, 'required': True, 'conditions': [(lambda x: '@' in x, "Invalid email")]},
        }
    },
    'Template email purchase': {
        'edit': {
            'body_purchase': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 10 and len(x) <= 255, "Email subject should be under 255 symbols")]},
        }
    },
    'Template email payment': {
        'edit': {
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

def registration(conn, cur):
    user_ip = request.remote_addr

    assertIsProvidedMethodsTrue('GET','POST')

    if request.method == 'GET':
        form_data = session.get('form_data_stack', []).pop() if 'form_data_stack' in session and len(session['form_data_stack']) > 0 else None
        if form_data:
            session.modified = True
        first_captcha_number = random.randint(0,100)
        second_captcha_number = random.randint(0,100)

        cur.execute("INSERT INTO captcha(first_number, second_number, result) VALUES (%s, %s, %s) RETURNING id", (first_captcha_number, second_captcha_number, first_captcha_number + second_captcha_number))
        captcha_id = cur.fetchone()[0]
     
        cur.execute("SELECT * FROM country_codes")
        country_codes = cur.fetchall()

        session["captcha_id"] = captcha_id
        return render_template('registration.html', country_codes=country_codes, form_data=form_data, captcha = {"first": first_captcha_number, "second": second_captcha_number})

    elif request.method == 'POST':

        form_data = request.form.to_dict()
        session['form_data'] = form_data
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

        utils.AssertUser(password_ == confirm_password_, "Password and Confirm Password fields are different")
        utils.AssertUser(len(address) >= 5 and len(address) <= 50, "Address must be between 5 and 50 characters long")
        regexx = r'^\d{7,15}$'
        utils.AssertUser(re.fullmatch(regexx, phone), "Phone number format is not valid. The number should be between 7 and 15 digits")
        utils.AssertUser(gender == 'male' or gender == 'female', "Gender must be Male of Female")

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
                
        captcha_id = session.get("captcha_id")
        cur.execute("SELECT result FROM captcha WHERE id = %s", (captcha_id,))
        result = cur.fetchone()[0]

        hashed_password = utils.hash_password(password_)
        verification_code = os.urandom(24).hex()

        if captcha_ != result:  
            utils.add_form_data_in_session(form_data)
            new_attempts = attempts + 1
            if attempt_record:
                cur.execute("UPDATE captcha_attempts SET attempts = %s, last_attempt_time = CURRENT_TIMESTAMP WHERE id = %s", (new_attempts, attempt_id))
            else:
                cur.execute("INSERT INTO captcha_attempts (ip_address, attempts, last_attempt_time) VALUES (%s, 1, CURRENT_TIMESTAMP)", (user_ip,))
            raise exception.WrongUserInputException("Invalid CAPTCHA. Please try again")
        else:
            if attempt_record:
                cur.execute("DELETE FROM captcha_attempts WHERE id = %s", (attempt_id,))

        utils.AssertUser(len(first_name) >= 3 and len(first_name) <= 50, "First name is must be between 3 and 50 symbols")
        utils.AssertUser(len(last_name) >= 3 and len(last_name) <= 50, "Last name must be between 3 and 50 symbols")
            
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
        utils.AssertUser(re.fullmatch(regex, email), "Email is not valid")
        
        cur.execute("SELECT email FROM users WHERE email = %s", (email,))
        is_email_present_in_database = cur.fetchone()
        cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
        is_email_verified = cur.fetchone()

        if is_email_present_in_database != None:
            utils.AssertUser(not(is_email_present_in_database[0] and is_email_verified[0]), "There is already registration with this email")
            utils.AssertUser(not(is_email_present_in_database[0] and not is_email_verified[0]), "Account was already registered with this email, but it's not verified")

        cur.execute("SELECT id FROM country_codes WHERE code = %s", (country_code,))
        country_code_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO users 
                (first_name, last_name, email, password, verification_code, address, gender, phone, country_code_id) 
            VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, 
            (first_name, last_name, email, hashed_password, verification_code, address, gender, phone,country_code_id))

        send_verification_email(email, verification_code, cur)

        session['verification_message'] = 'Successful registration, we send you a verification code on the provided email'
        return redirect("/verify")

    else:
        utils.AssertUser(False, "Invalid method")

def send_verification_email(user_email, verification_code, cur):

    cur.execute("SELECT subject, sender, body FROM email_template WHERE name = 'Verification Email'")
    values = cur.fetchone()

    cur.execute("SELECT first_name, last_name FROM users WHERE email = %s", (user_email,))
    user_data = cur.fetchone()

    utils.trace(values)

    if values and user_data:
        subject, sender, body = values
        first_name, last_name = user_data

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

def verify(conn, cur):
    assertIsProvidedMethodsTrue('GET','POST')

    if request.method == 'GET':
        form_data = session.get('form_data_stack', []).pop() if 'form_data_stack' in session and len(session['form_data_stack']) > 0 else None
        if form_data:
            session.modified = True
        return render_template('verify.html', form_data=form_data)

    form_data = request.form.to_dict()
    session['form_data'] = form_data
    email = request.form['email']
    verification_code = request.form['verification_code']

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))

    utils.AssertUser(not cur.rowcount == 0, "There is no registration with this email")

    email_from_database = cur.fetchone()['email']

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_verified = cur.fetchone()['verification_status']

    cur.execute("SELECT verification_code FROM users WHERE email = %s", (email,))
    verification_code_database = cur.fetchone()['verification_code']

    utils.AssertUser(email_from_database == email, "You entered different email")
    utils.AssertUser(not is_verified, "The account is already verified")
    utils.AssertUser(verification_code_database == verification_code, "The verification code you typed is different from the one we send you")
    
    cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", (verification_code,))

    session['login_message'] = 'Successful verification'
    return redirect("/login") 

def login(conn, cur):
    assertIsProvidedMethodsTrue('GET','POST')

    if request.method == 'GET':
        form_data = session.get('form_data_stack', []).pop() if 'form_data_stack' in session and len(session['form_data_stack']) > 0 else None
        if form_data:
            session.modified = True
        return render_template('login.html', form_data=form_data)

    form_data = request.form.to_dict()
    session['form_data'] = form_data
    email = request.form['email']
    password_ = request.form['password']

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("""
                SELECT 
                    email, 
                    verification_status, 
                    password
                FROM users
                WHERE email = %s
                """, (email,))
    user_data = cur.fetchone()

    utils.AssertUser(user_data, "There is no registration with this email")
    utils.AssertUser(utils.verify_password(password_, user_data['password']), "Invalid email or password")
    utils.AssertUser(user_data['verification_status'], "Your account is not verified or has been deleted")

    session_id = sessions.create_session(os, datetime, timedelta, email, cur, conn)
    response = make_response(redirect('/home'))
    response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')

    return response

def home(conn, cur, page = 1):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login') 

    page = request.args.get('page', 1, type=int)

    cur.execute("SELECT DISTINCT(category) FROM products")
    categories = [row[0] for row in cur.fetchall()]  # Extract categories from tuples

    first_name, last_name, email__ = utils.getUserNamesAndEmail(conn, cur, is_auth_user)

    prodcuts_user_wants = request.args.get('products_per_page', 10)
    if prodcuts_user_wants == '':
        prodcuts_user_wants = 10

    products_per_page = int(prodcuts_user_wants)
    offset = 0
    if page == None:
        page = 1
        offset = 10
    else:
        offset = (page - 1) * products_per_page
    
    sort_by = request.args.get('sort','id')
    sort_order = request.args.get('order', 'asc')
    product_name = request.args.get('product_name', '')
    product_category = request.args.get('product_category', '')
    price_min = request.args.get('price_min', '')
    price_max = request.args.get('price_max', '')

    valid_sort_columns = {'price':'price', 'category':'category', 'name':'name'}
    sort_column = valid_sort_columns.get(sort_by, 'id')
    order_by_clause = f"{sort_column} {'DESC' if sort_order == 'desc' else 'ASC'}"

    name_filter = f" AND name ILIKE %s" if product_name else ''
    category_filter = f" AND category ILIKE %s" if product_category else ''
    price_filter = ""
    query_params = []

    if product_name:
        query_params.append(f"%{product_name}%")
    if product_category:
        query_params.append(f"%{product_category}%")

    if price_min.isdigit() and price_max.isdigit():
        price_filter = " AND price BETWEEN %s AND %s"
        query_params.extend([price_min, price_max])

    query = f"SELECT p.id, p.name, p.price, p.quantity, p.category, c.symbol FROM products AS p JOIN currencies AS c ON p.currency_id=c.id WHERE TRUE{name_filter}{category_filter}{price_filter} ORDER BY {order_by_clause} LIMIT %s OFFSET %s"
    query_params.extend([products_per_page, offset])

    cur.execute(query,tuple(query_params))
    products = cur.fetchall()

    count_query = f"SELECT COUNT(*) FROM products WHERE TRUE{name_filter}{category_filter}{price_filter}"
    cur.execute(count_query, tuple(query_params[:-2]))
    total_products = cur.fetchone()[0]
    utils.AssertUser(total_products, 'No results with this filter')
    # total_pages = (total_products + products_per_page - 1)
    # total_pages = int(total_products / products_per_page) + 1
    total_pages = (total_products // products_per_page) + (1 if total_products % products_per_page > 0 else 0)

    cur.execute("SELECT id FROM users WHERE email = %s", (is_auth_user,))
    user_id = cur.fetchone()[0]

    cart_count = get_cart_items_count(conn, cur, user_id)

    return render_template('home.html', first_name=first_name, last_name=last_name, email = email__,products=products, page=page, total_pages=total_pages, sort_by=sort_by, sort_order=sort_order, product_name=product_name, product_category=product_category, cart_count=cart_count, categories=categories)

def logout(conn, cur):
    session_id = request.cookies.get('session_id')

    cur.execute("DELETE FROM custom_sessions WHERE session_id = %s", (session_id,))
    response = make_response(redirect('/login'))
    response.set_cookie('session_id', '', expires=0)
    return response

def profile(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login') 
    
    cur.execute("SELECT first_name, last_name, email FROM users WHERE email = %s", (is_auth_user,))
    user_details = cur.fetchone()

    if user_details:
        return render_template('profile.html', user_details=user_details, first_name=user_details[0], last_name=user_details[1], email=user_details[2])
    
    return render_template('profile.html')

def update_profile(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login')

    first_name = request.form['first-name']
    last_name = request.form['last-name']
    email = request.form['email']
    password_ = request.form['password']
    
    query_string = "UPDATE users SET "
    fields_list = []
    updated_fields = []

    name_regex = r'^[A-Za-z]+$'

    if first_name:
        if len(first_name) < 3 or len(first_name) > 50 or not re.match(name_regex, first_name):
            session['settings_error'] = 'First name must be between 3 and 50 letters and contain no special characters or digits'
            return redirect('/profile')
        query_string += "first_name = %s, "
        fields_list.append(first_name)
        updated_fields.append("first name")
    if last_name:
        if len(last_name) < 3 or len(last_name) > 50 or not re.match(name_regex, last_name):
            session['settings_error'] = 'Last name must be between 3 and 50 letters'
            return redirect('/profile')
        query_string += "last_name = %s, "
        fields_list.append(last_name)
        updated_fields.append("last name")
    if email:
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
        if not (re.fullmatch(regex, email)):
            session['settings_error'] = 'Invalid email'
            return redirect('/profile')
        query_string += "email = %s, "
        fields_list.append(email)
        updated_fields.append("email")
    if password_:
        if len(password_) < 8 or len(password_) > 20:
            session['settings_error'] = 'Password must be between 8 and 20 symbols'
            return redirect('/profile')
        query_string += "password = %s, "
        hashed_password = utils.hash_password(password_)
        fields_list.append(hashed_password)
        updated_fields.append("password")

    if first_name == "" and last_name == "" and email == "" and password_ == "":
        session['settings_error'] = 'You have to insert data in at least one field'
        return redirect('/profile')

    query_string = query_string[:-2]
    query_string += " WHERE email = %s"

    email_in_session = sessions.get_current_user(request, cur)
    fields_list.append(email_in_session)

    cur.execute(query_string, (fields_list))
    
    # Update session email if email was changed
    if email:
        sessions.update_current_user_session_data(cur, conn, email, sessions.get_user_session_id(request))
    
    updated_fields_message = ', '.join(updated_fields)
    session['home_message'] = f"You successfully updated your {updated_fields_message}."
    return redirect('/home')

def delete_account(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login')

    cur.execute("DELETE FROM users WHERE email = %s", (is_auth_user,))

    cur.execute("DELETE FROM custom_sessions WHERE session_id = %s", (session_id,))
    response = make_response(redirect('/login'))
    response.set_cookie('session_id', '', expires=0)
    session['login_message'] = 'You successful deleted your account'
    return response
# 
def recover_password(conn, cur):
    assertIsProvidedMethodsTrue('POST')

    email = request.form['recovery_email']
    new_password = os.urandom(10).hex()

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    utils.AssertUser(cur.rowcount == 1, "You entered non existent email")

    hashed_password = utils.hash_password(new_password)

    cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))

    send_recovey_password_email(email, new_password)
    
    session['login_message'] = 'A recovery password has been sent to your email.'
    return redirect('/login')

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
    assertIsProvidedMethodsTrue('POST') 
    
    email = request.form['resend_verf_code']
    
    login_token = os.urandom(24).hex()

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    utils.AssertUser(not cur.rowcount == 0, "There is no registration with this email")

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_verified = cur.fetchone()[0]

    utils.AssertUser(not is_verified, "The account is already verified")
    
    expiration_time = datetime.now() + timedelta(hours=1)

    cur.execute("INSERT INTO tokens(login_token, expiration) VALUES (%s, %s)", (login_token, expiration_time))

    cur.execute("SELECT id FROM tokens WHERE login_token = %s", (login_token,))
    token_id = cur.fetchone()[0]
    cur.execute("UPDATE users SET token_id = %s WHERE email = %s", (token_id, email))

    login_link = f"http://10.20.3.101:5000/log?token={login_token}"

    send_verification_link(email, login_link)

    session['login_message'] = 'A login link has been sent to your email.'

    return redirect('/login')

def send_verification_link(user_email, verification_link):
    with app.app_context():
        msg = Message('Email Verification',
                sender = 'galincho112@gmail.com',
                recipients = [user_email])
    msg.body = 'Click the link to go directly to your profile: ' + verification_link
    mail.send(msg)

def login_with_token(conn, cur):
    assertIsProvidedMethodsTrue('GET')
    
    token = request.args.get('token')

    if not token:
        session['registration_error'] = 'Invalid login token'
        return redirect('/registration')
    
    db_name = config.database
    db_user = config.user
    db_password = config.password
    db_host = config.host

    cur.execute("SELECT id, expiration FROM tokens WHERE login_token = %s", (token,))

    token_data = cur.fetchone()

    if not token_data or token_data[1] < datetime.now():
        session['registration_error'] = 'Invalid login token'
        return redirect('/login')
    
    cur.execute("SELECT * FROM users WHERE token_id = %s", (token_data[0],))
    user = cur.fetchone()

    if not user:
        session['registration_error'] = 'Invalid user'
        return redirect('/login')
    
    # cur.execute("DELETE token_id FROM users WHERE id = %s", (user[0],))

    email = user[3]

    cur.execute("UPDATE users SET token_id = NULL WHERE email = %s", (email,))

    cur.execute("DELETE FROM tokens WHERE id = %s", (token_data[0],))

    cur.execute("UPDATE users SET verification_status = true WHERE email = %s", (email,))

    session['user_email'] = email   
    return redirect('/home')

def log_exception(exception_type, message ,email = None):
    conn_new = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur_new = conn_new.cursor()

    cur_new.execute("INSERT INTO exception_logs (user_email, exception_type, message) VALUES (%s, %s, %s)", (email, exception_type, message))

    conn_new.commit()
    conn_new.close()
    cur_new.close()

def add_product(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
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

def serve_image(conn, cur, product_id):
    cur.execute("SELECT image FROM products WHERE id = %s", (product_id,))
    image_blob = cur.fetchone()[0]
    return Response(image_blob, mimetype='jpeg')

def add_to_cart(conn, cur, user_id, product_id, quantity):
    cur.execute("SELECT cart_id FROM carts WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    if result:
        cart_id = result[0]
    else:
        cur.execute("INSERT INTO carts(user_id) VALUES (%s) RETURNING cart_id", (user_id,))
        cart_id = cur.fetchone()[0]
    
    cur.execute("SELECT id FROM cart_itmes WHERE cart_id = %s AND product_id = %s", (cart_id, product_id))
    item = cur.fetchone()
    if item:
        cur.execute("UPDATE cart_itmes SET quantity = quantity + %s WHERE id = %s", (quantity, item[0]))
    else:
        cur.execute("INSERT INTO cart_itmes (cart_id, product_id, quantity) VALUES (%s, %s, %s)", (cart_id, product_id, quantity))
    return "You successfully added item."

def view_cart(conn, cur, user_id):
    cur.execute("""
                SELECT p.name, p.price, ci.quantity, p.id, currencies.symbol
                FROM     CARTS      AS c 
                    JOIN cart_itmes AS ci ON c.cart_id     = ci.cart_id 
                    JOIN products   AS p  ON ci.product_id = p.id
                    JOIN currencies AS currencies  ON p.currency_id = currencies.id
                WHERE c.user_id = %s
                """, (user_id,))
    items = cur.fetchall()
    return items

def get_cart_items_count(conn, cur, user_id):
    cur.execute("""
                SELECT p.name, p.price, ci.quantity, p.id FROM CARTS AS c 
                JOIN cart_itmes AS ci ON c.cart_id=ci.cart_id 
                JOIN products AS p ON ci.product_id=p.id 
                WHERE c.user_id = %s
                """, (user_id,))
    items = cur.fetchall()
    return len(items)

def remove_from_cart(conn, cur, item_id):
    cur.execute("DELETE FROM cart_itmes where product_id = %s", (item_id,))
    return "You successfully deleted item."

def add_to_cart_meth(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login')

    cur.execute("SELECT id FROM users WHERE email = %s", (is_auth_user,))
    user_id = cur.fetchone()[0]

    product_id = request.form['product_id']
    quantity = request.form.get('quantity', 1)

    response = add_to_cart(conn, cur, user_id, product_id, quantity)
    newCartCount = get_cart_items_count(conn, cur, user_id)

    return jsonify({'message':response, 'newCartCount': newCartCount})

def cart(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login')
    
    if request.method == 'GET':
        form_data = session.get('form_data_stack', []).pop() if 'form_data_stack' in session and len(session['form_data_stack']) > 0 else None

        if form_data:
            session.modified = True

        cur.execute("SELECT id FROM users WHERE email = %s", (is_auth_user,))
        user_id = cur.fetchone()[0]
        items = view_cart(conn, cur, user_id)


        total_sum = sum(item[1] * item[2] for item in items)
        cur.execute("SELECT * FROM country_codes")
        country_codes = cur.fetchall()

        cur.execute("SELECT first_name, last_name FROM users WHERE email = %s", (is_auth_user,))
        user_details = cur.fetchone()

        return render_template('cart.html', items=items, total_sum=total_sum, country_codes=country_codes, form_data=form_data, first_name=user_details[0], last_name=user_details[1], email=is_auth_user)
   
    elif request.method == 'POST':

        form_data = request.form.to_dict()
        session['form_data'] = form_data
        email = request.form['email'].strip()
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        town = request.form['town'].strip()
        address = request.form['address'].strip()
        country_code = request.form['country_code']
        phone = request.form['phone'].strip()

        cur.execute("SELECT id FROM users WHERE email = %s", (is_auth_user,))
        user_id = cur.fetchone()[0]
        regexx = r'^\d{7,15}$'

        # Check fields
        utils.AssertUser(len(first_name) >= 3 and len(first_name) <= 50, "First name is must be between 3 and 50 symbols")
        utils.AssertUser(len(last_name) >= 3 and len(last_name) <= 50, "Last name must be between 3 and 50 symbols")
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
        utils.AssertUser(re.fullmatch(regex, email), "Email is not valid")
        utils.AssertUser(re.fullmatch(regexx, phone), "Phone number format is not valid. The number should be between 7 and 15 digits")
        utils.AssertUser(phone[0] != "0", "Phone number format is not valid.")

        # Retrieve cart items for the user
        cur.execute("""
                    SELECT c.cart_id FROM users AS u 
                    JOIN carts AS c ON u.id = c.user_id
                    WHERE u.id = %s
                    """, (user_id,))
        cart_id = cur.fetchone()[0]

        cur.execute("""
                    SELECT ci.product_id, p.name, ci.quantity, p.price, currencies.symbol 
                    FROM cart_itmes     AS ci
                        JOIN products   AS p          ON ci.product_id = p.id
                        JOIN currencies AS currencies ON p.currency_id = currencies.id
                    WHERE ci.cart_id = %s
                    """, (cart_id,))
        cart_items = cur.fetchall()

        cur.execute("SELECT quantity FROM products WHERE id = %s", (cart_items[0][0],))
        quantity_db = cur.fetchone()[0]

        # Check and change quantity 
        for item in cart_items:
            product_id_, name, quantity, price, symbol = item
            if quantity > quantity_db:
                session['cart_error'] = "We don't have " + str(quantity) + " from product: " + str(name) + " in our store. You can purchase less or to remove the product from your cart"
                utils.add_form_data_in_session(session.get('form_data'))
                return redirect('/cart')
            cur.execute("UPDATE products SET quantity = quantity - %s WHERE id = %s", (quantity, product_id_))

        # current_prices = {item['poroduct_id']: item['price'] for item in cart_items}
        price_mismatch = False
        for item in cart_items:
            product_id, name, quantity, cart_price, symbol = item
            cur.execute("SELECT price FROM products WHERE id = %s", (product_id,))
            current_price = cur.fetchone()[0]
            if current_price != cart_price:
                # Price can be updated here
                price_mismatch = True
                break
        utils.AssertUser(not price_mismatch, "The price on some of your product's in the cart has been changed, you can't make the purchase")
        # Build JSON object of cart items if no mismatch
        products_json = [{"product_id": item[0], "name": item[1], "quantity": item[2], "price": str(item[3])} for item in cart_items]

        # First make order, then make shipping_details #
        formatted_datetime = datetime.now().strftime('%Y-%m-%d')
        # cur.execute("INSERT INTO orders (user_id, status, product_details, order_date) VALUES (%s, %s, %s, %s) RETURNING order_id", (user_id, "Ready for Paying", json.dumps(products_json), formatted_datetime))
        # order_id = cur.fetchone()[0]
        # #
        cur.execute("INSERT INTO orders (user_id, status, order_date) VALUES (%s, %s, CURRENT_TIMESTAMP) RETURNING order_id", (user_id, "Ready for Paying")) #formatted_datetime
        order_id = cur.fetchone()[0]

        # Insert order items into order_items table
        for item in cart_items:
            cur.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)", (order_id, item[0], item[2], item[3]))

        cur.execute("SELECT id FROM country_codes WHERE code = %s", (country_code,))
        country_code_id = cur.fetchone()[0]
        cur.execute("INSERT INTO shipping_details (order_id, email, first_name, last_name, town, address, phone, country_code_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (order_id, email, first_name, last_name, town, address, phone, country_code_id))

        # Total sum to be passed to the payment.html
        items = view_cart(conn, cur, user_id)
        total_sum = sum(item[1] * item[2] for item in items)

        # When the purchase is made we empty the user cart 
        cur.execute("SELECT cart_id FROM carts WHERE user_id = %s", (user_id,))
        cart_id = cur.fetchone()[0]
        cur.execute("DELETE FROM cart_itmes WHERE cart_id = %s", (cart_id,))

        cur.execute("""
                    SELECT shd.shipping_id, shd.order_id, shd.email, shd.first_name, shd.last_name, shd.town, shd.address, shd.phone, cc.code 
                    FROM shipping_details AS shd 
                    JOIN orders AS o ON shd.order_id=o.order_id 
                    JOIN country_codes AS cc ON shd.country_code_id = cc.id 
                    WHERE o.order_id = %s
                    """, (order_id,))
        shipping_details = cur.fetchall()

        send_purchase_email(cart_items, shipping_details, is_auth_user, cur)

        session['payment_message'] = "You successful made an order with id = " + str(order_id)

        cur.execute("SELECT first_name, last_name FROM users WHERE email = %s", (is_auth_user,))
        user_details = cur.fetchone()

        return render_template('payment.html', order_id=order_id, order_products=cart_items, shipping_details=shipping_details, total_sum=total_sum, first_name=user_details[0], last_name=user_details[1], email=is_auth_user)

    else:
        utils.AssertUser(False, "Invalid method")


def send_purchase_email(cart_items, shipping_details, user_email, cur):

    cart_html = "<table><tr><th>Product</th><th>Quantity</th><th>Price</th><th>Total Product Price</th></tr>"
    total_price = 0

    for item in cart_items:
        product_id, product_name, quantity, price, currency = item
        price_total = float(price) * int(quantity)
        total_price += price_total
        cart_html += f"<tr><th>{product_name}</th><th class=\"text-right\">{quantity}</th><th class=\"text-right\">{price} {currency}</th><th  class=\"text-right\">{price_total} {currency}</th></tr>"
    
    _total_price = round(total_price, 2)
    cart_html += f"<tr><td colspan='3'>Total Order Price</td><td>{_total_price} {currency}</td></tr></table>"

    shipping_id, order_id, email, first_name, last_name, town, address, phone, country_code = shipping_details[0]
    shipping_html = f"""
    <table>
        <tr><th>Recipient</th><td>{first_name} {last_name}</td></tr>
        <tr><th>Email</th><td>{email}</td></tr>
        <tr><th>Address</th><td>{address}, {town}</td></tr>
        <tr><th>Country code</th><td>{country_code}</td></tr>
        <tr><th>Phone</th><td>{phone}</td></tr>
    </table>
    """

    cur.execute("SELECT subject, sender, body FROM email_template WHERE name = 'Purchase Email'")
    values = cur.fetchone()

    cur.execute("SELECT first_name, last_name FROM users WHERE email = %s", (user_email,))
    first_name, last_name = cur.fetchone()

    utils.trace(values)

    if values:
        subject, sender, body = values

        body_filled = body.format(
            first_name=first_name,
            last_name=last_name,
            cart=cart_html,
            shipping_details=shipping_html,
        )

        with app.app_context():
            msg = Message(subject,
                    sender = sender,
                    recipients = [user_email])
        msg.html = body_filled
        mail.send(msg)
    else:
        utils.AssertDev(False, "No information in the database")

def remove_from_cart_meth(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login')

    item_id = request.form['item_id']
    response = remove_from_cart(conn, cur, item_id)
    session['cart_message'] = response
    return redirect('/cart')

def finish_payment(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login')
    
    if request.method == 'GET':
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        order_id = session.get('order_id')

        cur.execute("SELECT oi.product_id, p.name, oi.quantity, oi.price, currencies.symbol FROM order_items AS oi JOIN products AS p ON oi.product_id=p.id JOIN currencies ON p.currency_id=currencies.id WHERE order_id = %s", (order_id,))
        order_products = cur.fetchall()

        print(order_products, flush=True)

        total_summ = sum(int(product[2]) * Decimal(product[3]) for product in order_products)
        total_sum = round(total_summ, 2)

        cur.execute("SELECT * FROM shipping_details WHERE order_id = %s", (order_id,))
        shipping_details = cur.fetchone()

        session['order_id'] = order_id

        return render_template('payment.html', order_products=order_products, shipping_details=shipping_details, total_sum=total_sum)

    elif request.method == 'POST':

        order_id = request.form.get('order_id')

        if order_id == "":
            order_id = session.get('order_id')

        utils.AssertUser(isinstance(float(request.form.get('payment_amount')), float), "You must enter a number")

        payment_amountt = float(request.form.get('payment_amount'))
        payment_amount = round(Decimal(payment_amountt), 2)

        cur.execute("SELECT quantity, price FROM order_items WHERE order_id = %s", (order_id,))
        all_products_from_the_order = cur.fetchall()

        total = 0
        for product in all_products_from_the_order:
            total += int(product[0]) * Decimal(product[1])
        
        cur.execute("SELECT status FROM orders WHERE order_id= %s", (order_id,))
        order_status = cur.fetchone()[0]

        utils.AssertUser(order_status == 'Ready for Paying', "This order is not ready for payment or has already been paid")

        if payment_amount < total:
            session['order_id'] = order_id
            session['payment_error'] = "You entered amout, which is less than the order you have"
            return redirect('/finish_payment')
        if payment_amount > total:
            session['order_id'] = order_id
            session['payment_error'] = "You entered amout, which is bigger than the order you have"
            return redirect('/finish_payment')

        # formatted_datetime = datetime.now().strftime('%Y-%m-%d')
        cur.execute("UPDATE orders SET status = 'Paid' WHERE order_id = %s", (order_id,))

        cur.execute("SELECT * FROM shipping_details WHERE order_id = %s", (order_id,))
        shipping_details = cur.fetchone()

        cur.execute("SELECT products.name, oi.quantity, oi.price FROM order_items AS oi JOIN products ON oi.product_id=products.id WHERE order_id = %s", (order_id,))
        products_from_order = cur.fetchall()

        send_compleated_payment_email(products_from_order, shipping_details, total, payment_amount, is_auth_user, cur)

        session['home_message'] = "You paid the order successful"

        return redirect('/home')

    else:
        utils.AssertUser(False, "Invalid method")

def send_compleated_payment_email(products, shipping_details, total_sum, provided_sum, user_email, cur):

    products_html = "<table><tr><th>Product</th><th>Quantity</th><th>Price</th><th>Total Product Price</th></tr>"
    total_price = 0

    for item in products:
        product_name, quantity, price = item
        price_total = float(price) * int(quantity)
        total_price += price_total
        products_html += f"<tr><th>{product_name}</th><th class=\"text-right\">{quantity}</th><th class=\"text-right\">{price}</th><th  class=\"text-right\">{price_total}</th></tr>"
    
    _total_price = round(total_price, 2)
    products_html += f"<tr><td colspan='3'>Total Order Price:</td><td>{_total_price}</td></tr></table>"
    products_html += f"<tr><td colspan='3'>You payed:</td><td>{provided_sum}</td></tr></table>"

    utils.trace(shipping_details)
    shipping_id, order_id, email, first_name, last_name, town, address, phone, country_code_id = shipping_details
    shipping_html = f"""
    <table>
        <tr><th>Recipient</th><td>{first_name} {last_name}</td></tr>
        <tr><th>Email</th><td>{email}</td></tr>
        <tr><th>Address</th><td>{address}, {town}</td></tr>
        <tr><th>Phone</th><td>{phone}</td></tr>
    </table>
    """

    cur.execute("SELECT subject, sender, body FROM email_template WHERE name = 'Payment Email'")
    values = cur.fetchone()

    cur.execute("SELECT first_name, last_name FROM users WHERE email = %s", (user_email,))
    first_name, last_name = cur.fetchone()

    utils.trace(values)

    if values:
        subject, sender, body = values

        body_filled = body.format(
            first_name=first_name,
            last_name=last_name,
            products=products_html,
            shipping_details=shipping_html,
        )

        with app.app_context():
            msg = Message(subject,
                    sender = sender,
                    recipients = [user_email])
        msg.html = body_filled
        mail.send(msg)
    else:
        utils.AssertDev(False, "No information in the database")

def staff_login(conn, cur):

    if request.method == 'GET':
        return render_template('staff_login.html')

    elif request.method == 'POST':

        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        
        username = request.form['username']
        password = request.form['password']

        cur.execute("SELECT username, password FROM staff WHERE username = %s AND password = %s", (username, password))
        utils.AssertUser(cur.fetchone(), "There is no registration with this staff username and password")

        session['staff_username'] = username

        session_id = sessions.create_session(os, datetime, timedelta, username, cur, conn)
        response = make_response(redirect('/staff_portal'))
        response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')

        return response
    else:
        utils.AssertUser(False, "Invalid method")

def staff_portal(conn, cur):
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
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

    cur.execute("SELECT price FROM products WHERE id = %s", (item_id,))
    price = cur.fetchone()[0]
    new_total = price * quantity_

    cur.execute("UPDATE cart_itmes SET quantity = %s WHERE product_id = %s", (quantity_, item_id))

    return jsonify(success=True, new_total=new_total)

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
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/login')

    if request.method == 'GET':

        fields = utils.check_request_arg_fields(cur, request, datetime)

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
                c.symbol
            FROM orders      AS o 
            JOIN users       AS u  on o.user_id     = u.id 
            JOIN order_items AS oi on o.order_id    = oi.order_id 
            JOIN products    AS p  on oi.product_id = p.id 
            JOIN currencies  AS c  on p.currency_id = c.id 
            WHERE u.email = %s 
            """

        params.append(is_auth_user)

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
            query += "GROUP BY o.order_id, o.status, o_date, oi.product_id, oi.price, oi.quantity, p.name, c.symbol HAVING sum(oi.quantity * oi.price) >= %s AND sum(oi.quantity * oi.price) <= %s"
            params.extend([price_min, price_max])

        if price_min == '' and price_max == '':
            # o.order_id
            query += " GROUP BY o.order_id, o.status, o_date, oi.product_id, oi.price, oi.quantity, p.name, c.symbol"

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

        cur.execute("SELECT first_name, last_name FROM users WHERE email = %s", (is_auth_user,))
        user_details = cur.fetchone()

        return render_template('user_orders.html', orders = orders, statuses = statuses, price_min=price_min, price_max=price_max, date_from=date_from, date_to=date_to, order_by_id=order_by_id, first_name=user_details[0], last_name=user_details[1], email=is_auth_user)
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
    is_auth_user =  sessions.get_current_user(request, cur)

    if is_auth_user == None:
       return redirect('/staff_login')

    # username = is_auth_user
    # username_from_url = request.path.split('/')[1]
    # back_office = request.path.split('/')[2]

    # if username != username_from_url:
    #     requestt = request.path.split("/")
    #     requestt.pop(0)
    #     requestt.pop(0)
    #     path = '/'.join(requestt)

    #     return redirect(url_for('handle_request', username=username, path=path))

    print("back_office_manager request.path", flush=True)
    print(request.path, flush=True)

    print("len(request.path.split('/')", flush=True)
    print(len(request.path.split('/')), flush=True)

    if request.path == f'/active_users':

        valid_sort_columns = {'id', 'last_active'}
        valid_sort_orders = {'asc', 'desc'}

        sort_by = request.args.get('sort', 'desc')
        sort_order = request.args.get('order', 'desc')
        name = request.args.get('name', '')
        email = request.args.get('email', '')
        user_id = request.args.get('user_by_id','')

        if sort_by not in valid_sort_columns or sort_order not in valid_sort_orders:
            sort_by = 'id'
            sort_order = 'desc'

        users = get_active_users(sort_by, sort_order, name, email, user_id)

        return render_template('active_users.html', users=users, name=name, email=email, user_id=user_id)

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
        print("Entered /crud_products/upload_products cucessfully", flush=True)

        file = request.files['productFile']

        print("file", flush=True)
        print(file, flush=True)

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
            session['crud_error'] = "Invalid file or file type extension."

        return redirect(f'/crud_products')

    elif request.path == f'/error_logs':     
        utils.AssertUser(utils.has_permission(cur, request, 'Logs', 'read', is_auth_user), "You don't have permission to this resource")

        sort_by = request.args.get('sort','time')
        sort_order = request.args.get('order','asc')

        valid_sort_columns = {'time'}
        valid_sort_orders = {'asc', 'desc'}

        if sort_by not in valid_sort_columns or sort_order not in valid_sort_orders:
            sort_by = 'time'
            sort_order = 'asc'

        query = "SELECT * FROM exception_logs"

        if sort_by and sort_order:
            query += f" ORDER BY {sort_by} {sort_order}"

        cur.execute(query)
        log_exceptions = cur.fetchall()

        return render_template('logs.html', log_exceptions = log_exceptions, sort_by=sort_by, sort_order=sort_order)
    
    elif request.path == f'/update_captcha_settings':
        utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'read', is_auth_user), "You don't have permission to this resource")

        if request.method == 'GET':

            current_settings = utils.get_current_settings(cur)

            cur.execute("SELECT value FROM settings WHERE name = %s", ("report_limitation_rows",))
            limitation_rows = cur.fetchone()[0]

            return render_template('captcha_settings.html', limitation_rows=limitation_rows, **current_settings)

        utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', is_auth_user), "You don't have permission to this resource")

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

    elif request.path == f'/update_report_limitation_rows':

        if request.method == 'POST':
            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', is_auth_user), "You don't have permission to this resource")

            limitation_rows = int(request.form['report_limitation_rows'])

            if limitation_rows <= 0 or limitation_rows >= 50000:
                utils.AssertUser(False, "You can't enter zero or negative number. The maximum number is 50000")


            query = ("UPDATE settings SET value = %s WHERE name = %s")
            cur.execute(query, (limitation_rows, 'report_limitation_rows'))

            session['staff_message'] = "You changed the limitation number of every report to: " + str(limitation_rows)

            return redirect(f'/staff_portal')

        else:
            utils.AssertUser(False, "Invalid method")        

    elif request.path == f'/report_sales':
        utils.AssertUser(utils.has_permission(cur, request, 'Report sales', 'read', is_auth_user), "You don't have permission to this resource")

        default_to_date = datetime.now()
        dafault_from_date = default_to_date - timedelta(days=90)

        default_to_date_str = default_to_date.strftime('%Y-%m-%d')
        default_from_date_str = dafault_from_date.strftime('%Y-%m-%d')

        if request.method == 'GET':

            return render_template('report.html', default_to_date=default_to_date_str, default_from_date=default_from_date_str)
        
        elif request.method == 'POST':

            cur.execute("SELECT value FROM settings WHERE name = %s", ("report_limitation_rows",))
            limitation_rows = cur.fetchone()[0]

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
                query += "users.id, orders.order_id, orders.order_date, users.first_name, "
            else:
                query += f"'-' AS id, '-' AS order_id, date_trunc('{group_by}', order_date) AS order_date, '-' AS first_name, "

            if status == '' and group_by == '':
                query += "orders.status, "
            elif status == '' and group_by != '':
                query += "'-' as status, "
            elif status != '' and group_by != '':
                query += "orders.status, "

            query += "sum(order_items.price * order_items.quantity) As total "

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

            utils.trace(query_for_total_rows)
            utils.trace(query)

            params.append(limitation_rows)

            cur.execute(query, params)

            report = cur.fetchall()

            utils.AssertUser(report[0][0] != None and report[0][1] != None and report[0][2] != None and report[0][3] != None, "No result with this filter")

            # total_records = len(report)

            total_price = sum(row[5] for row in report)

            report_json = utils.serialize_report(report)

            return render_template('report.html', limitation_rows=limitation_rows, filter_by_status=filter_by_status,report=report, total_records=total_records, total_price=total_price, report_json=report_json, default_to_date=date_to, default_from_date=date_from)
        else:
            utils.AssertUser(False, "Invalid url")

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

        keys = ['date_from', 'date_to', 'group_by', 'status', 'filter_by_status', 'total_records', 'total_price', 'report_data', 'format']

        form_data = {key: request.form.get(key, '') for key in keys}

        report_data = json.loads(form_data['report_data'])

        headers = ['Date', 'User ID', 'Order ID', 'Total Price', 'Buyer', 'Order Status']

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
                    name = row[4]
                    status = row[5]

                    row = [date, user_id, order_id, price, name, status]

                    cw.writerow(row)
                    si.seek(0)
                    yield si.getvalue()
                    si.truncate(0)
                    si.seek(0)

                
                cw.writerow(['Total Records:', form_data['total_records'], 'Total Price:', form_data['total_price']])
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
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'read', is_auth_user), "You don't have permission to this resource")

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
    
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'update', is_auth_user), "You don't have permission to this resource")

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
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'read', is_auth_user), "You don't have permission to this resource")

        sort_by = request.args.get('sort', 'id')
        sort_order = request.args.get('order', 'asc')
        price_min = request.args.get('price_min', None, type=float)
        price_max = request.args.get('price_max', None, type=float)

        valid_sort_columns = {'id', 'name', 'price', 'quantity', 'category'}
        valid_sort_orders = {'asc', 'desc'}

        if sort_by not in valid_sort_columns or sort_order not in valid_sort_orders:
            sort_by = 'id'
            sort_order = 'asc'
        
        base_query = sql.SQL("SELECT p.id, p.name, p.price, p.quantity, p.category, currencies.symbol FROM products AS p JOIN currencies ON p.currency_id = currencies.id")
        conditions = []
        query_params = []

        if price_min is not None and price_max is not None:
            conditions.append(sql.SQL("price BETWEEN %s AND %s"))
            query_params.extend([price_min, price_max])
        
        if conditions:
            base_query = base_query + sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)
        
        base_query = base_query + sql.SQL(" ORDER BY ") + sql.Identifier(sort_by) + sql.SQL(f" {sort_order}")
        
        base_query = base_query + sql.SQL(" LIMIT 100")

        cur.execute(base_query.as_string(conn), query_params)
        products = cur.fetchall()

        return render_template('crud.html', products=products, sort_by=sort_by, sort_order=sort_order, price_min=price_min or '', price_max=price_max or '')

    elif request.path == f'/crud_products/add_product' and len(request.path.split('/')) == 3:

        print("Enterd crud_products add successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'create', is_auth_user), "You don't have permission to this resource")

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
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'update', is_auth_user), "You don't have permission to this resource")

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
        
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'delete', is_auth_user), "You don't have permission to this resource")

        product_id = request.path.split('/')[3]
        cur.execute("UPDATE products SET quantity = 0 WHERE id = %s", (product_id,))

        session['crud_message'] = "Product was set to be unavailable successful with id = " + str(product_id)

        return redirect(f'/crud_products')

    elif request.path == f'/crud_staff' and len(request.path.split('/')) == 2:

        print("Enterd crud_staff read successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'read', is_auth_user), "You don't have permission to this resource")

        cur.execute("SELECT s.username, r.role_name, sr.staff_id, sr.role_id FROM staff_roles sr JOIN staff s ON s.id = sr.staff_id JOIN roles r ON r.role_id = sr.role_id")
        relations = cur.fetchall()

        return render_template('staff_role_assignment.html', relations=relations)

    elif request.path == f'/crud_staff/add_role_staff' and len(request.path.split('/')) == 3:

        print("Enterd crud_staff add successfully", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'create', is_auth_user), "You don't have permission to this resource")

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
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'create', is_auth_user), "You don't have permission to this resource")

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
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'delete', is_auth_user), "You don't have permission to this resource")

        staff_id = request.path.split('/')[3]
        role_id = request.path.split('/')[4]
        cur.execute('DELETE FROM staff_roles WHERE staff_id = %s AND role_id = %s', (staff_id, role_id))

        session['staff_message'] = "You successful deleted a role"
        return redirect(f'/staff_portal')

    elif request.path == f'/crud_orders' and len(request.path.split('/')) == 2:

        print("Enterd crud_orders read successful", flush=True)

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'read', is_auth_user), "You don't have permission for this resource")

        validated_fields = utils.check_request_arg_fields(cur, request, datetime)

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
                u.first_name || ' ' || u.last_name as user_names, 
                array_agg(p.name) as product_names,
                to_char(sum(oi.quantity * oi.price),'FM999999990.00') as order_price, 
                o.status, 
                to_char(o.order_date, 'MM-DD-YYYY HH:MI:SS') AS formatted_order_date,
                c.symbol
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

        if status:
            query += " AND o.status = %s"
            params.append(status)

        if price_min and price_max:
            query += "GROUP BY o.order_id, user_names, c.symbol HAVING sum(oi.quantity * oi.price) >= %s AND sum(oi.quantity * oi.price) <= %s"
            params.extend([price_min, price_max])

        if price_min == '' and price_max == '':
            query += " GROUP BY o.order_id, user_names, c.symbol "

        query += f" ORDER BY o.order_{sort_by} {sort_order} "

        cur.execute("SELECT count(*) FROM orders")
        total_length_query = cur.fetchone()[0]

        query += "LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cur.execute(query, params)
        orders = cur.fetchall()

        loaded_orders = len(orders)

        print("total_length_query", flush=True)
        print(total_length_query, flush=True)

        print("total_length_query // per_page + 1", flush=True)
        print(total_length_query // per_page + 1, flush=True)

        return render_template('crud_orders.html', page=page,total_pages=total_length_query // per_page ,orders=orders, statuses=statuses, current_status=status, price_min=price_min, price_max=price_max, order_by_id=order_by_id, date_from=date_from, date_to=date_to, per_page=per_page, sort_by=sort_by, sort_order=sort_order)

    elif request.path == f'/crud_orders/add_order' and len(request.path.split('/')) == 3:

        print("Enterd crud_orders add successful", flush=True)
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'create', is_auth_user), "You don't have permission for this resource")

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
        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'update', is_auth_user), "You don't have permission for this resource")

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
                        c.symbol
                    FROM order_items AS oi 
                    JOIN products    AS p ON oi.product_id = p.id 
                    JOIN currencies  AS c ON p.currency_id = c.id
                    WHERE order_id = %s 
                    GROUP BY p.id, p.name, oi.quantity, oi.price, c.symbol
                """, (order_id,))

            products_from_order = cur.fetchall()

            all_products_sum = 0
            for product in products_from_order:
                all_products_sum += product[2] * product[3]

            return render_template('edit_order.html', order_id=order_id,statuses=statuses, order_date = formatted_date, products_from_order=products_from_order, all_products_sum=all_products_sum)

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

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'delete', is_auth_user), "You don't have permission to this resource")

        order_id = request.path.split('/')[3]

        cur.execute('DELETE FROM shipping_details WHERE order_id = %s', (order_id,))
        cur.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
        cur.execute('DELETE FROM orders WHERE order_id = %s', (order_id,))

        session['crud_message'] = "You successful deleted a  order with id: " + str(order_id)       

        return redirect(f'/crud_orders')

    elif request.path == f'/crud_users' and len(request.path.split('/')) == 2:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'read', is_auth_user), "You don't have permission for this resource")

        if request.method == 'GET':

            fields = utils.check_request_arg_fields(cur, request, datetime)

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

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'create', is_auth_user), "You don't have permission for this resource")

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

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'update', is_auth_user), "You don't have permission for this resource")

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

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'delete', is_auth_user), "You don't have permission to this resource")

        user_id = request.path.split('/')[3]

        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        # cur.execute("UPDATE users SET verification_status = False WHERE id = %s", (user_id,))

        session['crud_message'] = "You successfully deleted user with id: " + str(user_id)

        return redirect(f'/crud_users')

    elif request.path == f'/template_email':

        if request.method == 'GET':

            cur.execute("SELECT name, subject, body, sender FROM email_template WHERE name = 'Verification Email'")
            values = cur.fetchone()

            cur.execute("SELECT name, subject, body FROM email_template WHERE name = 'Purchase Email'")
            values_purchase = cur.fetchone()

            cur.execute("SELECT name, subject, body FROM email_template WHERE name = 'Payment Email'")
            values_payment = cur.fetchone()

            if values and values_purchase and values_payment:
                name, subject, body, sender = values
                name_purchase, subject_purchase, body_purchase = values_purchase
                name_payment, subject_payment, body_payment = values_payment

                return render_template('template_email.html', name=name, subject=subject, body=body, sender=sender, tepmplate_name_purchase=name_purchase, tepmplate_subject_purchase=subject_purchase, tepmplate_body_purchase=body_purchase, tepmplate_name_payment=name_payment, tepmplate_subject_payment=subject_payment, tepmplate_body_payment=body_payment)

        elif request.method == 'POST':
            
            data = process_form('Template email', 'edit')

            cur.execute("""
                UPDATE email_template 
                SET 
                    name = %s, 
                    subject = %s, 
                    body = %s, 
                    sender = %s 
                WHERE id = 1""", (data['values'][0], data['values'][1], data['values'][2], data['values'][3]))

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
                    body = %s 
                WHERE id = 4""", (data_purchase['values'][0],))
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
                    body = %s 
                WHERE id = 6""", (data_payment['values'][0],))
            session['staff_message'] = "You successfully updated template for sending payment email"

            return redirect(f'/staff_portal')

        else:
           utils.AssertUser(False, "Invalid method")  

    else:
        utils.AssertUser(False, "Invalid url")

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
    (r'/(crud_products_edit_picture|error_logs|update_captcha_settings|report_sales|crud_products|crud_staff|role_permissions|download_report|crud_orders|active_users|download_report_without_generating_rows_in_the_html|upload_products|crud_users|template_email|update_report_limitation_rows)(?:/[\w\d\-_/]*)?', back_office_manager),
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
    try:
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()

        print("request.path", flush=True)
        print(request.path, flush=True)

        #TODO Validaciq na cookie prez bazata + req.args
        is_auth_user = sessions.get_current_user(request, cur)

        print("is_auth_user", flush=True)
        print(is_auth_user, flush=True)

        funtion_to_call = None
        match = None
        flag_front_office = False
        # True for front office, false for back office
        flag_office = None

        if is_auth_user is not None:
            flag_office = sessions.get_session_cookie_type(request, cur)

        if is_auth_user == None or flag_office == True:

            utils.trace("Entered front office loop")
            funtion_to_call = map_function(url_to_function_map_front_office)

            if funtion_to_call is not None:
                flag_front_office = True


        if (is_auth_user == None and not flag_front_office) or flag_office == False or request.path == '/staff_login':

            utils.trace("Entered back office loop")
            funtion_to_call = map_function(url_to_function_map_back_office)

        if flag_front_office == True and is_auth_user != None:
            cur.execute("SELECT last_active FROM users WHERE email = %s", (is_auth_user,))
            current_user_last_active = cur.fetchone()[0]
            cur.execute("UPDATE users SET last_active = now() WHERE email = %s", (is_auth_user,))

        # TODO: for next code rev
        utils.AssertUser(funtion_to_call is not None, "Invalid URL")
        utils.AssertDev(callable(funtion_to_call), "You are trying to invoke something that is not a function")

        if match:
            return funtion_to_call(conn, cur, *match.groups())
        else:
            return funtion_to_call(conn, cur)

    except Exception as message:

        user_email = sessions.get_current_user(request, cur)
        traceback_details = traceback.format_exc()

        log_exception(message.__class__.__name__, str(message), user_email)

        print(f"Day: {datetime.now()} = ERROR by = {user_email} - {traceback_details} = error class name = {message.__class__.__name__} - Dev message: {message}", flush=True)

        # != 'WrongUSerInputException'
        if message.__class__.__name__ != 'WrongUserInputException':
            message = 'Internal error'
            print(f"User message: {message}", flush=True)

        # TODO: Change url for QA
        if request.url == 'http://127.0.0.1:5000/staff_login':
            session['staff_login'] = "Yes"

        utils.add_form_data_in_session(session.get('form_data'))

        conn.rollback()

        return render_template("error.html", message = str(message), redirect_url = request.url)
    finally:
        #TODO: Da premestq predi if match:
        conn.commit()

        if conn is not None:
            conn.close()
        if cur is not None:
            cur.close()

if __name__ == '__main__':
    app.run(debug=True)
    # flask run --host=0.0.0.0 --port=5000