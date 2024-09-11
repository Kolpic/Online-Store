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

app.add_url_rule("/", defaults={'path':''}, endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])  
app.add_url_rule("/<path:path>", endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])
app.add_url_rule("/<username>/<path:path>", endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])

def refresh_captcha_handler(conn, cur, authenticated_user):
    first_captcha_number = random.randint(0, 100)
    second_captcha_number = random.randint(0, 100)

    cur.execute("INSERT INTO captcha(first_number, second_number, result) VALUES (%s, %s, %s) RETURNING id", 
                (first_captcha_number, second_captcha_number, first_captcha_number + second_captcha_number))

    captcha_id = cur.fetchone()[0]
    session["captcha_id"] = captcha_id

    return jsonify({'first': first_captcha_number, 'second': second_captcha_number, 'captcha_id': captcha_id})
    
def registration_handler(conn, cur, authenticated_user):
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

        prepared_data = front_office.prepare_registration_data(
            cur=cur, 
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

        front_office.registration(
            cur=cur, 
            first_name=first_name, 
            last_name=last_name, 
            email=email, 
            password_=password_,
            confirm_password_=confirm_password_, 
            phone=phone, 
            gender=gender, 
            captcha_id=captcha_id, 
            captcha_=captcha_,
            user_ip=user_ip, 
            hashed_password=hashed_password, 
            verification_code=verification_code, 
            country_code=country_code, 
            address=address)

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


def verify_handler(conn, cur, authenticated_user):

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
        
        front_office.verify(
            cur=cur, 
            email=email, 
            verification_code=verification_code)

        session['login_message'] = 'Successful verification'
        return redirect("/login")

    else:
        utils.AssertPeer(False, "Invalid method")

def login_handler(conn, cur, authenticated_user):

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

        user_data = front_office.login(cur=cur, email=email, password_=password_)

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

def home_handler(conn, cur, authenticated_user, page = 1):

    if authenticated_user == None:
        session_id_unauthenticated_user = request.cookies.get('session_id_unauthenticated_user')

        cur.execute("SELECT DISTINCT(category) FROM products")
        
        categories_db = cur.fetchall()
        categories = [category[0] for category in categories_db]

        cart_count = front_office.get_cart_items_count(conn=conn, cur=cur, user_id=session_id_unauthenticated_user)
        first_name = ""
        last_name = ""
        email = ""
    else:
        email = authenticated_user['user_row']['data']
        query = """
            WITH categories AS (
                SELECT DISTINCT(category) FROM products
            )
            SELECT *
            FROM categories 
            CROSS JOIN (SELECT * FROM users WHERE email = %s) u
        """
        
        cur.execute(query, (authenticated_user['user_row']['data'],))
        results = cur.fetchall()

        categories = [row[0] for row in results]
        user_id = results[0][1]
        first_name = results[0][2]
        last_name = results[0][3]

        cart_count = front_office.get_cart_items_count(conn=conn, cur=cur, user_id=user_id)

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

    results_from_home_page_query = front_office.prepare_home_data(
        cur=cur, 
        sort_by=sort_by, 
        sort_order=sort_order, 
        products_per_page=products_per_page, 
        page=page, 
        offset=offset, 
        product_name=product_name, 
        product_category=product_category, 
        price_min=price_min, 
        price_max=price_max)

    products = results_from_home_page_query['products']
    total_pages = results_from_home_page_query['total_pages']

    return render_template('home.html', first_name=first_name, last_name=last_name, 
                                email = email, products=products, products_per_page=products_per_page, 
                                price_min=price_min, price_max=price_max,page=page, total_pages=total_pages, 
                                sort_by=sort_by, sort_order=sort_order, product_name=product_name, 
                                product_category=product_category, cart_count=cart_count, categories=categories)

def logout_handler(conn, cur, authenticated_user):

    cur.execute("DELETE FROM custom_sessions WHERE session_id = %s", (authenticated_user['user_row']['session_id'],))

    response = make_response(redirect('/login'))
    response.set_cookie('session_id', '', expires=0)
    return response

def profile_handler(conn, cur, authenticated_user):

    if authenticated_user == None:
       return redirect('/login') 
    
    if request.method == 'GET':

        result_data = front_office.prepare_profile_data(cur=cur, authenticated_user=authenticated_user['user_row']['data'])

        if result_data:
            return render_template('profile.html', first_name=result_data['first_name'], last_name=result_data['last_name'],
                                     email=result_data['email'], address=result_data['address'], phone=result_data['phone'],
                                     gender=result_data['gender'], country_codes=result_data['country_codes'], country_code=result_data['code'])
        
        return render_template('profile.html')
    else:
        utils.AssertPeer(False, "Invalid method")

def update_profile_handler(conn, cur, authenticated_user):

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

        result_data = front_office.update_profile(cur=cur, conn=conn,first_name=first_name, last_name=last_name,
                                        email=email, password_=password_, 
                                        address=address, phone=phone, 
                                        country_code=country_code, gender=gender, 
                                        authenticated_user=authenticated_user['user_row']['data'])

        session['home_message'] = f"You successfully updated your {result_data['updated_fields_message']}."

        return redirect('/home/1')
    else:
        utils.AssertPeer(False, "Invalid method")

def delete_account_handler(conn, cur, authenticated_user):

    if authenticated_user == None:
       return redirect('/login')

    cur.execute("DELETE FROM users WHERE email = %s", (authenticated_user['user_row']['data'],))

    cur.execute("DELETE FROM custom_sessions WHERE session_id = %s", (authenticated_user['user_row']['session_id'],))
    response = make_response(redirect('/login'))
    response.set_cookie('session_id', '', expires=0)
    session['login_message'] = 'You successful deleted your account'
    return response
# 
def recover_password_handler(conn, cur, authenticated_user):

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

def send_login_link_handler(conn, cur, authenticated_user):

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

def login_with_token_handler(conn, cur, authenticated_user):

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image_size(image_stream):
    image_stream.seek(0, io.SEEK_END) # Seek to the end of the file
    file_size = image_stream.tell() # Get the current position, which is the file size
    image_stream.seek(0) # Reset the stream position to the start
    utils.AssertUser(file_size < MAX_FILE_SIZE, "The image file size must not exceed 10MB.")
    return image_stream.read()

def serve_image_handler(product_id, cur, authenticated_user):
    pr_id = request.path.split("/")[2]
    cur.execute("SELECT * FROM products WHERE id = %s", (pr_id,))
    image_blob = cur.fetchone()['image']
    return Response(image_blob, mimetype='jpeg')

def add_to_cart_handler(conn, cur, authenticated_user):

    product_id = request.form['product_id']
    quantity = request.form.get('quantity', 1)

    if authenticated_user == None:

        session_id_unauthenticated_user = request.cookies.get('session_id_unauthenticated_user')

        if session_id_unauthenticated_user == None:

            session_id = str(uuid.uuid4())

            response_message = front_office.add_to_cart(conn, cur, session_id, product_id, quantity, authenticated_user)
            newCartCount = front_office.get_cart_items_count(conn, cur, session_id)

            response = make_response(jsonify({'message': response_message, 'newCartCount': newCartCount}))
            response.set_cookie('session_id_unauthenticated_user', session_id, httponly=True, samesite='Lax')

        else:
            response_message = front_office.add_to_cart(conn, cur, session_id_unauthenticated_user, product_id, quantity, authenticated_user)
            newCartCount = front_office.get_cart_items_count(conn, cur, session_id_unauthenticated_user)

            response = make_response(jsonify({'message': response_message, 'newCartCount': newCartCount}))
    else:
        user_id = authenticated_user['user_row']['user_id']

        response_message = front_office.add_to_cart(conn, cur, user_id, product_id, quantity, authenticated_user)
        newCartCount = front_office.get_cart_items_count(conn, cur, user_id)

        response = make_response(jsonify({'message': response_message, 'newCartCount': newCartCount}))

    return response

def cart_handler(conn, cur, authenticated_user):

    if authenticated_user == None:
        session['login_message_unauth_user'] = "You have to login to see your cart"
        return redirect("/login")
    
    if request.method == 'GET':
        recovery_data = None

        if 'recovery_data_stack' in session:
            recovery_data_stack = session.get('recovery_data_stack', [])
            if len(recovery_data_stack) >= 1:
                recovery_data = recovery_data_stack.pop()
                #TODO assert
            else:
                utils.AssertDev(False, "Too many values in recovery_data_stack")
        else:
            recovery_data = None 

        result_data = front_office.prepare_cart_data(cur=cur, conn=conn,authenticated_user=authenticated_user)

        return render_template('cart.html', items=result_data['items'], total_sum_with_vat=round(result_data['total_sum_with_vat'],2), 
                                total_sum=round(result_data['total_sum'],2),country_codes=result_data['country_codes'], recovery_data=recovery_data, 
                                first_name=result_data['first_name'], last_name=result_data['last_name'], email=authenticated_user['user_row']['data'], vat=result_data['vat_in_persent'])
   
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

        response_post_cart = front_office.cart(cur=cur, email=email, first_name=first_name, last_name=last_name, 
                                                        town=town, address=address, country_code=country_code, 
                                                        phone=phone, authenticated_user=authenticated_user)
        utils.trace("response_post_cart")
        utils.trace(response_post_cart)

        #TODO: Move into job queue -> pattern 
        send_email = False
        try:
            utils.trace("ENTERED TRY BLOCK")

            send_mail_data = {
                "products": response_post_cart['cart_items'],
                "shipping_details": response_post_cart['shipping_details'],
                "total_sum": round(response_post_cart['total_sum'],2),
                "total_with_vat": round(response_post_cart['total_sum_with_vat'],2),
                "provided_sum": 0,
                "user_email": authenticated_user['user_row']['data'],
                "cur": cur,
                "conn": conn,
                "email_type": 'purchase_mail',
                "app": app,
                "mail": mail,
            }

            session['send_email'] = True
            session['send_mail_data'] = send_mail_data

            session['payment_message'] = "You successful made an order with id = " + str(response_post_cart['order_id'])

            return render_template('payment.html', order_id=response_post_cart['order_id'], order_products=response_post_cart['cart_items'], 
                                    shipping_details=response_post_cart['shipping_details'], total_sum_with_vat=round(response_post_cart['total_sum_with_vat'],2),
                                    total_sum=round(response_post_cart['total_sum'],2), first_name=response_post_cart['user_first_name'], 
                                    last_name=response_post_cart['user_last_name'], email=authenticated_user['user_row']['data'], 
                                    vat_in_persent = response_post_cart['vat_in_persent'])
        except Exception as e:
            conn.rollback()
            raise e
    else:
        utils.AssertPeer(False, "Invalid method")

def remove_from_cart_handler(conn, cur, authenticated_user):

    if authenticated_user == None:
       return redirect('/login')

    item_id = request.form['item_id']

    response = front_office.remove_from_cart(conn, cur, item_id)

    session['cart_message'] = response
    return redirect('/cart')

def finish_payment_handler(conn, cur, authenticated_user):

    if authenticated_user == None:
       return redirect('/login')
    
    if request.method == 'GET':

        order_id = request.args.get('order_id')

        response = front_office.prepare_finish_payment_data(cur=cur, authenticated_user=authenticated_user, order_id=order_id)

        return render_template('payment.html', order_id=order_id,order_products=response['order_products'], shipping_details=response['shipping_details'], 
                                total_sum=round(response['total_sum'], 2), total_sum_with_vat=round(response['total_with_vat'], 2), 
                                first_name = response['first_name'], last_name = response['last_name'], 
                                email = response['email'], vat_in_persent=response['vat_in_persent'])

    elif request.method == 'POST':

        order_id = request.form.get('order_id')
        payment_amount = request.form.get('payment_amount')

        if order_id == "":
            order_id = session.get('order_id')

        response_post = front_office.payment_method(cur=cur, payment_amount=payment_amount, order_id=order_id)

        send_email = False
        try:
            utils.trace("ENTERED TRY BLOCK")

            send_mail_data = {
                "products": response_post['products_from_order'],
                "shipping_details": response_post['shipping_details'],
                "total_sum": response_post['total'],
                "total_with_vat": response_post['total_with_vat'],
                "provided_sum": payment_amount,
                "user_email": authenticated_user['user_row']['data'],
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

def staff_login(conn, cur, authenticated_user):

    if request.method == 'GET':
        return render_template('staff_login.html')

    elif request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        response = back_office.staff_login(cur=cur, username=username, password=password)

        session['staff_username'] = response['username']

        session_id = sessions.create_session(session_data=username, cur=cur, conn=conn, is_front_office=False)
        response = make_response(redirect('/staff_portal'))
        response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')

        return response
    else:
        utils.AssertPeer(False, "Invalid method")

def staff_portal(conn, cur, authenticated_user):

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
    
def logout_staff(conn, cur, authenticated_user):

    cur.execute("DELETE FROM custom_sessions WHERE session_id = %s", (authenticated_user['user_row']['session_id'],))
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
        
def update_cart_quantity_handler(conn, cur, authenticated_user):
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

def user_orders_handler(conn, cur, authenticated_user):

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

        params.append(authenticated_user['user_row']['data'])

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

        cur.execute(query, params)
        orders = cur.fetchall()

        cur.execute("SELECT first_name, last_name FROM users WHERE email = %s", (authenticated_user['user_row']['data'],))
        user_details = cur.fetchone()

        return render_template('user_orders.html', 
            orders = orders, 
            statuses = statuses, 
            price_min=price_min, 
            price_max=price_max, 
            date_from=date_from, 
            date_to=date_to, 
            order_by_id=order_by_id, 
            first_name=user_details[0], 
            last_name=user_details[1],
             email=authenticated_user['user_row']['data'])
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

def back_office_manager(conn, cur, authenticated_user, *params):

    if authenticated_user == None:
       return redirect('/staff_login')

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
        utils.AssertUser(utils.has_permission(cur, request, 'Logs', 'read', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        if request.method == 'GET':
        
            validated_request_args_fields = utils.check_request_arg_fields(cur=cur, request=request)

            sort_by = validated_request_args_fields['sort_by']
            sort_order = validated_request_args_fields['sort_order']

            response = back_office.prepare_error_logs_data(cur=cur, sort_by=sort_by, sort_order=sort_order)

            return render_template('logs.html', log_exceptions = response['log exceptions'], sort_by=sort_by, sort_order=sort_order)
        else:
            utils.AssertPeer(False, "Invalid method")
    
    elif request.path == f'/update_captcha_settings':
        utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'read', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        if request.method == 'GET':

            current_settings = utils.get_current_settings(cur)

            response = back_office.prepare_settings_data(cur)

            return render_template(
                'captcha_settings.html', 
                vat=response['vat'],
                limitation_rows=response['limitation_rows'], 
                border_collapse=response['border_collapse'],
                border=response['border'],
                text_align=response['text_align'],
                background_color=response['background_color'],
                **current_settings)

        elif request.method == 'POST':
            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', authenticated_user['user_row']['data']), "You don't have permission to this resource")

            new_max_attempts = request.form['max_captcha_attempts']
            new_timeout_minutes = request.form['captcha_timeout_minutes']

            response = back_office.captcha_settings(cur, new_max_attempts, new_timeout_minutes)
        
            if response['message'] != "":
                session['staff_message'] = response['message']

            return redirect(f'/staff_portal')
        else:
            utils.AssertPeer(False, "Invalid method")

    elif request.path == f'/update_report_limitation_rows':
        if request.method == 'POST':
            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', authenticated_user['user_row']['data']), "You don't have permission to this resource")

            limitation_rows = int(request.form['report_limitation_rows'])

            response = back_office.post_update_limitation_rows(cur=cur, limitation_rows=limitation_rows)

            session['staff_message'] = response['message']

            return redirect(f'/staff_portal')
        else:
            utils.AssertPeer(False, "Invalid method") 

    elif request.path == f'/update_email_templates_table':
        if request.method == 'POST':
            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', authenticated_user['user_row']['data']), "You don't have permission to this resource")

            background_color = request.form['background_color']
            text_align = request.form['text_align']
            border = request.form['border']
            border_collapse = request.form['border_collapse']

            response = back_office.edit_email_table(
                cur=cur, 
                background_color=background_color, 
                text_align=text_align, 
                border=border, 
                border_collapse=border_collapse)

            session['staff_message'] = response['message']

            return redirect(f'/staff_portal')
        else:
            utils.AssertPeer(False, "Invalid method")

    elif request.path == f'/update_vat_for_all_products':
        if request.method == 'POST':

            utils.AssertUser(utils.has_permission(cur, request, 'Captcha Settings', 'update', authenticated_user['user_row']['data']), "You don't have permission to this resource")
            vat_for_all_products = request.form['vat_for_all_products']

            response = back_office.vat_for_all_products(cur=cur, vat_for_all_products=vat_for_all_products)

            session['staff_message'] = response['message']

            return redirect(f'/staff_portal')
        else:
            utils.AssertPeer(False, "Invalid method")      

    elif request.path == f'/report_sales':
        utils.AssertUser(utils.has_permission(cur, request, 'Report sales', 'read', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        default_to_date = datetime.now()
        dafault_from_date = default_to_date - timedelta(days=90)

        default_to_date_str = default_to_date.strftime('%Y-%m-%d')
        default_from_date_str = dafault_from_date.strftime('%Y-%m-%d')

        if request.method == 'GET':

            return render_template('report.html', default_to_date=default_to_date_str, default_from_date=default_from_date_str)
        
        elif request.method == 'POST':

            date_from = request.form.get('date_from')
            date_to = request.form.get('date_to')

            group_by = request.form.get('group_by')
            status = request.form.get('status')
            filter_by_status = request.form.get('filter_by_status', '')
            order_id = request.form.get('sale_id')

            page = request.args.get('page', 1, type=int)
            per_page = 1000  

            response = back_office.report_sales(
                cur = cur, 
                date_from = date_from, 
                date_to = date_to, 
                group_by = group_by, 
                status = status, 
                filter_by_status = filter_by_status, 
                order_id = order_id, 
                page = page)
            

            return render_template(
                'report.html', 
                limitation_rows = response['limitation_rows'], 
                filter_by_status = response['filter_by_status'],
                report = response['report'], 
                total_records =response['total_records'], 
                total_price_with_vat = response['total_price_with_vat'],
                total_vat = response['total_vat'],
                total_price = response['total_price'], 
                report_json = response['report_json'], 
                default_to_date = response['default_to_date'], 
                default_from_date = response['default_from_date'])
        else:
            utils.AssertPeer(False, "Invalid url")

    elif request.path == f'/download_report_without_generating_rows_in_the_html':

        form_data = {key: request.form.get(key, '') for key in ['date_from', 'date_to', 'format']}

        response_generate = back_office.download_report(form_data=form_data)

        response = Response(stream_with_context(response_generate()), mimetype='text/csv')
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

        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'read', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        role = request.path.split('/')[1]

        cur.execute("SELECT role_id, role_name FROM roles")
        roles = cur.fetchall()

        selected_role = int(request.args.get('role', roles[0][0] if roles else None))

        cur.execute("SELECT DISTINCT interface FROM permissions ORDER BY interface ASC")

        interfaces = []
        for interface in cur.fetchall():
            interfaces.append(interface[0])

        if request.method == 'GET':
            
            response = back_office.prepare_role_permissions_data(cur=cur, role=role, selected_role=selected_role, interfaces=interfaces)

            return render_template(
                'role_permissions.html', 
                roles=response['roles'],
                interfaces=response['interfaces'], 
                role_permissions=response['role_permissions'], 
                selected_role=selected_role, 
                role_to_display=role)
    
        elif request.method == 'POST':

            utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'update', authenticated_user['user_row']['data']), "You don't have permission to this resource")

            role_id = request.form['role']

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.role_permissions(cur=cur, role_id=role_id, form_data=form_data, interfaces=interfaces)

            session['role_permission_message'] = response['message']

            return redirect(f'/role_permissions?role=' + role_id)
        else:
            utils.AssertPeer(False, "Invalid method")

    elif request.path == f'/crud_products' and len(request.path.split('/')) == 2:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'read', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        validated_request_args_fields = utils.check_request_arg_fields(cur=cur, request=request)

        sort_by = validated_request_args_fields['sort_by']
        sort_order = validated_request_args_fields['sort_order']
        price_min = validated_request_args_fields['price_min']
        price_max = validated_request_args_fields['price_max']

        response = back_office.prepare_crud_products_data(
            cur = cur, 
            sort_by = sort_by, 
            sort_order = sort_order, 
            price_min = price_min, 
            price_max = price_max)

        return render_template('crud.html', products=response['products'], sort_by=sort_by, sort_order=sort_order, price_min=price_min or '', price_max=price_max or '')

    elif request.path == f'/crud_products/add_product' and len(request.path.split('/')) == 3:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'create', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        if request.method == 'GET':

            response = back_office.prepare_crud_add_product_data(cur=cur)

            return render_template('add_product_staff.html', categories=response['categories'], currencies=response['all_currencies'])

        elif request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}
            files_data = {file_field: request.files.get(file_field) for file_field in request.files}

            response = back_office.crud_add_product(cur, form_data, files_data)

            session['crud_message'] = response['message']

            return redirect(f'/crud_products')
        else:
            utils.AssertDev(False, "Different method")

    elif re.match(r'^/crud_products/edit_product/\d+$', request.path) and len(request.path.split('/')) == 4:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'update', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        product_id = request.path.split('/')[3]

        if request.method == 'GET':

            response = back_office.prepare_edit_product_data(cur=cur, product_id=product_id)

            return render_template('edit_product.html', product=response['product'], product_id=product_id, currencies = response['all_currencies'])

        elif request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.edit_product(cur=cur, form_data=form_data, files_data="", product_id=product_id)

            session['crud_message'] = response['message']

            return redirect(f'/crud_products')
        else:
            utils.AssertDev(False, "Different method")

    elif re.match(r'/crud_products/delete_product/\d+$', request.path) and len(request.path.split('/')) == 4:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Products', 'delete', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        product_id = request.path.split('/')[3]

        response = back_office.delete_product(cur=cur, product_id=product_id)

        session['crud_message'] = response['message']

        return redirect(f'/crud_products')

    elif request.path == f'/crud_staff' and len(request.path.split('/')) == 2:

        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'read', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        response = back_office.prepare_crud_staff_data(cur=cur)

        return render_template('staff_role_assignment.html', relations=response['relations'])

    elif request.path == f'/crud_staff/add_role_staff' and len(request.path.split('/')) == 3:

        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'create', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        if request.method == 'GET':
            
            response = back_office.prepare_add_role_staff_data(cur=cur)

            return render_template('add_staff_role.html', staff=response['staff'], roles=response['roles'])

        elif request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.add_role_staff(cur=cur, form_data=form_data, files_data="")

            session['staff_message'] = response['message']

            return redirect('/staff_portal')
        else:
            utils.AssertDev(False, "Different method")

    elif request.path == f'/crud_staff/add_staff' and len(request.path.split('/')) == 3:

        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'create', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        if request.method == 'GET':

            return render_template('add_staff.html')

        elif request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.add_staff(cur=cur, form_data=form_data, files_data="")

            session['staff_message'] = response['message']
            return redirect('/staff_portal')
        else:
            utils.AssertDev(False, "Different method")

    elif re.match(r'/crud_staff/delete_role/\d+/\d+$', request.path) and len(request.path.split('/')) == 5:

        utils.AssertUser(utils.has_permission(cur, request, 'Staff roles', 'delete', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        staff_id = request.path.split('/')[3]
        role_id = request.path.split('/')[4]

        response = back_office.delete_crud_staff_role(cur=cur, staff_id=staff_id, role_id=role_id)

        session['staff_message'] = response['message']
        return redirect(f'/staff_portal')

    elif request.path == f'/crud_orders' and len(request.path.split('/')) == 2:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'read', authenticated_user['user_row']['data']), "You don't have permission for this resource")

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

        response = back_office.prepare_crud_orders_data(
            cur = cur, 
            sort_by = sort_by, 
            sort_order = sort_order, 
            price_min = price_min, 
            price_max = price_max, 
            order_by_id = order_by_id, 
            date_from = date_from, 
            date_to = date_to, 
            status = status, 
            page = page, 
            per_page = per_page, 
            offset = offset)

        return render_template(
            'crud_orders.html', 
            page=response['page'],
            total_pages=response['total_pages'],
            orders=response['orders'], 
            statuses=response['statuses'], 
            current_status=response['current_status'], 
            price_min=price_min, 
            price_max=price_max, 
            order_by_id=order_by_id, 
            date_from=date_from, 
            date_to=date_to, 
            per_page=per_page, 
            sort_by=sort_by, 
            sort_order=sort_order)

    elif request.path == f'/crud_orders/add_order' and len(request.path.split('/')) == 3:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'create', authenticated_user['user_row']['data']), "You don't have permission for this resource")

        if request.method == 'GET':
            
            response = back_office.prepare_crud_orders_add_order_data(cur=cur)

            return render_template('add_order.html', statuses=response['statuses'])

        elif request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.crud_orders_add_order(cur, form_data=form_data, files_data="")

            session['crud_message'] = response['message']

            return redirect(f'/crud_orders')
        else:
            utils.AssertUser(False, "Invalid operation")

    elif re.match(r'/crud_orders/edit_order/\d+$', request.path) and len(request.path.split('/')) == 4:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'update', authenticated_user['user_row']['data']), "You don't have permission for this resource")

        order_id = request.path.split('/')[3]

        if request.method == 'GET':

            response = back_office.prepare_crud_orders_edit_order_data(cur=cur, order_id=order_id)

            return render_template(
                'edit_order.html', 
                order_id=order_id, 
                statuses=response['statuses'], 
                order_date = response['order_date'], 
                products_from_order=response['products_from_order'], 
                all_products_sum=response['all_products_sum'])

        elif request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.crud_orders_edit_order(cur=cur, order_id=order_id, form_data=form_data, files_data="")
            
            session['crud_message'] = response['message']

            return redirect(f'/crud_orders')
        else:
            utils.AssertUser(False, "Invalid operation")

    elif re.match(r'/crud_orders/delete_order/\d+$', request.path) and len(request.path.split('/')) == 4:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Orders', 'delete', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        order_id = request.path.split('/')[3]

        response = back_office.delete_crud_orders_edit_order(cur=cur, order_id=order_id)

        session['crud_message'] = response['message']       

        return redirect(f'/crud_orders')

    elif request.path == f'/crud_users' and len(request.path.split('/')) == 2:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'read', authenticated_user['user_row']['data']), "You don't have permission for this resource")

        if request.method == 'GET':

            fields = utils.check_request_arg_fields(cur, request)

            sort_by = fields['sort_by']
            sort_order = fields['sort_order']
            email = fields['email']
            user_by_id = fields['user_by_id']
            status = fields['status']

            response = back_office.prepare_crud_users_data(
                cur=cur, 
                email=email, 
                user_by_id=user_by_id, 
                status=status, 
                sort_by=sort_by, 
                sort_order=sort_order)

            return render_template('crud_users.html', users=response['users'], statuses=response['statuses'], email=fields['email'], user_by_id=fields['user_by_id'])

        elif request.method == 'POST':

            return redirect(f'/crud_users')

        else:
            utils.AssertUser(False, "Invalid method")


    elif request.path == f'/crud_users/add_user' and len(request.path.split('/')) == 3:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'create', authenticated_user['user_row']['data']), "You don't have permission for this resource")

        if request.method == 'GET':

            response = back_office.prepare_crud_users_add_user_data(cur=cur)

            return render_template("add_user.html", statuses=response['statuses']) 

        elif request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.crud_users_add_user(cur=cur, form_data=form_data, files_data="")

            session['crud_message'] = response['message']

            return redirect(f'/crud_users')

        else:
            utils.AssertUser(False, "Invalid method")

    elif re.match(r'/crud_users/edit_user/\d+$', request.path) and len(request.path.split('/')) == 4:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'update', authenticated_user['user_row']['data']), "You don't have permission for this resource")

        if request.method == 'GET':

            user_id = request.path.split('/')[3]

            response = back_office.prepare_crud_users_edit_user_data(cur=cur, user_id=user_id)

            return render_template(
                'edit_user.html', 
                first_name=response['first_name'], 
                last_name=response['last_name'], 
                email=response['email'], 
                verification_status=response['verification_status'], 
                user_id=user_id)

        elif request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}
            user_id = request.path.split('/')[3]
            
            response = back_office.crud_users_edit_user(cur=cur, form_data=form_data, files_data="", user_id=user_id)

            session['crud_message'] = response['message']

            return redirect(f'/crud_users')

        else:
            utils.AssertUser(False, "Invalid method")

    elif re.match(r'/crud_users/delete_user/\d+$', request.path) and len(request.path.split('/')) == 4:

        utils.AssertUser(utils.has_permission(cur, request, 'CRUD Users', 'delete', authenticated_user['user_row']['data']), "You don't have permission to this resource")

        user_id = request.path.split('/')[3]

        response = back_office.delete_crud_users_user(cur=cur, user_id=user_id)

        session['crud_message'] = "You successfully deleted user with id: " + str(user_id)

        return redirect(f'/crud_users')

    elif request.path == f'/template_email':

        if request.method == 'GET':

            response = back_office.prepare_template_email_data(cur)

            return render_template(
                'template_email.html', 
                subject = response['subject'], 
                body = response['body'], 
                tepmplate_subject_purchase = response['subject_purchase'], 
                tepmplate_body_purchase = response['body_purchase'], 
                tepmplate_subject_payment = response['subject_payment'], 
                tepmplate_body_payment = response['body_payment'],
                background_color = response['background_color'], 
                text_align = response['text_align'],
                border = response['border'], 
                border_collapse = response['border_collapse'])

        elif request.method == 'POST':
            
            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.edit_email_template(cur=cur, template_name='Verification Email', form_data=form_data, files_data="")

            session['staff_message'] = response['message']

            return redirect(f'/staff_portal')

        else:
            utils.AssertUser(False, "Invalid method")

    elif request.path == f'/template_email_purchase':

        if request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.edit_email_template(cur=cur, template_name='Purchase Email', form_data=form_data, files_data="")

            session['staff_message'] = response['message']

            return redirect(f'/staff_portal')

        else:
           utils.AssertUser(False, "Invalid method")

    elif request.path == f'/template_email_payment':

        if request.method == 'POST':

            form_data = {field: request.form.get(field) for field in request.form}

            response = back_office.edit_email_template(cur=cur, template_name='Payment Email', form_data=form_data, files_data="")

            session['staff_message'] = response['message']

            return redirect(f'/staff_portal')

        else:
           utils.AssertUser(False, "Invalid method")  

    else:
        utils.AssertPeer(False, "Invalid url")

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')


