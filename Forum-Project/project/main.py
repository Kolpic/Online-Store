from flask import Flask, request, render_template, redirect, url_for, session, abort
from flask_mail import Mail, Message
import psycopg2, os, re, secrets, psycopg2.extras, uuid
import bcrypt
# import os
from project import config, exception
from flask_session_captcha import FlaskSessionCaptcha
# from flask_sessionstore import Session
from flask_session import Session
import json 
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
# Captcha Configuration
app.config["SECRET_KEY"] = uuid.uuid4() 
app.config["CAPTCHA_WIDTH"] = 160
app.config["CAPTCHA_HEIGHT"] = 60 
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/home/galin/Desktop/projects/GitHub/Forum-Project/project/captcha'

Session(app)

app.config["CAPTCHA_ENABLE"] = True
app.config["CAPTCHA_NUMERIC_DIGITS"] = 5
captcha = FlaskSessionCaptcha(app)

mail = Mail(app)

database = config.database
user = config.user
password = config.password
host = config.host

app.add_url_rule("/registration", endpoint="registration", methods=['POST', 'GET'])
app.add_url_rule("/", endpoint="registration", methods=['POST', 'GET'])
app.add_url_rule("/verify", endpoint="verify", methods=['POST', 'GET'])
app.add_url_rule("/login", endpoint="login", methods=['POST', 'GET'])  
app.add_url_rule("/home", endpoint="home", methods=['GET'])
app.add_url_rule("/logout", endpoint="logout", methods=['GET'])
app.add_url_rule("/profile", endpoint="profile")
app.add_url_rule("/update_profile", endpoint="update_profile", methods=['POST'])
app.add_url_rule("/delete_account", endpoint="delete_account", methods=['POST','GET'])
app.add_url_rule("/recover_password", endpoint="recover_password", methods=['POST'])
app.add_url_rule("/resend_verf_code", endpoint="resend_verf_code", methods=['POST'])

@app.endpoint("registration")
def registration():
    if request.method != 'GET' and request.method != 'POST':
        raise exception.MethodNotAllowed()

    if request.method == 'GET':
        form_data = session.get('form_data_stack', []).pop() if 'form_data_stack' in session and len(session['form_data_stack']) > 0 else None
        if form_data:
            session.modified = True
        return render_template('registration.html', form_data=form_data)

    form_data = request.form.to_dict()
    captcha_response = request.form['captcha']
    if not captcha.validate():
        add_form_data_in_session(form_data)
        raise exception.WrongUserInputRegistration("Invalid CAPTCHA. Please try again")       

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    password_ = request.form['password']

    hashed_password = hash_password(password_)
    verification_code = os.urandom(24).hex()

    if len(first_name) < 3 or len(first_name) > 50:
        add_form_data_in_session(form_data)
        raise exception.WrongUserInputRegistration('First name is must be between 3 and 50 symbols')
    if len(last_name) < 3 or len(last_name) > 50:
        add_form_data_in_session(form_data)
        raise exception.WrongUserInputRegistration('Last name must be between 3 and 50 symbols')
        
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

    if not (re.fullmatch(regex, email)):
        add_form_data_in_session(form_data)
        raise exception.WrongUserInputRegistration('Email is not valid')

    cur = conn.cursor()
    cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", (first_name, last_name, email, hashed_password, verification_code))
    conn.commit()
    cur.close()

    send_verification_email(email, verification_code)

    return redirect(url_for('verify'))

def add_form_data_in_session(form_data):
    if 'form_data_stack' not in session:
        session['form_data_stack'] = []
    session['form_data_stack'].append(form_data)

def send_verification_email(user_email, verification_code):
    with app.app_context():
        msg = Message('Email Verification',
                sender = 'galincho112@gmail.com',
                recipients = [user_email])
    msg.body = 'Please insert the verification code in the form: ' + verification_code
    mail.send(msg)

def hash_password(password):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_password.decode('utf-8')

@app.endpoint("verify")
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

    if email_from_database != email:
        raise exception.WrongUserInputVerification('You entered different email')
    if is_verified:
        raise exception.WrongUserInputVerification('The account is already verified')
    
    cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", (verification_code,))
    conn.commit()
    cur.close()
    return redirect(url_for('login'))  

@app.endpoint("login")
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

    are_passwords_same = bool(verify_password(password_, hashed_password))

    if not are_passwords_same:
        raise exception.WrongUserInputLogin('Invalid email or password')

    if not is_the_email_verified:
        raise exception.WrongUserInputLogin('Your account is not verified or has been deleted')

    session['user_email'] = email   
    return redirect(url_for('home'))
    
def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def is_authenticated():
    return 'user_email' in session

@app.endpoint("home")
def home():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    return render_template('home.html')

@app.endpoint("logout")    
def logout():
    session.pop('user_email', None) 
    return redirect(url_for('home'))

@app.endpoint("profile")
def profile():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()
    cur.execute("SELECT first_name, last_name, email FROM users WHERE email = %s", (session['user_email'],))
    user_details = cur.fetchone()
    conn.commit()

    if user_details:
        return render_template('profile.html', user_details=user_details)
    
    return render_template('profile.html')

@app.endpoint("update_profile")
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

    if first_name:
        query_string += "first_name = %s, "
        fields_list.append(first_name)
    if last_name:
        query_string += "last_name = %s, "
        fields_list.append(last_name)
    if email:
        query_string += "email = %s, "
        fields_list.append(email)
    if password_:
        query_string += "password = %s, "
        hashed_password = hash_password(password_)
        fields_list.append(hashed_password)

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
    
    return redirect(url_for('home'))

@app.endpoint("delete_account")
def delete_account():
    if 'user_email' not in session:
        raise exception.MethodNotAllowed()
    
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    user_email = session['user_email']
    cur = conn.cursor()

    cur.execute("UPDATE users SET verification_status = false WHERE email = %s", (user_email,))
    conn.commit()

    cur.close()
    session.clear()

    return redirect(url_for('login'))

@app.endpoint("recover_password")
def recover_password():
    if request.method != 'POST':
        raise exception.MethodNotAllowed()

    email = request.form['recovery_email']
    new_password = os.urandom(10).hex()

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    is_email_valid = cur.fetchone()['email']

    hashed_password = hash_password(new_password)

    cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))

    conn.commit()
    cur.close()
    conn.close()

    send_recovey_password_email(email, new_password)
    
    session['login_message'] = 'A recovery password has been sent to your email.'
    return redirect(url_for('login'))

def send_recovey_password_email(user_email, recovery_password):
    with app.app_context():
        msg = Message('Recovery password',
                sender = 'galincho112@gmail.com',
                recipients = [user_email])
    msg.body = 'Your recovery password: ' + recovery_password
    mail.send(msg)

@app.endpoint("resend_verf_code")
def resend_verf_code():
    if request.method != 'POST':
        raise exception.MethodNotAllowed()
    
    email = request.form['resend_verf_code']

    new_verification_code = os.urandom(24).hex()

    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()

    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    # is_present = cur.fetchone().statusmessage is "SELECT 0"

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
    return redirect(url_for('verify'))
    
if __name__ == '__main__':
    # app.run(debug=True)
    app.run(debug=True)
    # flask run --host=0.0.0.0 --port=5000