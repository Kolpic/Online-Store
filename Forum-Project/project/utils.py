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

def get_captcha_setting_by_name(cur, setting_name):
    cur.execute("SELECT value FROM captcha_settings WHERE name = %s", (setting_name, ))
    value_to_return = cur.fetchone()[0]
    return value_to_return

def get_current_settings(cur):
    cur.execute("SELECT name, value FROM captcha_settings ")
    settings = {name: value for name, value in cur.fetchall()}
    return settings

def Assert(*args):
    boolean = args[0]
    string = str(args[1])

    if boolean is None and string == "Invalid url address": raise exception.WrongUserInputException(string)
    if not callable(boolean) and string == "You are trying to invoke something that is not function !!!": raise exception.DevException(string)
    if boolean and string == "Password and Confirm Password fields are different": raise exception.WrongUserInputException(string)
    if boolean and string == "You typed wrong captcha several times, now you have timeout": raise exception.WrongUserInputException(string)
    if boolean and string == "First name is must be between 3 and 50 symbols": raise exception.WrongUserInputException(string)
    if boolean and string == "Last name must be between 3 and 50 symbols": raise exception.WrongUserInputException(string)
    if not boolean and string == "Email is not valid": raise exception.WrongUserInputException(string)
    if boolean and string == "There is already registration with this email":  raise exception.WrongUserInputException(string)
    if boolean and string == "Account was already registered and deleted with this email, type another email":  raise exception.WrongUserInputException(string)
    if boolean and string == "You entered different email":  raise exception.WrongUserInputException(string)
    if boolean and string == "The account is already verified":  raise exception.WrongUserInputException(string)
    if boolean and string == "The verification code you typed is different from the one we send you":  raise exception.WrongUserInputException(string)
    if not boolean and string == "Invalid email or password":  raise exception.WrongUserInputException(string)
    if not boolean and string == "Your account is not verified or has been deleted":  raise exception.WrongUserInputException(string)
    if boolean and string == "There is no registration with this email":  raise exception.WrongUserInputException(string)
    if boolean and string == "Captcha attempts must be possitive number":  raise exception.WrongUserInputException(string)
    if boolean and string == "Timeout minutes must be possitive number":  raise exception.WrongUserInputException(string)