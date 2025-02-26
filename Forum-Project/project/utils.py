from flask import session, request
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

def add_recovery_data_in_session(recovery_data):
    if 'recovery_data_stack' not in session:
        session['recovery_data_stack'] = []
    session['recovery_data_stack'].append(recovery_data)
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

def AssertPeer(boolean, str):
    if not boolean: raise exception.PeerException(str)

def trace(str):
    print(str, flush=True)

def has_permission(cur, request, interface, permission_needed, username):
    # username = request.path.split('/')[1]
    cur.execute("select permission_name, interface from permissions as p join role_permissions as rp on p.permission_id = rp.permission_id join roles as r on rp.role_id = r.role_id join staff_roles as sr on r.role_id = sr.role_id join staff as s on sr.staff_id = s.id where s.username = %s", (username,))
    permission_interface = cur.fetchall()
    for perm_interf in permission_interface:
        if permission_needed == perm_interf[0] and interface == perm_interf[1]:
            return True
    return False

def serialize_report(report):
    json_ready_report = []
    for row in report:
        date_str = row[2].strftime('%Y-%m-%d') if isinstance(row[2], date) else row[2]
        json_row = [
            date_str,
            row[0] if not isinstance(row[0], int) else int(row[0]), 
            row[1] if not isinstance(row[1], int) else int(row[1]),
            float(row[5]),
            float(row[6]) if row[6] is not None else 1,
            float(row[7]) if row[7] is not None else 1,
            row[3],
            row[4],
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
            WHERE o.order_date >= '2023-01-01 21:00:00' AND o.order_date <= '2025-01-01 00:00:00'
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

def check_request_arg_fields(cur, request):

    valid_sort_columns = {'id', 'date', 'first_name', 'last_name', 'email', 'name', 'price', 'quantity', 'category'}
    valid_sort_orders = {'asc', 'desc'}

    parameters = {
        'sort_by': (request.args.get('sort', 'id'), str),
        'sort_order': (request.args.get('order', 'desc'), str),
        'price_min': (request.args.get('price_min', '', type=float), float),
        'price_max': (request.args.get('price_max', '', type=float), float),
        'order_by_id': (request.args.get('order_by_id', '', type=int), int),
        'date_from': (request.args.get('date_from', ''), datetime),
        'date_to': (request.args.get('date_to', ''), datetime),
        'status': (request.args.get('status', ''), str),
        'email': (request.args.get('email','', type=str), str),
        'name': (request.args.get('name','', type=str), str),
        'user_by_id': (request.args.get('user_by_id', '', type=int), int),
        'page': (request.args.get('page', 1, type=int), int),
        'per_page': (request.args.get('per_page', 10, type=int), int),
        'product_name': (request.args.get('product_name', '', type=str), str),
        'product_category': (request.args.get('product_category', '', type=str), str),
        'products_per_page': (request.args.get('products_per_page', 10, type=int), int),
        # 'offset': (page - 1) * per_page
    }

    if parameters['sort_by'][0] not in valid_sort_columns or parameters['sort_order'][0] not in valid_sort_orders:
        sort_by = 'id'
        sort_order = 'asc'

    if len(request.path.split("/")) > 2:
        parameters['page_front_office'] = ((request.path.split("/")[2]), int)

    validated_params = {}

    for key, (value, expected_type) in parameters.items():

        if value is None or value == '':
             validated_params[key] = value
        else:
            try:
                if expected_type is datetime:
                    validated_params[key] = datetime.strptime(value, '%Y-%m-%dT%H:%M')
                else:
                    validated_params[key] = expected_type(value)
            except:
                AssertUser(False, f"Invalid value for {key}. Expected type {expected_type.__name__}.")

    validated_params['offset'] = (validated_params['page'] - 1) * validated_params['per_page']

    if validated_params.get('page_front_office') is not None:
        validated_params['offset_front_office'] = (validated_params['page_front_office'] - 1) * validated_params['per_page']
    else:
        pass

    return validated_params

def check_request_form_fields(request):
    # TODO da vidq greshkata i da viq request tochno
    parameters = {
        'first_name': (request.form['first_name'], str),
        'last_name': (request.form['last_name'],str),
        'email': (request.form['email'], str),
        'password': (request.form['password'],str),
        'address': (request.form['address'], str),
        'phone': (request.form['phone'], int),
        'country_code': (request.form['country_code'], str),
        'gender': (request.form['gender'],str),
    }

    validated_params = {}

    for key, (value, expected_value) in parameters.items():

        if value == '':
            validated_params[key] = value
        else:
            try:
                validated_params[key] = expected_value(value)
            except:
                AssertUser(False, f"Invalid value for {key}. Expected type {expected_value.__name__}.")

    return validated_params

def check_request_form_fields_post_method(path, needed_fields, form_data):

    if path not in needed_fields:
        pass
    else:
        # Get the required fields and their constraints for the path
        fields_constraints = needed_fields[path]

        # Iterate over each field and its constraints
        for field_name, constraints in fields_constraints.items():

            field_value = form_data.get(field_name)

            # Check if the field is required and is missing
            is_field_required = constraints.get('required')

            if is_field_required:
                AssertUser(field_value, f"{field_name} is required.")
            else:
                pass

            # Check the type of the field
            try:
                constraint_type = constraints['type']
                field_value_converted = constraint_type(field_value)
            except:
                AssertUser(False, f"Invalid value for {field_name}. Expected type {field_name.__name__}.")

            # Check custom conditions for length or regex
            if 'conditions' in constraints:
                for condition, error_message in constraints['conditions']:
                    AssertUser(condition(field_value), error_message)