url_to_function_map_front_office = [
    (r'/registration', registration_handler),
    (r'/refresh_captcha', refresh_captcha_handler),
    (r'/verify', verify_handler),
    (r'/login', login_handler),
    (r'/home', home_handler),
    (r'/home(?:\?page=([1-9]+)\?[A-z,\=,\&]+)?', home_handler),
    (r'/logout', logout_handler),
    (r'/profile', profile_handler),
    (r'/update_profile', update_profile_handler),
    (r'/delete_account', delete_account_handler),
    (r'/recover_password', recover_password_handler),
    (r'/resend_verf_code', resend_verf_code),
    (r'/send_login_link', send_login_link_handler),
    (r'/log', login_with_token_handler),
    (r'/image/(\d+)', serve_image_handler),
    (r'/generate_orders', generate_orders),
    (r'/add_to_cart', add_to_cart_handler),
    (r'/cart', cart_handler),
    (r'/update_cart_quantity', update_cart_quantity_handler),
    (r'/remove_from_cart', remove_from_cart_handler),
    (r'/finish_payment', finish_payment_handler),
    (r'/user_orders', user_orders_handler),
]

url_to_function_map_back_office = [
    (r'/staff_login', staff_login),
    (r'/staff_portal', staff_portal),
    (r'/logout_staff', logout_staff),
    (r'/(crud_products_edit_picture|error_logs|update_captcha_settings|report_sales|crud_products|crud_staff|role_permissions|download_report|crud_orders|active_users|download_report_without_generating_rows_in_the_html|upload_products|crud_users|template_email|update_report_limitation_rows|update_email_templates_table|update_vat_for_all_products)(?:/[\w\d\-_/]*)?', back_office_manager),
]


