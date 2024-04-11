from flask import session
import bcrypt
import psycopg2
from project import config

database = config.database
user = config.user
password = config.password
host = config.host

def add_form_data_in_session(form_data):
    if 'form_data_stack' not in session:
        session['form_data_stack'] = []
    session['form_data_stack'].append(form_data)
    session.modified = True

def hash_password(password):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_password.decode('utf-8')

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def is_authenticated():
    return 'user_email' in session

def getDBConn():
    conn = psycopg2.connect(dbname=database, user=user, password=password, host=host)
    cur = conn.cursor()
    return conn, cur

def get_captcha_setting_by_name(setting_name):
    conn, cur = getDBConn()
    cur.execute("SELECT value FROM captcha_settings WHERE name = %s", (setting_name, ))
    value_to_return = cur.fetchone()[0]
    conn.close()
    cur.close()
    return value_to_return

def get_current_settings():
    conn, cur = getDBConn()
    cur.execute("SELECT name, value FROM captcha_settings ")
    settings = {name: value for name, value in cur.fetchall()}
    conn.close()
    return settings