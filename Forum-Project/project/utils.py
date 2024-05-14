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

def getUserNamesAndEmail(conn, cur):
    cur.execute("SELECT first_name, last_name, email FROM users WHERE email = %s", (session.get('user_email'),))
    return cur.fetchone()

def AssertDev(boolean, str):
    if not boolean: raise exception.DevException(str)

def AssertUser(boolean, str):
    if not boolean: raise exception.WrongUserInputException(str)

def has_permission(cur, request,interface, permission_needed):
    role = request.path.split('/')[1]
    cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (role,))
    role_id = cur.fetchone()[0]
    cur.execute("SELECT permission_name FROM permissions AS p JOIN role_permissions AS rp ON p.permission_id=rp.permission_id JOIN roles AS r ON rp.role_id=r.role_id WHERE r.role_id = %s and p.interface = %s", (role_id, interface))
    permissions = cur.fetchall()
    return any(permission_needed in permission for permission in permissions)
