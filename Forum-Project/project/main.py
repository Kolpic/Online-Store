from flask import Flask, request, render_template, redirect, url_for, session
from flask_mail import Mail, Message
import psycopg2, os, re, secrets, bcrypt
# import os
from project import config
from project import exception
# import re
# import secrets
# import bcrypt

# https://stackoverflow.com/questions/23327293/flask-raises-templatenotfound-error-even-though-template-file-exists

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USE_SSL'] = config.MAIL_USE_SSL

mail = Mail(app)

database = config.test_database
user = config.user
password = config.password
host = config.host

@app.route('/registration', methods =['GET', 'POST'])
def registration():

    if request.method == 'GET':
        return render_template('registration.html')
    
    if request.method == 'POST':
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password_ = request.form['password']

        hashed_password = hash_password(password_)
        verification_code = os.urandom(24).hex()
        try:
            if len(first_name) < 3 or len(first_name) > 50:
                raise exception.CustomError('First name is must be between 3 and 50 symbols')
            if len(last_name) < 3 or len(last_name) > 50:
                raise exception.CustomError('Last name must be between 3 and 50 symbols')
            
            regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

            if not (re.fullmatch(regex, email)):
                raise exception.CustomError('Email is not valid')
        except exception.CustomError as e:
            session['registration_error'] = str(e)
            return redirect(url_for('registration'))

        cur = conn.cursor()
        cur.execute("INSERT INTO users (first_name, last_name, email, password, verification_code) VALUES (%s, %s, %s, %s, %s)", (first_name, last_name, email, hashed_password, verification_code))
        conn.commit()
        cur.close()

        send_verification_email(email, verification_code)

        return redirect(url_for('verify'))

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

@app.route('/verify', methods=['POST', 'GET'])
def verify():

    if request.method == 'GET':
        return render_template('verify.html')

    if request.method == 'POST':
        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

        email = request.form['email']
        verification_code = request.form['verification_code']

        cur = conn.cursor()

        cur.execute("SELECT email FROM users WHERE email = %s", (email,))
        
        dictionary = {}

        try:
            # cur.fetchone()[0]
            # email_from_database 
            email_from_database = cur.fetchone()[0]   
            if email_from_database == email:
                cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", (verification_code,))
                conn.commit()
                cur.close()
                return redirect(url_for('login'))
        except TypeError as e:
            error_message = 'You entered different email'
            session['verification_error'] = str(error_message)
            return redirect(url_for('verify'))    

@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    if request.method == 'GET':
        return render_template('login.html')

    if request.method == 'POST':

        conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

        email = request.form['email']
        password_ = request.form['password']

        cur = conn.cursor()

        cur.execute("SELECT verification_status FROM users WHERE email = %s", (email,))
        is_the_email_verified = cur.fetchone()[0]

        cur.execute("SELECT password FROM users WHERE email = %s", (email,))
        hashed_password = cur.fetchone()[0]

        are_passwords_same = bool(verify_password(password_, hashed_password))

        flag = False
        if not are_passwords_same:
            error_message = 'Invalid email or password'
            flag = True

        if not is_the_email_verified:
            error_message = 'Your account is not verified or has been deleted'
            flag = True

        if flag:
            session['login_error'] = str(error_message)
            return redirect(url_for('login')) 
        
        session['user_email'] = email   
        return redirect(url_for('home'))


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def is_authenticated():
    return 'user_email' in session

@app.route('/home', methods=['GET'])
def home():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    return render_template('home.html')

@app.route('/logout', methods=['GET'])    
def logout():
    session.pop('user_email', None) 
    return redirect(url_for('home'))

@app.route('/settings')
def settings():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    return render_template('settings.html')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user_email' not in session:
         return 'Unauthorized', 401
    
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    first_name = request.form['first-name']
    last_name = request.form['last-name']
    email = request.form['email']
    password_ = request.form['password']

    cur = conn.cursor()
        
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

@app.route('/delete_account', methods=['POST', 'GET'])
def delete_account():

    if 'user_email' not in session:
        return redirect(url_for('registration'))
    
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)

    user_email = session['user_email']
    cur = conn.cursor()

    cur.execute("UPDATE users SET verification_status = false WHERE email = %s", (user_email,))
    conn.commit()

    cur.close()
    session.clear()

    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

