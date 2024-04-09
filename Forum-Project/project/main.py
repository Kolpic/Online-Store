from flask import Flask, request, render_template, redirect, url_for, session, abort
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

def registration():
    user_ip = request.remote_addr

    if request.method != 'GET' and request.method != 'POST':
        raise exception.MethodNotAllowed()

    if request.method == 'GET':
        form_data = session.get('form_data_stack', []).pop() if 'form_data_stack' in session and len(session['form_data_stack']) > 0 else None
        if form_data:
            session.modified = True
        first_captcha_number = random.randint(0,100)
        second_captcha_number = random.randint(0,100)

        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
        cur = conn.cursor()

        cur.execute("INSERT INTO captcha(first_number, second_number, result) VALUES (%s, %s, %s) RETURNING id", (first_captcha_number, second_captcha_number, first_captcha_number + second_captcha_number))
        conn.commit()
        captcha_id = cur.fetchone()[0]
        
        session["captcha_id"] = captcha_id
        return render_template('registration.html', form_data=form_data, captcha = {"first": first_captcha_number, "second": second_captcha_number})

    form_data = request.form.to_dict()

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    cur = conn.cursor()

    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    password_ = request.form['password']
    confirm_password_ = request.form['confirm_password']
    captcha_ = int(request.form['captcha'])

    if password_ != confirm_password_:
        utils.add_form_data_in_session(form_data)
        raise exception.WrongUserInputRegistration("Password and Confirm Password fields are different")

    cur.execute("SELECT id, last_attempt_time, attempts FROM captcha_attempts WHERE ip_address = %s", (user_ip,))
    attempt_record = cur.fetchone()

    attempts = 0

    if attempt_record:
        attempt_id, last_attempt_time, attempts = attempt_record
        time_since_last_attempt = datetime.now() - last_attempt_time
        if attempts >= 3 and time_since_last_attempt < timedelta(minutes=30):
            raise exception.WrongUserInputRegistration("You typed wrong captcha 3 times, you have timeout 30 minutes")
        elif time_since_last_attempt >= timedelta(minutes=30):
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

    if len(first_name) < 3 or len(first_name) > 50:
        utils.add_form_data_in_session(form_data)
        raise exception.WrongUserInputRegistration('First name is must be between 3 and 50 symbols')
    if len(last_name) < 3 or len(last_name) > 50:
        utils.add_form_data_in_session(form_data)
        raise exception.WrongUserInputRegistration('Last name must be between 3 and 50 symbols')
        
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

    if not (re.fullmatch(regex, email)):
        utils.add_form_data_in_session(form_data)
        raise exception.WrongUserInputRegistration('Email is not valid')
    
    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    is_email_present_in_database = cur.fetchone()
    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_email_verified = cur.fetchone()

    if is_email_present_in_database != None:
        if is_email_present_in_database[0] and is_email_verified[0]:
            utils.add_form_data_in_session(form_data)
            raise exception.WrongUserInputRegistration('There is already registration with this email')
        if is_email_present_in_database[0] and not is_email_verified[0]:
            utils.add_form_data_in_session(form_data)
            raise exception.WrongUserInputRegistration('Account was already registered and deleted with this email, type another email')

    cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", (first_name, last_name, email, hashed_password, verification_code))
    conn.commit()
    cur.close()

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

def verify():
    if request.method != 'GET' and request.method != 'POST':
        raise exception.MethodNotAllowed()

    if request.method == 'GET':
        return render_template('verify.html')
    
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    email = request.form['email']
    verification_code = request.form['verification_code']

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    email_from_database = cur.fetchone()['email']

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_verified = cur.fetchone()['verification_status']

    cur.execute("SELECT verification_code FROM users WHERE email = %s", (email,))
    verification_code_database = cur.fetchone()['verification_code']

    if email_from_database != email:
        raise exception.WrongUserInputVerification('You entered different email')
    if is_verified:
        raise exception.WrongUserInputVerification('The account is already verified')
    if verification_code_database != verification_code:
        raise exception.WrongUserInputVerification('The verification code you typed is different from the one we send you')
    
    cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", (verification_code,))
    conn.commit()
    cur.close()

    session['login_message'] = 'Successful verification'
    return redirect("/login") 

def login():
    if request.method != 'GET' and request.method != 'POST':
        raise exception.MethodNotAllowed()

    if request.method == 'GET':
        return render_template('login.html')

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    email = request.form['email']
    password_ = request.form['password']

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
        
    is_the_email_verified = cur.fetchone()['verification_status']

    cur.execute("SELECT password FROM users WHERE email = %s", (email,))
        
    hashed_password = cur.fetchone()['password']

    are_passwords_same = bool(utils.verify_password(password_, hashed_password))

    if not are_passwords_same:
        raise exception.WrongUserInputLogin('Invalid email or password')

    if not is_the_email_verified:
        raise exception.WrongUserInputLogin('Your account is not verified or has been deleted')

    session['user_email'] = email   
    return redirect("/home")

