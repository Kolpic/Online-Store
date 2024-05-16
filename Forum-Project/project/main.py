from flask import Flask, request, render_template, redirect, url_for, session, abort, Response, jsonify, flash
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
# import os
from project import config, exception
from flask_session_captcha import FlaskSessionCaptcha
# from flask_sessionstore import Session
from flask_session import Session
from project import utils
# from project.error_handlers import not_found
# from project import exception
# import re
# import secrets
# import bcrypt

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

# End of database configuration migration

# Dev database
database = config.database
user = config.user
password = config.password
host = config.host

ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # Maximum file size in bytes (e.g., 10MB)
CURRENT_URL = ""

app.add_url_rule("/", defaults={'path':''}, endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])  
app.add_url_rule("/<path:path>", endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])
app.add_url_rule("/<role>/<path:path>", endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])  

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
    conn.commit()
    captcha_id = cur.fetchone()[0]
    session["captcha_id"] = captcha_id
    return jsonify({'first': first_captcha_number, 'second': second_captcha_number, 'captcha_id': captcha_id})

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
        conn.commit()
        captcha_id = cur.fetchone()[0]
     
        session["captcha_id"] = captcha_id
        return render_template('registration.html', form_data=form_data, captcha = {"first": first_captcha_number, "second": second_captcha_number})

    form_data = request.form.to_dict()
    session['form_data'] = form_data
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    password_ = request.form['password']
    confirm_password_ = request.form['confirm_password']
    captcha_ = int(request.form['captcha'])

    utils.AssertUser(password_ == confirm_password_, "Password and Confirm Password fields are different")

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
            conn.commit()
        else:
            cur.execute("INSERT INTO captcha_attempts (ip_address, attempts, last_attempt_time) VALUES (%s, 1, CURRENT_TIMESTAMP)", (user_ip,))
            conn.commit()
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

    cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", (first_name, last_name, email, hashed_password, verification_code))
    conn.commit()

    send_verification_email(email, verification_code)

    session['verification_message'] = 'Successful registration, we send you a verification code on the provided email'
    return redirect("/verify")

def send_verification_email(user_email, verification_code):
    with app.app_context():
        msg = Message('Email Verification',
                sender = 'galincho112@gmail.com',
                recipients = [user_email])
    msg.body = 'Please insert the verification code in the form: ' + verification_code
    mail.send(msg)

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
    conn.commit()

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

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))

    utils.AssertUser(not cur.rowcount == 0, "There is no registration with this email")

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
        
    is_the_email_verified = cur.fetchone()['verification_status']

    cur.execute("SELECT password FROM users WHERE email = %s", (email,))
        
    hashed_password = cur.fetchone()['password']

    are_passwords_same = bool(utils.verify_password(password_, hashed_password))

    utils.AssertUser(are_passwords_same, "Invalid email or password")
    utils.AssertUser(is_the_email_verified, "Your account is not verified or has been deleted")

    session['user_email'] = email   
    return redirect("/home")

def home(conn, cur, page = 1):
    if not utils.is_authenticated():
        return redirect('/login')

    cur.execute("SELECT DISTINCT(category) FROM products")
    categories = [row[0] for row in cur.fetchall()]  # Extract categories from tuples

    first_name, last_name, email__ = utils.getUserNamesAndEmail(conn, cur)

    prodcuts_user_wants = request.args.get('products_per_page', 50)
    if prodcuts_user_wants == '':
        prodcuts_user_wants = 50
    # utils.AssertUser(isinstance(prodcuts_user_wants, int), "You must enter a number in the \'Products per page\' form ")
    products_per_page = int(prodcuts_user_wants)
    offset = 0
    if page == None:
        page = 1
        offset = 50
    else:
        offset = (page - 1) * products_per_page

    global CURRENT_URL
    CURRENT_URL = request.url
    
    sort_by = request.args.get('sort','id')
    sort_order = request.args.get('order', 'asc')
    product_name = request.args.get('product_name', '')
    product_category = request.args.get('product_category', '')
    price_min = request.args.get('price_min', '')
    pric_max = request.args.get('price_max', '')

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

    if price_min.isdigit() and pric_max.isdigit():
        price_filter = " AND price BETWEEN %s AND %s"
        query_params.extend([price_min, pric_max])

    query = f"SELECT * FROM products WHERE TRUE{name_filter}{category_filter}{price_filter} ORDER BY {order_by_clause} LIMIT %s OFFSET %s"
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

    cur.execute("SELECT id FROM users WHERE email = %s", (session.get('user_email'),))
    user_id = cur.fetchone()[0]

    cart_count = get_cart_items_count(conn, cur, user_id)

    return render_template('home.html', first_name=first_name, last_name=last_name, email = email__,products=products, page=page, total_pages=total_pages, sort_by=sort_by, sort_order=sort_order, product_name=product_name, product_category=product_category, cart_count=cart_count, categories=categories)

def logout(conn, cur):
    session.pop('user_email', None) 
    return redirect('/home')

