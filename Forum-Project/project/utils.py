from flask import session
import bcrypt, json
import psycopg2
from project import config, exception
from datetime import date

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

def has_permission(cur, request, interface, permission_needed):
    username = request.path.split('/')[1]
    cur.execute("select permission_name, interface from permissions as p join role_permissions as rp on p.permission_id = rp.permission_id join roles as r on rp.role_id = r.role_id join staff_roles as sr on r.role_id = sr.role_id join staff as s on sr.staff_id = s.id where s.username = %s", (username,))
    permission_interface = cur.fetchall()
    for perm_interf in permission_interface:
        if permission_needed == perm_interf[0] and interface == perm_interf[1]:
            return True
    return False

def serialize_report(report):
    json_ready_report = []
    for row in report:
        date_str = row[0].strftime('%Y-%m-%d') if isinstance(row[0], date) else row[0]
        json_row = [
            date_str,
            list(row[1]), 
            list(row[2]),
            float(row[3]),
            list(row[4])
        ]
        json_ready_report.append(json_row)
    return json.dumps(json_ready_report)