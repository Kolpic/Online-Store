from flask import session
import bcrypt, json
import psycopg2
from project import config, exception
from datetime import date
import pandas as pd
import random
from datetime import datetime, timedelta
from psycopg2.extensions import adapt, register_adapter, AsIs

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

def getUserNamesAndEmail(conn, cur, email):
    cur.execute("SELECT first_name, last_name, email FROM users WHERE email = %s", (email,)) # session.get('user_email')
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

def fetch_verified_users(cur):
    cur.execute("SELECT id FROM users WHERE verification_status = True")
    users = cur.fetchall()
    return [user[0] for user in users]

def read_products_from_csv():
    return pd.read_csv('/home/galin/Desktop/projects/GitHub/Forum-Project/large_products.csv')

def random_datetime(start_date, end_date):
    delta = end_date - start_date
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start_date + timedelta(seconds=random_second)

def fetch_products_from_db(cur):
    cur.execute("SELECT id, price FROM products")
    products = cur.fetchall()
    return [{'id': product[0], 'price': product[1]} for product in products]

def create_random_orders(number_orders, cur, conn):

    verified_users = fetch_verified_users(cur)
    start_date = datetime(1950, 1, 1)
    end_date = datetime.now()
    statuses = ['Ready for Paying', 'Paid']
    products = fetch_products_from_db(cur)

    counter = 0

    for _ in range(number_orders):

        if counter == 100000:
            print("Successfully imported 100 000 products", flush=True)
            conn.commit()
            counter = 0

        user_id = random.choice(verified_users)
        num_products = random.randint(1, 5)
        order_date = random_datetime(start_date, end_date)
        order_status = random.choice(statuses)

        cur.execute("INSERT INTO orders (user_id, status, order_date) VALUES (%s, %s, %s) RETURNING order_id", (user_id, order_status, order_date))
        order_id = cur.fetchone()[0]

        for _ in range(num_products):
            product = random.choice(products)
            quantity = random.randint(1, 3)
            price = product['price']

            cur.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)", (order_id, product['id'], quantity, price))

        counter = counter + 1

def fetch_batches(conn, date_from, date_to, offset, batch_size=10000):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:

        CURSOR_NAME = 'batch_cursor'
        
        #TODO: rename as
        query = f"""
            DECLARE {CURSOR_NAME} CURSOR FOR
            SELECT 
                    DATE(date_trunc('second', o.order_date)) AS date, 
                    o.order_id, 
                    o.status, 
                    u.first_name, 
                    SUM(oi.quantity * oi.price)              AS total_price
            FROM orders AS o
            JOIN users       AS u  ON o.user_id  = u.id
            JOIN order_items AS oi ON o.order_id = oi.order_id
            WHERE o.order_date >= '1950-01-01 21:00:00' AND o.order_date <= '2024-01-01 00:00:00'
            GROUP BY 
                    date,
                    o.order_id,
                    u.first_name,
                    u.last_name,
                    oi.quantity,
                    oi.price
            ORDER BY o.order_date;
        """

        cur.execute(query)
        fetch_query = f"FETCH {batch_size} FROM {CURSOR_NAME}"

        while True:

            cur.execute(fetch_query)
            rows = cur.fetchall()

            if not rows:
                print("No more rows to fetch, breaking loop...", flush=True)
                break
            yield rows

        cur.execute(f"CLOSE {CURSOR_NAME}")

def batch_insert_import_csv(cursor, data, os, batch_size=100):
    batch = []

    for row in data:
        row_currency = row[5]

        cursor.execute("SELECT id FROM currencies WHERE symbol = %s", ([row_currency]))
        row_currency_id = cursor.fetchone()[0]

        row[5] = row_currency_id

        image_filename = row[4]

        image_path = os.path.join(os.path.dirname("/home/galin/Desktop/projects/GitHub/Forum-Project/images/"), image_filename)

        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()

            row[4] = image_data

        batch.append(row)

        if len(batch) >= batch_size:
            cursor.executemany("INSERT INTO products (name, price, quantity, category, image, currency_id) VALUES (%s, %s, %s, %s, %s, %s)", batch)
            batch = [] 
    if batch:
        cursor.executemany("INSERT INTO products (name, price, quantity, category, image, currency_id) VALUES (%s, %s, %s, %s, %s, %s)", batch)

def adapt_datetime(dt):
    return AsIs("'" + dt.strftime('%Y-%m-%dT%H:%M:%S') + "'")

register_adapter(datetime, adapt_datetime)

def check_request_arg_fields(cur, request, datetime):

    valid_sort_columns = {'id', 'date', 'first_name', 'last_name', 'email'}
    valid_sort_orders = {'asc', 'desc'}

    # SQL adaptation protocol objects
    sort_by = request.args.get('sort', 'id')
    sort_order = request.args.get('order', 'desc')
    price_min = request.args.get('price_min', '', type=float)
    price_max = request.args.get('price_max', '', type=float)
    order_by_id = request.args.get('order_by_id', '', type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    status = request.args.get('status', '')
    email = request.args.get('email','', type=str)
    user_by_id = request.args.get('user_by_id', '', type=int)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    offset = (page - 1) * per_page

    if sort_by not in valid_sort_columns or sort_order not in valid_sort_orders:
        sort_by = 'id'
        sort_order = 'asc'

    if price_min:
        try:
            price_min = float(price_min)
        except:
            utils.AssertUser(False, "Entered min price is not a number")

    if price_max:
        try:
            price_max = float(price_max)
        except:
            utils.AssertUser(False, "Entered max price is not a number")

    if order_by_id:
        try:
            order_by_id = int(order_by_id)
        except:
            utils.AssertUser(False, "Entered order by id is not a number")

    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%dT%H:%M')
        except:
            utils.AssertUser(False, "Entered date_from is not a date")

    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%dT%H:%M')
        except:
            utils.AssertUser(False, "Entered date_to is not a date")

    if email:
        AssertUser('@' in email, "Not valid email")

    if user_by_id:
        try:
            user_by_id = int(user_by_id)
        except:
            utils.AssertUser(False, "Entered user by id is not a number")

    return {'sort_by': sort_by,
            'sort_order': sort_order, 
            'price_min': price_min, 
            'price_max': price_max, 
            'order_by_id': order_by_id, 
            'date_from': date_from, 
            'date_to': date_to, 
            'status': status, 
            'page': page, 
            'per_page': per_page, 
            'offset': offset,
            'email': email, 
            'user_by_id': user_by_id}