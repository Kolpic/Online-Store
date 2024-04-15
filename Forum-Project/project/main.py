from flask import Flask, request, render_template, redirect, url_for, session, abort, Response
from flask_mail import Mail, Message
import psycopg2, os, re, secrets, psycopg2.extras, uuid
import bcrypt
import datetime, random
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

database = config.database
user = config.user
password = config.password
host = config.host
 
app.add_url_rule("/", defaults={'path':''}, endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])  
app.add_url_rule("/<path:path>", endpoint="handle_request", methods=['GET', 'POST', 'PUT', 'DELETE'])  

# def main:
#     cb = getCommandByEndpoint()
#     try
#     cb()

def assertIsMailInSession():
    if not 'user_email' in session: raise exception.MethodNotAllowed("You tried to asscess resources, you don't have permission for")

def assertIsProvidedMethodsTrue(*args):
    if len(args) == 2:
        if not request.method == 'GET' and not request.method == 'POST': raise exception.MethodNotAllowed("You tried to asscess resources, you don't have permission for")
    else:
        method_type = str(args[0]).upper()
        if not request.method == method_type: raise exception.MethodNotAllowed("You tried to asscess resources, you don't have permission for")

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

    utils.Assert(password_ != confirm_password_, "Password and Confirm Password fields are different")
    # if password_ != confirm_password_:
    #     utils.add_form_data_in_session(form_data)
    #     raise exception.WrongUserInputRegistration("Password and Confirm Password fields are different")

    cur.execute("SELECT id, last_attempt_time, attempts FROM captcha_attempts WHERE ip_address = %s", (user_ip,))
    attempt_record = cur.fetchone()

    attempts = 0
    max_attempts = int(utils.get_captcha_setting_by_name(cur, 'max_captcha_attempts'))
    timeout_minutes = int(utils.get_captcha_setting_by_name(cur,'captcha_timeout_minutes'))

    if attempt_record:
        attempt_id, last_attempt_time, attempts = attempt_record
        time_since_last_attempt = datetime.now() - last_attempt_time
        utils.Assert(attempts >= max_attempts and time_since_last_attempt < timedelta(minutes=timeout_minutes), "You typed wrong captcha several times, now you have timeout")
        # if attempts >= max_attempts and time_since_last_attempt < timedelta(minutes=timeout_minutes):
        #     raise exception.WrongUserInputRegistration("You typed wrong captcha 3 times, you have timeout 30 minutes")
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
        raise exception.WrongUserInputRegistration("Invalid CAPTCHA. Please try again")
    else:
        if attempt_record:
            cur.execute("DELETE FROM captcha_attempts WHERE id = %s", (attempt_id,))

    # TODO utils.add_form_data_in_session(form_data)
    utils.Assert(len(first_name) < 3 or len(first_name) > 50, "First name is must be between 3 and 50 symbols")
    # if len(first_name) < 3 or len(first_name) > 50:
    #     utils.add_form_data_in_session(form_data)
    #     raise exception.WrongUserInputRegistration('First name is must be between 3 and 50 symbols')
    utils.Assert(len(last_name) < 3 or len(last_name) > 50, "Last name must be between 3 and 50 symbols")
    # if len(last_name) < 3 or len(last_name) > 50:
    #     utils.add_form_data_in_session(form_data)
    #     raise exception.WrongUserInputRegistration('Last name must be between 3 and 50 symbols')
        
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    # boolean_regex = re.fullmatch(regex, email)
    utils.Assert(re.fullmatch(regex, email), "Email is not valid")
    # if not (re.fullmatch(regex, email)):
    #     utils.add_form_data_in_session(form_data)
    #     raise exception.WrongUserInputRegistration('Email is not valid')
    
    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    is_email_present_in_database = cur.fetchone()
    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_email_verified = cur.fetchone()

    if is_email_present_in_database != None:
        utils.Assert(is_email_present_in_database[0] and is_email_verified[0], "There is already registration with this email")
        # if is_email_present_in_database[0] and is_email_verified[0]:
        #     utils.add_form_data_in_session(form_data)
        #     raise exception.WrongUserInputRegistration('There is already registration with this email')
        utils.Assert(is_email_present_in_database[0] and not is_email_verified[0], "Account was already registered and deleted with this email, type another email")
        # if is_email_present_in_database[0] and not is_email_verified[0]:
        #     utils.add_form_data_in_session(form_data)
        #     raise exception.WrongUserInputRegistration('Account was already registered and deleted with this email, type another email')

    cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", (first_name, last_name, email, hashed_password, verification_code))
    conn.commit()

    send_verification_email(email, verification_code)

    session['verification_message'] = 'Successful registration'
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
        return render_template('verify.html')

    email = request.form['email']
    verification_code = request.form['verification_code']

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))

    utils.Assert(cur.rowcount == 0, "There is no registration with this email")

    email_from_database = cur.fetchone()['email']

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_verified = cur.fetchone()['verification_status']

    cur.execute("SELECT verification_code FROM users WHERE email = %s", (email,))
    verification_code_database = cur.fetchone()['verification_code']

    utils.Assert(email_from_database != email, "You entered different email")
    utils.Assert(is_verified, "The account is already verified")
    utils.Assert(verification_code_database != verification_code, "The verification code you typed is different from the one we send you")
    
    cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", (verification_code,))
    conn.commit()

    session['login_message'] = 'Successful verification'
    return redirect("/login") 