def profile(conn, cur):
    if 'user_email' not in session:
        return redirect('/login')
    
    cur.execute("SELECT first_name, last_name, email FROM users WHERE email = %s", (session['user_email'],))
    user_details = cur.fetchone()
    conn.commit()

    if user_details:
        return render_template('profile.html', user_details=user_details)
    
    return render_template('profile.html')

def update_profile(conn, cur):
    if 'user_email' not in session:
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
    email_in_session = session['user_email']
    fields_list.append(email_in_session)

    cur.execute(query_string, (fields_list))

    conn.commit()
    
    # Update session email if email was changed
    if email:
        session['user_email'] = email
    
    updated_fields_message = ', '.join(updated_fields)
    session['home_message'] = f"You successfully updated your {updated_fields_message}."
    return redirect('/home')

def delete_account(conn, cur):
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']

    cur.execute("DELETE FROM users WHERE email = %s", (user_email,))
    conn.commit()
    session.clear()
    session['login_message'] = 'You successful deleted your account'
    return redirect('/login')

# 
def recover_password(conn, cur):
    assertIsProvidedMethodsTrue('POST')

    email = request.form['recovery_email']
    new_password = os.urandom(10).hex()

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    is_email_valid = cur.fetchone()['email']

    hashed_password = utils.hash_password(new_password)

    cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))

    conn.commit()

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

    conn.commit()

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
    conn.commit()
    cur.execute("SELECT id FROM tokens WHERE login_token = %s", (login_token,))
    token_id = cur.fetchone()[0]
    cur.execute("UPDATE users SET token_id = %s WHERE email = %s", (token_id, email))

    conn.commit()

    login_link = f"http://10.20.3.101:5001/log?token={login_token}"
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
    conn.commit()
    cur.execute("DELETE FROM tokens WHERE id = %s", (token_data[0],))
    conn.commit()
    cur.execute("UPDATE users SET verification_status = true WHERE email = %s", (email,))
    conn.commit()

    session['user_email'] = email   
    return redirect('/home')

def update_captcha_settings(conn, cur):
    if 'staff_username' not in session:
        return redirect('/login_staff')

    if request.method == 'GET':
        current_settings = utils.get_current_settings(cur)
        return render_template('captcha_settings.html', **current_settings)

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
    
    conn.commit()
 
    if str_message != "":
        session['home_message'] = str_message
    return redirect('/home')

def view_logs(conn, cur):
    if 'staff_username' not in session:
        return redirect('/staff_login')
    
    utils.AssertUser(utils.has_permission(cur, request, 'Logs', 'read'), "You don't have permission to this resource")

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

def log_exception(conn, cur, exception_type, message ,email = None):

    cur.execute("INSERT INTO exception_logs (user_email, exception_type, message) VALUES (%s, %s, %s)", (email, exception_type, message))
    conn.commit()

def add_product(conn, cur):
    if 'staff_username' not in session:
        return redirect('/staff_login')

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
    conn.commit()
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
        conn.commit()
    
    cur.execute("SELECT id FROM cart_itmes WHERE cart_id = %s AND product_id = %s", (cart_id, product_id))
    item = cur.fetchone()
    if item:
        cur.execute("UPDATE cart_itmes SET quantity = quantity + %s WHERE id = %s", (quantity, item[0]))
    else:
        cur.execute("INSERT INTO cart_itmes (cart_id, product_id, quantity) VALUES (%s, %s, %s)", (cart_id, product_id, quantity))
    conn.commit()
    return "You successfully added item."