def home():
    if not utils.is_authenticated():
        return redirect('/login')
    
    return render_template('home.html')

def logout():
    session.pop('user_email', None) 
    return redirect('/home')

def profile():
    if 'user_email' not in session:
        return redirect('/login')
    
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()
    cur.execute("SELECT first_name, last_name, email FROM users WHERE email = %s", (session['user_email'],))
    user_details = cur.fetchone()
    conn.commit()

    if user_details:
        return render_template('profile.html', user_details=user_details)
    
    return render_template('profile.html')

def update_profile():
    if 'user_email' not in session:
        raise exception.MethodNotAllowed()
    
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()

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
    cur.close()
    
    # Update session email if email was changed
    if email:
        session['user_email'] = email
    
    updated_fields_message = ', '.join(updated_fields)
    session['home_message'] = f"You successfully updated your {updated_fields_message}."
    return redirect('/home')

def delete_account():
    if 'user_email' not in session:
        raise exception.MethodNotAllowed("You are not logged in")
    
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    user_email = session['user_email']
    cur = conn.cursor()

    cur.execute("UPDATE users SET verification_status = false WHERE email = %s", (user_email,))
    conn.commit()

    cur.close()
    session.clear()

    return redirect('/login')

def recover_password():
    if request.method != 'POST':
        raise exception.MethodNotAllowed()

    email = request.form['recovery_email']
    new_password = os.urandom(10).hex()

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    is_email_valid = cur.fetchone()['email']

    hashed_password = utils.hash_password(new_password)

    cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))

    conn.commit()
    cur.close()
    conn.close()

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

def resend_verf_code():
    if request.method != 'POST':
        raise exception.MethodNotAllowed()
    
    email = request.form['resend_verf_code']

    new_verification_code = os.urandom(24).hex()

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    # is_present = cur.fetchone().statusmessage is "SELECT 0"

    # assertUser( cur.rowcount == 0, "There is no registration with this email")

    if cur.rowcount == 0:
        raise exception.WrongUserInputVerification('There is no registration with this email')
    
    cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
    is_verified = cur.fetchone()[0]

    if is_verified:
        raise exception.WrongUserInputVerification('The email is already verified')

    cur.execute("UPDATE users SET verification_code = %s WHERE email = %s", (new_verification_code, email))

    conn.commit()
    cur.close()
    conn.close()

    send_verification_email(email, new_verification_code)

    session['verification_message'] = 'A new verification code has been sent to your email.'
    return redirect('/verify')

def send_login_link():
    if request.method != 'POST':
        raise exception.MethodNotAllowed()
    
    email = request.form['resend_verf_code']
    
    login_token = os.urandom(24).hex()

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    if cur.rowcount == 0:
        raise exception.WrongUserInputVerification('There is no registration with this email')
    
    expiration_time = datetime.now() + timedelta(hours=1)

    cur.execute("INSERT INTO tokens(login_token, expiration) VALUES (%s, %s)", (login_token, expiration_time))
    conn.commit()
    cur.execute("SELECT id FROM tokens WHERE login_token = %s", (login_token,))
    token_id = cur.fetchone()[0]
    cur.execute("UPDATE users SET token_id = %s WHERE email = %s", (token_id, email))

    conn.commit()
    cur.close()
    conn.close()

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

def login_with_token():

    if request.method != 'GET':
        raise exception.MethodNotAllowed()
    
    token = request.args.get('token')

    if not token:
        session['registration_error'] = 'Invalid login token'
        return redirect('/registration')
    
    db_name = config.database
    db_user = config.user
    db_password = config.password
    db_host = config.host

    conn = psycopg2.connect(dbname=db_name, user=db_user, password=db_password, host=db_host)
    cur = conn.cursor()

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
    cur.close()
    conn.close()

    session['user_email'] = email   
    return redirect('/home')

def log_exception(exception_type, message ,email = None):
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()

    cur.execute("INSERT INTO exception_logs (user_email, exception_type, message) VALUES (%s, %s, %s)", (email, exception_type, message))
    conn.commit()
    cur.close()
    conn.close()

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
}

@app.endpoint("handle_request")
def handle_request(**kwargs):
    try:
        try:
            request_path = request.path
            funtion_to_call = url_to_function_map.get(request_path)
            if funtion_to_call:
                return funtion_to_call()
            else:
                exception.MethodNotAllowed("Wrong url address")
        except Exception as message:
            user_email = session.get('user_email', 'Guest')
            log_exception(message.__class__.__name__, str(message), user_email)

            redirect_url = getattr(message, 'redirect_url')
            return render_template("error.html", message = str(message), redirect_url = redirect_url)
    except Exception as e:
        return render_template("method_not_allowed.html")

if __name__ == '__main__':
    # app.run(debug=True)
    app.run(debug=True)
    # assert(x == "goodbye", "x should be 'hello'")
    # flask run --host=0.0.0.0 --port=5000