url_fields_mapper = {
    r'/registration': {
        'first_name': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 50 and re.match(r'^[A-Za-z]+$', x)), "First name must be between 3 and 50 letters and contain no special characters or digits")]},
        'last_name': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 3 and len(x) <= 50 and re.match(r'^[A-Za-z]+$', x)), "Last name must be between 3 and 50 letters and contain no special characters or digits")]},
        'email': {'type': str, 'required': True, 'conditions': [((lambda x: re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', x)), "Email is not valid")]},
        'password': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 8 and len(x) <= 20), "Password must be between 8 and 20 symbols")]},
        'confirm_password': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 8 and len(x) <= 20), "Password and Confirm Password fields are different")]},
        'address': {'type': str, 'required': False, 'conditions': [((lambda x: len(x) >= 5 and len(x) <= 50), "Address must be between 5 and 50 symbols")]},
        'country_code': {'type': str, 'required': True, 'conditions': [((lambda x: len(x) >= 1 and len(x) <= 4), "Invalid country code")]},
        'phone': {'type': str, 'required': True, 'conditions': [((lambda x: re.fullmatch(r'^\d{7,15}$', x)), "Phone number format is not valid. The number should be between 7 and 15 digits")]},
        'gender': {'type': str, 'required': True, 'conditions': [((lambda x: x == 'male' or x == 'female' or x == 'other'), "Gender must be Male of Female or Prefere not to say")]},
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

        authenticated_user = sessions.get_current_user(session_id, cur=cur, conn=conn)

        funtion_to_call = None
        match = None

        # True for front office, false for back office
        flag_office = None

        if authenticated_user is not None:
            flag_office = sessions.get_session_cookie_type(session_id, cur)
        else:
            flag_office = True

        if not flag_office or request.path == '/staff_login':
            funtion_to_call = map_function(url_to_function_map_back_office)
        else:
            if request.method == 'POST':
                form_data = request.form.to_dict()
                utils.check_request_form_fields_post_method(path=request.path, needed_fields=url_fields_mapper, form_data=form_data)
            else:
                pass

            funtion_to_call = map_function(url_to_function_map_front_office)

     
        if flag_office and authenticated_user is not None:
            cur.execute("UPDATE users SET last_active = now() WHERE email = %s", (authenticated_user['user_row']['data'],))
        else:
            pass

        utils.AssertDev(callable(funtion_to_call), "You are trying to invoke something that is not a function")

        if match:
            response = funtion_to_call(conn, cur, authenticated_user,*match.groups())
        else:
            response = funtion_to_call(conn, cur, authenticated_user)

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

        user_data = sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)
        
        if user_data is None:
            user_email = 'Guest'
        else:
            user_email = user_data['user_row']['data']

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