def view_cart(conn, cur, user_id):
    cur.execute("""
                SELECT p.name, p.price, ci.quantity, p.id FROM CARTS AS c 
                JOIN cart_itmes AS ci ON c.cart_id=ci.cart_id 
                JOIN products AS p ON ci.product_id=p.id 
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
    conn.commit()
    return "You successfully deleted item."

def add_to_cart_meth(conn, cur):
    if 'user_email' not in session:
        return redirect('/login')
    user_email = session.get('user_email')
    cur.execute("SELECT id FROM users WHERE email = %s", (user_email,))
    user_id = cur.fetchone()[0]
    product_id = request.form['product_id']
    quantity = request.form.get('quantity', 1)
    response = add_to_cart(conn, cur, user_id, product_id, quantity)
    session['home_message'] = response
    return redirect(CURRENT_URL)

def cart(conn, cur):
    if 'user_email' not in session:
        return redirect('/login')
    
    if request.method == 'GET':
        form_data = session.get('form_data_stack', []).pop() if 'form_data_stack' in session and len(session['form_data_stack']) > 0 else None
        if form_data:
            session.modified = True
        user_email = session.get('user_email')
        cur.execute("SELECT id FROM users WHERE email = %s", (user_email,))
        user_id = cur.fetchone()[0]
        items = view_cart(conn, cur, user_id)
        total_sum = sum(item[1] * item[2] for item in items)
        cur.execute("SELECT * FROM country_codes")
        country_codes = cur.fetchall()
        return render_template('cart.html', items=items, total_sum=total_sum, country_codes=country_codes, form_data=form_data)
   
    form_data = request.form.to_dict()
    session['form_data'] = form_data
    email = request.form['email'].strip()
    first_name = request.form['first_name'].strip()
    last_name = request.form['last_name'].strip()
    town = request.form['town'].strip()
    address = request.form['address'].strip()
    country_code = request.form['country_code']
    phone = request.form['phone'].strip()

    cur.execute("SELECT id FROM users WHERE email = %s", (session.get('user_email'),))
    user_id = cur.fetchone()[0]
    regexx = r'^\d{7,15}$'

    # Check fields
    utils.AssertUser(len(first_name) >= 3 and len(first_name) <= 50, "First name is must be between 3 and 50 symbols")
    utils.AssertUser(len(last_name) >= 3 and len(last_name) <= 50, "Last name must be between 3 and 50 symbols")
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    utils.AssertUser(re.fullmatch(regex, email), "Email is not valid")
    utils.AssertUser(re.fullmatch(regexx, phone), "Phone number format is not valid.")
    utils.AssertUser(phone[0] != "0", "Phone number format is not valid.")

    # Retrieve cart items for the user
    cur.execute("""
                SELECT c.cart_id FROM users AS u 
                JOIN carts AS c ON u.id = c.user_id
                WHERE u.id = %s
                """, (user_id,))
    cart_id = cur.fetchone()[0]

    cur.execute("""
                SELECT ci.product_id, p.name, ci.quantity, p.price FROM cart_itmes AS ci
                JOIN products AS p ON ci.product_id = p.id
                WHERE ci.cart_id = %s
                """, (cart_id,))
    cart_items = cur.fetchall()

    cur.execute("SELECT quantity FROM products WHERE id = %s", (cart_items[0][0],))
    quantity_db = cur.fetchone()[0]

    # Check and change quantity 
    for item in cart_items:
        product_id_, name, quantity, price = item
        if quantity > quantity_db:
            session['cart_error'] = "We don't have " + str(quantity) + " from product: " + str(name) + " in our store. You can purchase less or to remove the product from your cart"
            utils.add_form_data_in_session(session.get('form_data'))
            return redirect('/cart')
        cur.execute("UPDATE products SET quantity = quantity - %s WHERE id = %s", (quantity, product_id_))

    # current_prices = {item['poroduct_id']: item['price'] for item in cart_items}
    price_mismatch = False
    for item in cart_items:
        product_id, name, quantity, cart_price = item
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
    cur.execute("INSERT INTO orders (user_id, status, order_date) VALUES (%s, %s, %s) RETURNING order_id", (user_id, "Ready for Paying", formatted_datetime))
    order_id = cur.fetchone()[0]

    # Insert order items into order_items table
    for item in cart_items:
        cur.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)", (order_id, item[0], item[2], item[3]))

    cur.execute("SELECT id FROM country_codes WHERE code = %s", (country_code,))
    country_code_id = cur.fetchone()[0]
    cur.execute("INSERT INTO shipping_details (order_id, email, first_name, last_name, town, address, phone, country_code_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (order_id, email, first_name, last_name, town, address, phone, country_code_id))
    
    conn.commit()

    # Total sum to be passed to the payment.html
    items = view_cart(conn, cur, user_id)
    total_sum = sum(item[1] * item[2] for item in items)

    # When the purchase is made we empty the user cart 
    cur.execute("SELECT cart_id FROM carts WHERE user_id = %s", (user_id,))
    cart_id = cur.fetchone()[0]
    cur.execute("DELETE FROM cart_itmes WHERE cart_id = %s", (cart_id,))

    conn.commit()
    cur.execute("""
                SELECT shd.shipping_id, shd.order_id, shd.email, shd.first_name, shd.last_name, shd.town, shd.address, shd.phone, cc.code 
                FROM shipping_details AS shd 
                JOIN orders AS o ON shd.order_id=o.order_id 
                JOIN country_codes AS cc ON shd.country_code_id = cc.id 
                WHERE o.order_id = %s
                """, (order_id,))
    shipping_details = cur.fetchall()

    session['payment_message'] = "You successful made an order with id = " + str(order_id)
    return render_template('payment.html', order_id=order_id, order_products=cart_items, shipping_details=shipping_details, total_sum=total_sum)

def remove_from_cart_meth(conn, cur):
    if 'user_email' not in session:
        return redirect('/login')
    item_id = request.form['item_id']
    response = remove_from_cart(conn, cur, item_id)
    session['cart_message'] = response
    return redirect('/cart')

def finish_payment(conn, cur):
    if 'user_email' not in session:
        return redirect('/login')
    
    if request.method == 'GET':
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        order_id = session.get('order_id')
        # cur.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        # order = cur.fetchone()

        cur.execute("SELECT oi.product_id, p.name, oi.quantity, oi.price FROM order_items AS oi JOIN products AS p ON oi.product_id=p.id WHERE order_id = %s", (order_id,))
        order_products = cur.fetchall()

        # order_products = order['product_details']
        # list_products = [
        #     [
        #         product['product_id'],
        #         product['name'],
        #         int(product['quantity']),
        #         float(product['price']),
        #         float(product['price']) * int(product['quantity'])
        #     ]
        #     for product in order_products
        # ]

        total_summ = sum(int(product[2]) * Decimal(product[3]) for product in order_products)
        total_sum = round(total_summ, 2)

        cur.execute("SELECT * FROM shipping_details WHERE order_id = %s", (order_id,))
        shipping_details = cur.fetchone()
        session['order_id'] = order_id
        return render_template('payment.html', order_products=order_products, shipping_details=shipping_details, total_sum=total_sum)

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

    # cur.execute("SELECT SUM((product_detail->>'price')::numeric * (product_detail->>'quantity')::numeric) FROM orders, json_array_elements(product_details) AS product_detail WHERE order_id = %s", (order_id,))
    # total = cur.fetchone()[0]
    
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
    formatted_datetime = datetime.now().strftime('%Y-%m-%d')
    cur.execute("UPDATE orders SET status = 'Paid', order_date = %s WHERE order_id = %s", (formatted_datetime, order_id))
    conn.commit()
    session['home_message'] = "You paid the order successful"
    return redirect('/home')


def crud_inf(conn, cur):
    if 'staff_username' not in session:
        return redirect('/staff_login')
    
    sort_by = request.args.get('sort', 'id')
    sort_order = request.args.get('order', 'asc')
    price_min = request.args.get('price_min', None, type=float)
    price_max = request.args.get('price_max', None, type=float)

    valid_sort_columns = {'id', 'name', 'price', 'quantity', 'category'}
    valid_sort_orders = {'asc', 'desc'}

    if sort_by not in valid_sort_columns or sort_order not in valid_sort_orders:
        sort_by = 'id'
        sort_order = 'asc'
    
    base_query = sql.SQL("SELECT * FROM products")
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


def staff_login(conn, cur):
    if request.method == 'GET':
        return render_template('staff_login.html')
    
    username = request.form['username']
    password = request.form['password']

    cur.execute("SELECT username, password FROM staff WHERE username = %s AND password = %s", (username, password))
    utils.AssertUser(cur.fetchone(), "There is no registration with this staff username and password")

    session['staff_username'] = username
    return redirect('/staff_portal')

def staff_portal(conn, cur):
    if 'staff_username' not in session:
        return redirect('/staff_login')

    if request.method == 'GET':
        return render_template('staff_portal.html')
    
def logout_staff(conn, cur):
    session.pop('staff_username', None) 
    return redirect('/staff_login')

def edit_product(conn, cur, product_id):
    if 'staff_username' not in session:
        return redirect('/staff_login')
    
    if request.method == 'GET':
        cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product = cur.fetchone()
        utils.AssertUser(product, "Invalid product")
        return render_template('edit_product.html', product=product, product_id=product_id)
    
    name = request.form['name']
    price_ = request.form['price']
    quantity_ = request.form['quantity']
    category = request.form['category']

    utils.AssertUser(name and price_ and quantity_ and category, "All fields must be filled")

    price = float(price_)
    utils.AssertUser(price > 0, "Price must be possitive")
    quantity = int(quantity_)
    utils.AssertUser(quantity >= 0, "Quantity must be possitive")

    cur.execute("UPDATE products SET name = %s, price = %s, quantity = %s, category = %s WHERE id = %s", (name, price, quantity, category, product_id))
    conn.commit()
    session['crud_message'] = "Product was updated successfully with id = " + str(product_id)
    return redirect('/crud')

def delete_product(conn, cur, product_id):
    if 'staff_username' not in session:
        return redirect('/staff_login')
    
    cur.execute("UPDATE products SET quantity = 0 WHERE id = %s", (product_id,))
    conn.commit()
    session['crud_message'] = "Product was set to be unavailable successful with id = " + str(product_id)
    return redirect('/crud')

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
            conn.commit()
        return "Imprted"
        
def report(conn, cur):
    if 'staff_username' not in session:
        return redirect('/staff_login')
    
    if request.method == 'GET':
        return render_template('report.html')
    
    date_from = request.form.get('date_from')
    date_to = request.form.get('date_to')
    group_by = request.form.get('group_by')
    status = request.form.get('status')

    utils.AssertUser(date_from or date_to, "You have to select a date from, date to")

    if group_by:
        group_by_clause = f"DATE(date_trunc(%s, order_date))"
    else:
        group_by_clause = "o.order_id"

    status_filter = ""
    if status:
        status_filter = "AND o.status = %s"

    query = f"""
    WITH OrderSums AS (
        SELECT
            o.order_id,
            DATE(o.order_date) AS order_date,
            u.first_name || ' ' || u.last_name AS buyer_name,
            o.status,
            SUM(oi.quantity * oi.price) AS order_sum
        FROM
            orders o
        JOIN
            users u ON o.user_id = u.id
        JOIN
            order_items oi ON o.order_id = oi.order_id
        WHERE
            o.order_date BETWEEN %s AND %s
            {status_filter}
        GROUP BY
            o.order_id, o.order_date, buyer_name, o.status
    )
    SELECT
        {group_by_clause} AS period,
        array_agg(order_id) AS order_ids,
        array_agg(buyer_name) AS names_of_buyers,
        SUM(order_sum) AS total_sum,
        array_agg(status) AS order_statuses,
        status
    FROM
        OrderSums as o
    GROUP BY
        period, status
    ORDER BY
        period, status;
    """

    params = [date_from, date_to]
    if status:
        params.append(status)
    if group_by:
        params.append(group_by)

    cur.execute(query, tuple(params))
    report = cur.fetchall()
    return render_template('report.html', report=report)  
 
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
    conn.commit()

    return jsonify(success=True, new_total=new_total)

def staff_role(conn, cur):
    if 'staff_username' not in session:
        return redirect('/staff_login')
    
    if request.method == 'GET':
        cur.execute("SELECT s.username, r.role_name, sr.staff_id, sr.role_id FROM staff_roles sr JOIN staff s ON s.id = sr.staff_id JOIN roles r ON r.role_id = sr.role_id")
        relations = cur.fetchall()
        return render_template('staff_role_assignment.html', relations=relations)

def staff_role_add(conn, cur):
    if 'staff_username' not in session:
        return redirect('/staff_login')

    if request.method == 'GET':
        cur.execute("SELECT id, username FROM staff")
        staff = cur.fetchall()

        cur.execute("SELECT role_id, role_name FROM roles")
        roles = cur.fetchall()

        return render_template('add_staff_role.html', staff=staff, roles=roles) 

    staff_name = request.form['staff']
    staff_role = request.form['role']

    cur.execute("SELECT id FROM staff WHERE username = %s", (staff_name,))
    staff_id = cur.fetchone()[0]

    cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (staff_role,))
    role_id = cur.fetchone()[0]

    cur.execute('INSERT INTO staff_roles (staff_id, role_id) VALUES (%s, %s)', (staff_id, role_id))
    conn.commit()

    session['staff_message'] = "You successful gave a role: " + staff_role + "to user: " + staff_name
    return redirect('/staff_portal')

def delete_role(conn, cur, staff_id, role_id):
    cur.execute('DELETE FROM staff_roles WHERE staff_id = %s AND role_id = %s', (staff_id, role_id))
    conn.commit()

    session['staff_message'] = "You successful deleted a role"
    return redirect('/staff_role')

def role_permissions(conn, cur):
    if 'staff_username' not in session:
        return redirect('/staff_login')
    
    interfaces = ['Logs', 'CRUD Products', 'Captcha Settings', 'Report sales', 'Staff roles',]

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

        return render_template('role_permissions.html', roles=roles, interfaces=interfaces, role_permissions=role_permissions, selected_role=selected_role, role_to_display=role)
    
    role_id = request.form['role']
    cur.execute('DELETE FROM role_permissions WHERE role_id = %s', (role_id,))
    for interface in interfaces:
        for action in ['create', 'read', 'update', 'delete']:
            if f'{interface}_{action}' in request.form:
                cur.execute("SELECT permission_id FROM permissions WHERE permission_name = %s AND interface = %s", (action, interface))
                permission_id = cur.fetchone()[0]
                cur.execute('INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)', 
                            (role_id, permission_id))
    conn.commit()
    return redirect('/role_permissions?role=' + role_id)

def back_office_manager(conn, cur, *params):
    if 'staff_username' not in session:
        return redirect('/staff_login')

    current_role = request.path.split('/')[1]

    if request.path == f'/{current_role}/error_logs':     
        utils.AssertUser(utils.has_permission(cur, request, 'Logs', 'read'), "You don't have permission to this resource")

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
    
    if request.path == f'/{current_role}/update_captcha_settings':
        utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'read'), "You don't have permission to this resource")

        if request.method == 'GET':
            current_settings = utils.get_current_settings(cur)
            return render_template('captcha_settings.html', current_role=current_role, **current_settings)

        utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update'), "You don't have permission to this resource")
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
        
        conn.commit()
    
        if str_message != "":
            session['staff_message'] = str_message
        return redirect(f'/{current_role}/staff_portal')

    if request.path.split('/')[2] == 'report_sales':
        utils.AssertUser(utils.has_permission(cur, request, 'Report sales', 'read'), "You don't have permission to this resource")

        if request.method == 'GET':
            return render_template('report.html', current_role=current_role)
    
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        group_by = request.form.get('group_by')
        status = request.form.get('status')
        order_id = 0
        if len(request.path.split('/')) > 3:
            order_id = request.path.split('/')[3]
            utils.AssertUser(isinstance(int(order_id), int), 'You must enter a number')

        if order_id != 0:
            cur.execute("""
                SELECT
                    o.order_date,
                    array_agg(o.order_id),
                    array_agg(u.first_name || ' ' || u.last_name) AS buyer_name,
                    oi.quantity * oi.price AS item_total,
                    array_agg(o.status)
                FROM
                    orders o
                JOIN
                    users u ON o.user_id = u.id
                JOIN
                    order_items oi ON o.order_id = oi.order_id
                WHERE
                    o.order_id = %s
                GROUP BY
                    o.order_date, o.order_id, u.first_name, u.last_name, oi.quantity, oi.price, o.status
                ORDER BY
                    o.order_date, o.status;
                        """, (order_id,))
            report = cur.fetchall()
            return render_template('report.html', report=report, current_role=current_role)
        
        utils.AssertUser(date_from or date_to, "You have to select a date from, date to")

        if group_by:
            group_by_clause = f"DATE(date_trunc(%s, order_date))"
        else:
            group_by_clause = "o.order_id"

        status_filter = ""
        if status:
            status_filter = "AND o.status = %s"

        query = f"""
        WITH OrderSums AS (
            SELECT
                o.order_id,
                DATE(o.order_date) AS order_date,
                u.first_name || ' ' || u.last_name AS buyer_name,
                o.status,
                SUM(oi.quantity * oi.price) AS order_sum
            FROM
                orders o
            JOIN
                users u ON o.user_id = u.id
            JOIN
                order_items oi ON o.order_id = oi.order_id
            WHERE
                o.order_date BETWEEN %s AND %s
                {status_filter}
            GROUP BY
                o.order_id, o.order_date, buyer_name, o.status
        )
        SELECT
            {group_by_clause} AS period,
            array_agg(order_id) AS order_ids,
            array_agg(buyer_name) AS names_of_buyers,
            SUM(order_sum) AS total_sum,
            array_agg(status) AS order_statuses,
            status
        FROM
            OrderSums as o
        GROUP BY
            period, status
        ORDER BY
            period, status;
        """

        params = [date_from, date_to]
        if status:
            params.append(status)
        if group_by:
            params.append(group_by)

        cur.execute(query, tuple(params))
        report = cur.fetchall()
        total_records = len(report)
        total_price = sum(row[3] for row in report)
        report_json = utils.serialize_report(report)
        return render_template('report.html', report=report, current_role=current_role, total_records=total_records, total_price=total_price, report_json=report_json)

    if request.path == f'/{current_role}/download_report':
        date_from = request.form['date_from']
        date_to = request.form['date_to']
        group_by = request.form['group_by']
        status = request.form['status']
        total_records = request.form['total_records']
        total_price = request.form['total_price']
        report_data = request.form['report_data']

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Date', 'Order ID\'s', 'Name of Buyers', 'Total Price', 'Order Status'])
        for row in json.loads(report_data):
            cw.writerow(row)
        cw.writerow(['Total Records: ', total_records, 'Total: ', total_price])

        cw.writerow(['Filters'])
        cw.writerow(['Date From:', date_from])
        cw.writerow(['Date To:', date_to])
        cw.writerow(['Group By:', group_by])
        cw.writerow(['Status:', status])

        output = si.getvalue()
        si.close()

        response = Response(output, mimetype= 'text/csv')
        response.headers['Content-Disposition'] = 'attachment; filename=report.csv'
        return response

    if request.path == f'/{current_role}/role_permissions':
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'read'), "You don't have permission to this resource")
        interfaces = ['Logs', 'CRUD Products', 'Captcha Settings', 'Report sales', 'Staff roles',]

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

            return render_template('role_permissions.html', roles=roles, interfaces=interfaces, role_permissions=role_permissions, selected_role=selected_role, role_to_display=role)
    
        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'update'), "You don't have permission to this resource")
        role_id = request.form['role']
        cur.execute('DELETE FROM role_permissions WHERE role_id = %s', (role_id,))
        for interface in interfaces:
            for action in ['create', 'read', 'update', 'delete']:
                if f'{interface}_{action}' in request.form:
                    cur.execute("SELECT permission_id FROM permissions WHERE permission_name = %s AND interface = %s", (action, interface))
                    permission_id = cur.fetchone()[0]
                    cur.execute('INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)', 
                                (role_id, permission_id))
        conn.commit()
        session['role_permission_message'] = 'You successfull updated permissions for role with id: ' + str(role_id)
        return redirect(f'/{current_role}/role_permissions?role=' + role_id)

    if request.path.split('_')[0] == f'/{current_role}/crud':
        if request.path.split('_')[1] == 'products' or request.path.split('_')[1] == 'staff':
            if request.path.split('_')[1] == 'products':
                utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'read'), "You don't have permission to this resource")

                sort_by = request.args.get('sort', 'id')
                sort_order = request.args.get('order', 'asc')
                price_min = request.args.get('price_min', None, type=float)
                price_max = request.args.get('price_max', None, type=float)

                valid_sort_columns = {'id', 'name', 'price', 'quantity', 'category'}
                valid_sort_orders = {'asc', 'desc'}

                if sort_by not in valid_sort_columns or sort_order not in valid_sort_orders:
                    sort_by = 'id'
                    sort_order = 'asc'
                
                base_query = sql.SQL("SELECT * FROM products")
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
            
            if request.path.split('_')[1] == 'staff':
                utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'read'), "You don't have permission to this resource")

                cur.execute("SELECT s.username, r.role_name, sr.staff_id, sr.role_id FROM staff_roles sr JOIN staff s ON s.id = sr.staff_id JOIN roles r ON r.role_id = sr.role_id")
                relations = cur.fetchall()
                return render_template('staff_role_assignment.html', relations=relations, current_role=current_role)
        
        if request.path.split('/')[3] == 'add_product' or request.path.split('/')[3] == 'add_role_staff':

            if request.path.split('/')[3] == 'add_product':
                utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'create'), "You don't have permission to this resource")
                # TODO: ref
                if request.method == 'GET':
                    cur.execute("SELECT DISTINCT(category) FROM products")
                    categories = [row[0] for row in cur.fetchall()]  # Extract categories from tuples
                    return render_template('add_product_staff.html', categories=categories, current_role=current_role)

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
                conn.commit()
                session['crud_message'] = "Item was added successful"
                return redirect(f'/{current_role}/crud_products')
            
            if request.path.split('/')[3] == 'add_role_staff':
                utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'create'), "You don't have permission to this resource")
                 # TODO: ref
                if request.method == 'GET':
                    cur.execute("SELECT id, username FROM staff")
                    staff = cur.fetchall()

                    cur.execute("SELECT role_id, role_name FROM roles")
                    roles = cur.fetchall()

                    return render_template('add_staff_role.html', staff=staff, roles=roles, current_role=current_role) 

                staff_name = request.form['staff']
                staff_role = request.form['role']

                cur.execute("SELECT id FROM staff WHERE username = %s", (staff_name,))
                staff_id = cur.fetchone()[0]

                cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (staff_role,))
                role_id = cur.fetchone()[0]

                cur.execute('INSERT INTO staff_roles (staff_id, role_id) VALUES (%s, %s)', (staff_id, role_id))
                conn.commit()

                session['staff_message'] = "You successful gave a role: " + staff_role + "to user: " + staff_name
                return redirect('/staff_portal')

        if request.path.split('/')[3] == 'edit_product':
            utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'update'), "You don't have permission to this resource")
            # TODO: ref
            product_id = request.path.split('/')[4]
            if request.method == 'GET':
                cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
                product = cur.fetchone()
                utils.AssertUser(product, "Invalid product")
                return render_template('edit_product.html', product=product, product_id=product_id, current_role=current_role)
    
            name = request.form['name']
            price_ = request.form['price']
            quantity_ = request.form['quantity']
            category = request.form['category']

            utils.AssertUser(name and price_ and quantity_ and category, "All fields must be filled")

            price = float(price_)
            utils.AssertUser(price > 0, "Price must be possitive")
            quantity = int(quantity_)
            utils.AssertUser(quantity >= 0, "Quantity must be possitive")

            cur.execute("UPDATE products SET name = %s, price = %s, quantity = %s, category = %s WHERE id = %s", (name, price, quantity, category, product_id))
            conn.commit()
            session['crud_message'] = "Product was updated successfully with id = " + str(product_id)
            return redirect(f'/{current_role}/crud_products')
        
        if request.path.split('/')[3] == 'delete_product' or request.path.split('/')[3] == 'delete_role':
            if request.path.split('/')[3] == 'delete_product':
                # TODO: ref
                utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'delete'), "You don't have permission to this resource")

                product_id = request.path.split('/')[4]
                cur.execute("UPDATE products SET quantity = 0 WHERE id = %s", (product_id,))
                conn.commit()
                session['crud_message'] = "Product was set to be unavailable successful with id = " + str(product_id)
                return redirect(f'/{current_role}/crud_products')
            
            if request.path.split('/')[3] == 'delete_role':
                utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'delete'), "You don't have permission to this resource")

                staff_id = request.path.split('/')[4]
                role_id = request.path.split('/')[5]
                cur.execute('DELETE FROM staff_roles WHERE staff_id = %s AND role_id = %s', (staff_id, role_id))
                conn.commit()

                session['staff_message'] = "You successful deleted a role"
                return redirect(f'/{current_role}/staff_portal')
                        

@app.route('/favicon.ico')
def favicon():#
    return app.send_static_file('favicon.ico')

url_to_function_map = [
    (r'(?:/[A-z]+)?/registration', registration),
    (r'(?:/[A-z]+)?/refresh_captcha', refresh_captcha),
    (r'(?:/[A-z]+)?/verify', verify),
    (r'(?:/[A-z]+)?/login', login),
    (r'(?:/[A-z]+)?/home(?:/(\d+))?', home),
    (r'(?:/[A-z]+)?/logout', logout),
    (r'(?:/[A-z]+)?/profile', profile),
    (r'(?:/[A-z]+)?/update_profile', update_profile),
    (r'(?:/[A-z]+)?/delete_account', delete_account),
    (r'(?:/[A-z]+)?/recover_password', recover_password),
    (r'(?:/[A-z]+)?/resend_verf_code', resend_verf_code),
    (r'(?:/[A-z]+)?/send_login_link', send_login_link),
    (r'(?:/[A-z]+)?/log', login_with_token),
    (r'(?:/[A-z]+)?/image/(\d+)', serve_image),
    (r'(?:/[A-z]+)?/add_to_cart', add_to_cart_meth),
    (r'(?:/[A-z]+)?/cart', cart),
    (r'(?:/[A-z]+)?/update_cart_quantity', update_cart_quantity),
    (r'(?:/[A-z]+)?/remove_from_cart', remove_from_cart_meth),
    (r'(?:/[A-z]+)?/finish_payment', finish_payment),
    (r'(?:/[A-z]+)?/staff_login', staff_login),
    (r'(?:/[A-z]+)?/staff_portal', staff_portal),
    (r'(?:/[A-z]+)?/logout_staff', logout_staff),
    (r'(/[A-z]+)/logout_staff', logout_staff),
    (r'(?:/[A-z]+)?/(error_logs|update_captcha_settings|report_sales|crud_products|crud_staff|role_permissions|download_report)(?:/[\w\d\-_/]*)?', back_office_manager),

    # # (r'(?:/[A-z]+)?/error_logs', view_logs),
    # (r'(?:/[A-z]+)?/error_logs', back_office_manager),
    # # (r'(?:/[A-z]+)?/update_captcha_settings', update_captcha_settings),
    # (r'(?:/[A-z]+)?/update_captcha_settings', back_office_manager),
    # # (r'(?:/[A-z]+)?/crud', crud_inf),
    # (r'(?:/[A-z]+)?/crud_products', back_office_manager),
    # # (r'(?:/[A-z]+)?/add_product', add_product),
    # (r'(?:/[A-z]+)?/crud_products/add_product', back_office_manager),
    # # (r'(?:/[A-z]+)?/edit_product/(\d+)', edit_product),
    # (r'(?:/[A-z]+)?/crud_products/edit_product/(\d+)', back_office_manager),
    # # (r'(?:/[A-z]+)?/delete_product/(\d+)', delete_product),
    # (r'(?:/[A-z]+)?/crud_products/delete_product/(\d+)', back_office_manager),
    # (r'(?:/[A-z]+)?/add_products_from_file/(.+)', add_products_from_file),
    # # (r'(?:/[A-z]+)?/reports', report),
    # (r'(?:/[A-z]+)?/report_sales', back_office_manager),
    # # (r'(?:/[A-z]+)?/staff_role', staff_role),
    # # (r'(?:/[A-z]+)?/staff_role_add', staff_role_add),
    # # (r'(?:/[A-z]+)?/delete_role/(\d+)/(\d+)', delete_role),
    # (r'(?:/[A-z]+)?/crud_staff', back_office_manager),
    # # (r'(?:/[A-z]+)?/crud_staff/add_staff', back_office_manager),
    # (r'(?:/[A-z]+)?/crud_staff/add_role_staff', back_office_manager),
    # (r'(?:/[A-z]+)?/crud_staff/delete_role/(\d+)/(\d+)', back_office_manager),
    # # (r'(?:/[A-z]+)?/role_permissions(?:\?role=\d+)?', role_permissions),
    # (r'(?:/[A-z]+)?/role_permissions(?:\?role=\d+)?', back_office_manager),
]


@app.endpoint("handle_request")
def handle_request(role=None, path=''):
    conn = None
    cur = None
    roles = None
    try:
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()
        staff_username = user_email = session.get('staff_username')

        if staff_username is not None:
            cur.execute("SELECT role_name FROM roles AS r JOIN staff_roles AS sr ON r.role_id=sr.role_id JOIN staff AS s ON sr.staff_id = s.id WHERE s.username = %s", (staff_username,))
            roles = cur.fetchone()[0]
        
        if roles:
            if role is None:
                # Redirect to the URL with the role included
                return redirect(url_for('handle_request', role=roles, path=path))

        funtion_to_call = None
        match = None

        for pattern, function in url_to_function_map:
            match = re.match(pattern, request.path)
            if match:
                funtion_to_call = function
                break

        utils.AssertUser(funtion_to_call is not None, "Invalid URL")
        utils.AssertDev(callable(funtion_to_call), "You are trying to invoke something that is not a function")

        if match:
            return funtion_to_call(conn, cur, *match.groups())
        else:
            return funtion_to_call(conn, cur)
    except Exception as message:
        user_email = session.get('user_email', 'Guest')
        log_exception(conn, cur, message.__class__.__name__, str(message), user_email)

        # != 'WrongUSerInputException'
        if message.__class__.__name__ == 'DevException':
            message = 'Internal error'

        # TODO: Change url for QA
        if request.url == 'http://127.0.0.1:5000/staff_login':
            session['staff_login'] = "Yes"

        utils.add_form_data_in_session(session.get('form_data'))
        return render_template("error.html", message = str(message), redirect_url = request.url)
    finally:
        if conn is not None:
            conn.close()
        if cur is not None:
            cur.close()

if __name__ == '__main__':
    app.run(debug=True)
    # flask run --host=0.0.0.0 --port=5000