def login(conn, cur):
    assertIsProvidedMethodsTrue('GET','POST')

    if request.method == 'GET':
        return render_template('login.html')

    email = request.form['email']
    password_ = request.form['password']

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))

    utils.Assert(cur.rowcount == 0, "There is no registration with this email")

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
        
    is_the_email_verified = cur.fetchone()['verification_status']

    cur.execute("SELECT password FROM users WHERE email = %s", (email,))
        
    hashed_password = cur.fetchone()['password']

    are_passwords_same = bool(utils.verify_password(password_, hashed_password))

    utils.Assert(are_passwords_same, "Invalid email or password")
    utils.Assert(is_the_email_verified, "Your account is not verified or has been deleted")

    session['user_email'] = email   
    return redirect("/home")

def home(conn, cur):
    if not utils.is_authenticated():
        return redirect('/login')
    
    cur.execute("SELECT * FROM products LIMIT 10")
    products = cur.fetchall()

    return render_template('home.html', products=products)

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
    assertIsMailInSession()

    first_name = request.form['first-name']
    last_name = request.form['last-name']
    email = request.form['email']
    password_ = request.form['password']
    
    query_string = "UPDATE users SET "
    fields_list = []
    updated_fields = []

    if first_name:
        if len(first_name) < 3 or len(first_name) > 50:
            session['settings_error'] = 'First name must be between 3 and 50 symbols'
            return redirect('/profile')
        query_string += "first_name = %s, "
        fields_list.append(first_name)
        updated_fields.append("first name")
    if last_name:
        if len(last_name) < 3 or len(last_name) > 50:
            session['settings_error'] = 'Last name must be between 3 and 50 symbols'
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
    assertIsMailInSession()

    user_email = session['user_email']

    cur.execute("UPDATE users SET verification_status = false WHERE email = %s", (user_email,))
    conn.commit()
    session.clear()
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

    utils.Assert(cur.rowcount == 0, "There is no registration with this email")
    
    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_verified = cur.fetchone()[0]

    utils.Assert(is_verified, "The account is already verified")

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
    utils.Assert(cur.rowcount == 0, "There is no registration with this email")

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_verified = cur.fetchone()[0]

    utils.Assert(is_verified, "The account is already verified")
    
    expiration_time = datetime.now() + timedelta(hours=1)

    cur.execute("INSERT INTO tokens(login_token, expiration) VALUES (%s, %s)", (login_token, expiration_time))
    conn.commit()
    cur.execute("SELECT id FROM tokens WHERE login_token = %s", (login_token,))
    token_id = cur.fetchone()[0]
    cur.execute("UPDATE users SET token_id = %s WHERE email = %s", (token_id, email))

    conn.commit()

    login_link = f"http://127.0.0.1:5000/log?token={login_token}"
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

    if not token_data or token_data[1] < datetime.datetime.now():
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
    assertIsMailInSession()

    if request.method == 'GET':
        current_settings = utils.get_current_settings(cur)
        return render_template('captcha_settings.html', **current_settings)

    new_max_attempts = request.form['max_captcha_attempts']
    new_timeout_minutes = request.form['captcha_timeout_minutes']

    utils.Assert(new_max_attempts and int(new_max_attempts) <= 0, "Captcha attempts must be possitive number")
    utils.Assert(new_timeout_minutes and int(new_timeout_minutes) <= 0, "Timeout minutes must be possitive number")

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
    assertIsMailInSession()

    cur.execute("SELECT * FROM exception_logs")
    log_exceptions = cur.fetchall()

    return render_template('logs.html', log_exceptions = log_exceptions)

def log_exception(conn, cur, exception_type, message ,email = None):

    cur.execute("INSERT INTO exception_logs (user_email, exception_type, message) VALUES (%s, %s, %s)", (email, exception_type, message))
    conn.commit()

def add_product(conn, cur):
    name = request.form['name']
    price = request.form['price']
    quantity = request.form['quantity']
    category = request.form['category']
    image = request.files['image'].read()

    cur.execute("INSERT INTO products (name, price, quantity, category, image) VALUES (%s, %s, %s, %s, %s)", (name, price, quantity, category, image))
    conn.commit()
    return redirect('/home')

@app.route('/image/<int:product_id>')
def serve_image(product_id):
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()
    cur.execute("SELECT image FROM products WHERE id = %s", (product_id,))
    image_blob = cur.fetchone()[0]
    return Response(image_blob, mimetype='jpeg')

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

url_to_function_map = {
    '/': registration,
    '/registration': registration,
    '/verify': verify,
    '/login': login,
    '/home': home,
    '/logout': logout,
    '/profile': profile,
    '/update_profile': update_profile,
    '/delete_account': delete_account,
    '/recover_password': recover_password,
    '/resend_verf_code': resend_verf_code,
    '/send_login_link': send_login_link,
    '/log': login_with_token,
    '/logs': view_logs,
    '/update_captcha_settings': update_captcha_settings,
    '/add_product': add_product,
    '/image/<int:product_id>': serve_image,
    '/momo': 'momo',
}

@app.endpoint("handle_request")
def handle_request(**kwargs):
    conn = None
    cur = None
    try:
        request_path = request.path
        funtion_to_call = url_to_function_map.get(request_path)

        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()

        utils.Assert(funtion_to_call, "Invalid url address")
        utils.Assert(funtion_to_call, "You are trying to invoke something that is not function !!!")

        return funtion_to_call(conn, cur)
    except Exception as message:
        user_email = session.get('user_email', 'Guest')
        log_exception(conn, cur, message.__class__.__name__, str(message), user_email)

        if message.__class__.__name__ == 'DevException':
            message = 'Internal error'

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