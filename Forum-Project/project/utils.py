from flask import session
import bcrypt
import psycopg2
from project import config, exception

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

def assertUser(boolean):
    if boolean is None: raise exception.WrongUserInputException("Invalid url address")
    if boolean and str(boolean) == "password_ != confirm_password_": raise exception.WrongUserInputException("Password and Confirm Password fields are different")

def assertDev(boolean):
    if not callable(boolean): raise exception.DevException("You are trying to invoke something that is not function !!!")
    # if not boolean: raise exception.DevException("Invalid url address")

def Assert(*args):
    boolean = args[0]
    string = str(args[1])

    if boolean is None and string == "Invalid url address": raise exception.WrongUserInputException(string)
    if not callable(boolean) and string == "You are trying to invoke something that is not function !!!": raise exception.DevException(string)
    if boolean and string == "Password and Confirm Password fields are different": raise exception.WrongUserInputException(string)
    if boolean and string == "You typed wrong captcha several times, now you have timeout": raise exception.WrongUserInputException(string)
    if boolean and string == "First name is must be between 3 and 50 symbols": raise exception.WrongUserInputException(string)
    if boolean and string == "Last name must be between 3 and 50 symbols": raise exception.WrongUserInputException(string)
    if boolean and string == "Email is not valid": raise exception.WrongUserInputException(string)
    
    # if not len(args) > 1:
    #     return    
    # string = getattr(str(args[1]))
    # if boolean and str(string) == "Password and Confirm Password fields are different": raise exception.WrongUserInputException("Password and Confirm Password fields are different")