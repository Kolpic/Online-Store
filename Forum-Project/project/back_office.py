import os, re
import psycopg2
import csv
import io

from decimal import Decimal
from datetime import timedelta, datetime

from project import cache_impl, sessions
from project import sessions
from project import utils
from project import helper
from project import config

def staff_login(cur, username, password):
	cur.execute("SELECT * FROM staff WHERE username = %s AND password = %s", (username, password))
	staff_row = cur.fetchone()
	utils.AssertUser(staff_row is not None, "There is no registration with this staff username and password")

	data_to_return = {
		'username': staff_row['username']
	}

	return data_to_return

def prepare_error_logs_data(cur, sort_by, sort_order):

	query = "SELECT * FROM exception_logs"

	if sort_by and sort_order:
		query += f" ORDER BY {sort_by} {sort_order}"

	cur.execute(query)
	log_exceptions = cur.fetchall()

	utils.AssertDev(len(log_exceptions) <= 100000, "Too much fetched values from db /error_logs")

	data_to_return = {
		'log exceptions': log_exceptions
	}

	return data_to_return

def prepare_settings_data(cur):

	cur.execute("SELECT * FROM settings")
	settings_row = cur.fetchone()

	limitation_rows = settings_row['report_limitation_rows']
	vat = settings_row['vat']
	background_color = settings_row['send_email_template_background_color']
	text_align = settings_row['send_email_template_text_align']
	border = settings_row['send_email_template_border']
	border_collapse = settings_row['send_email_template_border_collapse']

	data_to_return = {
		'limitation_rows': limitation_rows,
		'vat': vat,
		'background_color': background_color,
		'text_align': text_align,
		'border': border,
		'border_collapse': border_collapse,
	}

	return data_to_return

def captcha_settings(cur, new_max_attempts, new_timeout_minutes):

	utils.AssertUser(not(new_max_attempts and int(new_max_attempts)) <= 0, "Captcha attempts must be possitive number")
	utils.AssertUser(not(new_timeout_minutes and int(new_timeout_minutes)) <= 0, "Timeout minutes must be possitive number")

	str_message = ""

	if new_max_attempts:
	    cur.execute("UPDATE captcha_settings SET value = %s WHERE name = 'max_captcha_attempts'", (new_max_attempts,))
	    str_message += 'You updated captcha attempts. '
	if new_timeout_minutes:
	    cur.execute("UPDATE captcha_settings SET value = %s WHERE name = 'captcha_timeout_minutes'", (new_timeout_minutes,))
	    str_message += 'You updated timeout minutes.'

	data_to_return = {
		'message': str_message,
	}

	return data_to_return

def post_update_limitation_rows(cur, limitation_rows):

	utils.AssertUser(limitation_rows >= 0 and limitation_rows <= 50000, "You can't enter zero or negative number. The maximum number is 50000")

	query = ("UPDATE settings SET report_limitation_rows = %s")
	cur.execute(query, (limitation_rows,))

	message = "You changed the limitation number of every report to: " + str(limitation_rows)

	data_to_return = {
		'message': message,
	}

	return data_to_return

def vat_for_all_products(cur, vat_for_all_products):

	try:
	    vat_for_all_products = int(vat_for_all_products)
	except:
	    utils.AssertUser(False,"Enter a number !!!, Without the '%' sign")

	cur.execute("UPDATE settings SET vat = %s", (vat_for_all_products,))

	message = "You changed the VAT for all products successfully"

	data_to_return = {
		'message': message,
	}

	return data_to_return

def report_sales(cur, date_from, date_to, group_by, status, filter_by_status, order_id, page):

	cur.execute("SELECT * FROM settings")
	settings_rows = cur.fetchone()
	limitation_rows = settings_rows['report_limitation_rows']

	per_page = 1000  

	utils.AssertUser(date_from or date_to, "You have to select date from and date to")

	params = []

	query = "SELECT "

	if group_by == '':
	    query += "users.id, orders.order_id, to_char(orders.order_date, 'YYYY-MM-DD HH24:MI:SS') AS order_date, users.first_name, "
	else:
	    query += f"'-' AS id, '-' AS order_id, date_trunc('{group_by}', order_date) AS order_date, '-' AS first_name, "

	if status == '' and group_by == '':
	    query += "orders.status, "
	elif status == '' and group_by != '':
	    query += "'-' as status, "
	elif status != '' and group_by != '':
	    query += "orders.status, "

	query += "sum(order_items.price * order_items.quantity) As total, "
	query += "round(sum(order_items.price * order_items.quantity * (CAST(order_items.vat as numeric) / 100)),2) as vat, "
	query += "round(sum(order_items.price * order_items.quantity) + sum(order_items.price * order_items.quantity * (cast(order_items.vat as numeric) / 100)),2) as total_with_vat "

	query += """
	        FROM orders 
	        JOIN order_items ON orders.order_id = order_items.order_id
	        JOIN users       ON users.id        = orders.user_id
	        WHERE order_date >= %s AND order_date <= %s 
	"""

	params.append(date_from)
	params.append(date_to)

	if filter_by_status:
	    query += "AND orders.status = %s "
	    params.append(filter_by_status)

	if order_id:
	    query += "AND orders.order_id = %s "
	    params.append(order_id)

	query += "GROUP BY 1, 2, 3, 4, 5 ORDER BY order_date DESC LIMIT %s"

	query_for_total_rows = query[:len(query)-8]
	cur.execute(query_for_total_rows, params)
	total_records = len(cur.fetchall())

	params.append(limitation_rows)

	cur.execute(query, params)

	report = cur.fetchall()
	utils.trace(report)

	utils.AssertUser(len(report) != 0, "No result with this filter")

	# total_records = len(report)

	total_price = sum(row[5] for row in report)
	total_vat = sum(row[6] for row in report if row[6] is not None)
	total_price_with_vat = sum(row[7] for row in report if row[7] is not None)

	report_json = utils.serialize_report(report)

	data_to_return = {
		'limitation_rows': int(limitation_rows),
		'filter_by_status': filter_by_status,
		'report': report,
		'total_records': total_records,
		'total_price_with_vat': total_price_with_vat,
		'total_vat': total_vat,
		'total_price': total_price,
		'report_json': report_json,
		'default_to_date': date_to,
		'default_from_date': date_from, 
	}

	return data_to_return

def prepare_crud_products_data(cur, sort_by, sort_order, price_min, price_max):
	base_query = """

                SELECT 
                    products.id, 
                    products.name, 
                    products.price, 
                    products.quantity, 
                    products.category, 
                    currencies.symbol,
                    settings.vat,
                    products.price + (products.price * (CAST(settings.vat AS numeric) / 100)) AS product_vat_price
                FROM products 
                    JOIN currencies ON products.currency_id = currencies.id
                    JOIN settings   ON products.vat_id      = settings.id
                WHERE 1=1

           		"""
	query_params = []

	if price_min is not '' and price_max is not '':
	    base_query += " AND products.price + (products.price * (CAST(settings.vat AS numeric) / 100)) BETWEEN %s AND %s"
	    query_params.extend([price_min, price_max])

	base_query += f"ORDER BY {sort_by} {sort_order} LIMIT 100"

	cur.execute(base_query, query_params)
	products = cur.fetchall()

	data_to_return = {
		'products': products,
	}

	return data_to_return

def prepare_crud_add_product_data(cur):

	cur.execute("SELECT symbol, id FROM currencies")
	all_currencies = cur.fetchall()


	cur.execute("SELECT DISTINCT(category) FROM products")
	categories = [row[0] for row in cur.fetchall()]  # Extract categories from tuples

	data_to_return = {
		'all_currencies': all_currencies,
		'categories': categories,
	}

	return data_to_return

def crud_add_product(cur, form_data, files_data):

	data = helper.process_form('CRUD Products', 'create', form_data, files_data)

	cur.execute(f"INSERT INTO products ({ data['fields'] }) VALUES ({ data['placeholders'] }) RETURNING *", data['values'])
	new_item_row = cur.fetchone()

	data_to_return = {
		'message': "Item was added successfully",
		'new_item_row': new_item_row,
	}

	return data_to_return

def prepare_edit_product_data(cur, product_id):

	cur.execute("SELECT symbol, id FROM currencies")
	all_currencies = cur.fetchall()

	cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
	product = cur.fetchone()

	utils.AssertUser(product, "Invalid product")

	data_to_return = {
		'product': product,
		'all_currencies': all_currencies,
	}

	return data_to_return

def edit_product(cur, form_data, files_data, product_id):

	data = helper.process_form('CRUD Products', 'edit', form_data, files_data)

	cur.execute("UPDATE products SET name = %s, price = %s, quantity = %s, category = %s, currency_id = %s WHERE id = %s", (data['values'][0], data['values'][1], data['values'][2], data['values'][3], data['values'][4],product_id))

	data_to_return = {
		'message': "Product was updated successfully with id = " + str(product_id)
	}

	return data_to_return

def delete_product(cur, product_id):

    cur.execute("UPDATE products SET quantity = 0 WHERE id = %s", (product_id,))

    data_to_return = {
    	'message': "Product was set to be unavailable successful with id = " + str(product_id),
    }

    return data_to_return

def prepare_crud_staff_data(cur):

	cur.execute("""

				SELECT 
					staff.username, 
					roles.role_name,
					staff_roles.staff_id, 
					staff_roles.role_id 
				FROM staff_roles 
					JOIN staff  ON staff.id      = staff_roles.staff_id 
					JOIN roles  ON roles.role_id = staff_roles.role_id

				""")
	relations = cur.fetchall()

	data_to_return = {
	'relations': relations,
	}

	return data_to_return

def prepare_add_role_staff_data(cur):

	cur.execute("SELECT id, username FROM staff")
	staff = cur.fetchall()

	cur.execute("SELECT role_id, role_name FROM roles")
	roles = cur.fetchall()

	data_to_return = {
		'staff': staff,
		'roles': roles, 
	}

	return data_to_return

def add_role_staff(cur, form_data, files_data):

	data = helper.process_form('Staff roles', 'create_staff_roles', form_data, files_data)

	cur.execute("SELECT id FROM staff WHERE username = %s", (data['values'][0],))
	staff_id = cur.fetchone()[0]

	cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (data['values'][1],))
	role_id = cur.fetchone()[0]

	cur.execute(f"INSERT INTO staff_roles ({data['fields']}) VALUES ({data['placeholders']})", (staff_id, role_id))

	message = "You successful gave a role: " + str(data['values'][1]) + " to user: " + str(data['values'][0])

	data_to_return = {
		'message': message,
	}

	return data_to_return

def add_staff(cur, form_data, files_data):

	data = helper.process_form('Staff roles', 'create_staff', form_data, files_data)

	cur.execute(f"INSERT INTO staff ({data['fields']}) VALUES ({data['placeholders']})", (data['values']))

	message = "You successful made new user with name: " + str(data['values'][0])

	data_to_return = {
		'message': message,
	}

	return data_to_return

def delete_crud_staff_role(cur, staff_id, role_id):

	cur.execute('DELETE FROM staff_roles WHERE staff_id = %s AND role_id = %s', (staff_id, role_id))

	message = "You successful deleted a role"

	data_to_return = {
		'message': message
	}

	return data_to_return

def prepare_crud_orders_data(cur, sort_by, sort_order, price_min, price_max, order_by_id, date_from, date_to, status, page, per_page, offset):

	cur.execute("SELECT DISTINCT status FROM orders")
	statuses = cur.fetchall()

	query = """
		SELECT 
			o.order_id, 
			u.first_name || ' ' || u.last_name                    AS user_names, 
			array_agg(p.name)                                     AS product_names,
			to_char(sum(oi.quantity * oi.price),'FM999999990.00') AS order_price, 
			o.status, 
			to_char(o.order_date, 'MM-DD-YYYY HH:MI:SS')          AS formatted_order_date,
			c.symbol,
			oi.vat
		FROM orders      AS o 
		JOIN users       AS u  ON o.user_id     = u.id 
		JOIN order_items AS oi ON o.order_id    = oi.order_id 
		JOIN products    AS p  ON oi.product_id = p.id
		JOIN currencies  AS c  ON p.currency_id = c.id
		WHERE 1=1
	"""

	params = []

	if order_by_id:
		query += " AND o.order_id = %s"
		params.append(order_by_id)

	if date_from and date_to:
		query += " AND o.order_date >= %s AND o.order_date <= %s"
		params.extend([date_from, date_to])

		query_cus = "SELECT count(*) FROM orders WHERE orders.order_date >= %s AND orders.order_date <= %s"

		cur.execute(query_cus, (date_from, date_to))
		total_length_query = cur.fetchone()[0]
	else:
		default_to_date = datetime.now()
		dafault_from_date = default_to_date - timedelta(days=7)

		query += " AND o.order_date >= %s AND o.order_date <= %s"
		params.extend([dafault_from_date, default_to_date])

		query_cus = "SELECT count(*) FROM orders WHERE orders.order_date >= %s AND orders.order_date <= %s"

		cur.execute(query_cus, (dafault_from_date, default_to_date))
		total_length_query = cur.fetchone()[0]

		utils.trace("total_length_query")
		utils.trace(total_length_query)

	if status:
		query += " AND o.status = %s"
		params.append(status)

	# AND products.price + (products.price * (CAST(settings.value AS numeric) / 100)) BETWEEN %s AND %s"
	if price_min and price_max:
		query += """
					GROUP BY 
					o.order_id, 
					user_names, 
					c.symbol, 
					oi.vat 
					HAVING sum((oi.quantity * oi.price) + ((oi.quantity * oi.price) * (CAST(oi.vat AS numeric) / 100))) >= %s AND sum((oi.quantity * oi.price) + ((oi.quantity * oi.price) * (CAST(oi.vat AS numeric) / 100))) <= %s
				"""
		params.extend([price_min, price_max])

	if price_min == '' and price_max == '':
		query += " GROUP BY o.order_id, user_names, c.symbol, oi.vat "

	query += f" ORDER BY o.order_{sort_by} {sort_order} "

	query += "LIMIT %s OFFSET %s"
	params.extend([per_page, offset])

	cur.execute(query, params)
	orders = cur.fetchall()

	loaded_orders = len(orders)

	data_to_return = {
	'page': page,
	'total_pages': total_length_query // per_page,
	'orders': orders,
	'statuses': statuses,
	'current_status': status,
	'price_min': price_min,
	'price_max': price_max,
	'order_by_id': order_by_id,
	'date_from': date_from,
	'date_to': date_to,
	'per_page': per_page,
	'sort_by': sort_by,
	'sort_order': sort_order,
	}

	return data_to_return

def prepare_crud_orders_add_order_data(cur):

	cur.execute("SELECT DISTINCT status FROM orders")
	statuses = cur.fetchall()

	data_to_return = {
		'statuses': statuses, 
	}

	return data_to_return

def crud_orders_add_order(cur, form_data, files_data):

	data = helper.process_form('CRUD Orders', 'create', form_data, files_data)        

	order_data = data['orders']
	item_data = data['order_items']

	cur.execute("SELECT id FROM users WHERE id = %s", (order_data['values'][0],))

	utils.AssertUser(cur.fetchone() != None, "There is no such product with id " + str(order_data['values'][0]))

	query_one = f"INSERT INTO orders ({ order_data['fields'] }) VALUES ({ order_data['placeholders'] }) RETURNING order_id"

	cur.execute(query_one, order_data['values'])

	order_id = cur.fetchone()[0]

	order_item_values = (order_id,) + item_data['values']
	query_two = f"INSERT INTO order_items (order_id, {item_data['fields']}) VALUES (%s, {item_data['placeholders']})"

	cur.execute(query_two, order_item_values)

	message = "Successfully added new order with id: " + str(order_id)

	data_to_return = {
		'message': message,
	}

	return data_to_return

def prepare_crud_orders_edit_order_data(cur, order_id):

	cur.execute("SELECT DISTINCT status FROM orders")
	statuses = cur.fetchall()

	cur.execute("SELECT order_date FROM orders WHERE order_id = %s", (order_id,))
	order_date = cur.fetchone()[0]

	formatted_date = order_date.strftime('%Y-%m-%dT%H:%M:%S')

	cur.execute("""

				SELECT 
					p.id, 
					p.name, 
					oi.quantity, 
					oi.price, 
					sum(oi.quantity * oi.price) AS total_price,
					c.symbol,
					oi.vat
				FROM order_items                AS oi 
					JOIN products               AS p ON oi.product_id = p.id 
					JOIN currencies             AS c ON p.currency_id = c.id
				WHERE order_id = %s 
				GROUP BY 
					p.id, 
					p.name, 
					oi.quantity, 
					oi.price, 
					c.symbol,
					oi.vat

				""", (order_id,))

	products_from_order = cur.fetchall()

	all_products_sum_with_vat = 0

	for product in products_from_order:
		all_products_sum_with_vat += float(product[2] * product[3]) + (float(product[2] * product[3]) * (float(product[6]) / 100))

	data_to_return = {
		'statuses': statuses,
		'order_date': formatted_date,
		'products_from_order': products_from_order,
		'all_products_sum': round(all_products_sum_with_vat,2),
	}

	return data_to_return

def crud_orders_edit_order(cur, order_id, form_data, files_data):

	data = helper.process_form('CRUD Orders', 'edit', form_data, files_data)

	cur.execute("UPDATE orders SET status = %s, order_date = %s WHERE order_id = %s", (data['values'][0], data['values'][1], order_id))

	message = "Order was updated successfully with id = " + str(order_id)

	data_to_return = {
		'message': message,
	}

	return data_to_return

def delete_crud_orders_edit_order(cur, order_id):

	cur.execute('DELETE FROM shipping_details WHERE order_id = %s', (order_id,))
	cur.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
	cur.execute('DELETE FROM orders WHERE order_id = %s', (order_id,))

	message = "You successful deleted a  order with id: " + str(order_id)

	data_to_return = {
		'message': message,
	} 

	return data_to_return

def prepare_crud_users_data(cur, email, user_by_id, status, sort_by, sort_order):

	cur.execute("SELECT DISTINCT verification_status FROM users")
	statuses = cur.fetchall()

	params = []
	query = """

			SELECT  
				id, 
				first_name, 
				last_name, 
				email, 
				verification_status, 
				verification_code, 
				last_active 
			FROM users
			WHERE 1=1

			"""

	if email:
		query += " AND email = %s"
		params.append(email)

	if user_by_id:
		query += " AND id = %s"
		params.append(user_by_id)

	if status:
		query += " AND verification_status = %s"
		params.append(status)

	query += f" ORDER BY {sort_by} {sort_order}"

	cur.execute(query, params)
	users = cur.fetchall()

	data_to_return = {
	'users': users,
	'statuses': statuses,
	}

	return data_to_return

def prepare_crud_users_add_user_data(cur):

	cur.execute("SELECT DISTINCT verification_status FROM users")
	statuses = cur.fetchall()

	data_to_return = {
		'statuses': statuses,
	}

	return data_to_return

def crud_users_add_user(cur, form_data, files_data):

	data = helper.process_form('CRUD Users', 'create', form_data, files_data)

	# hashed_password = utils.hash_password(password_)

	sql_command = f"INSERT INTO users ({data['fields']}) VALUES ({data['placeholders']}) RETURNING id;"
	cur.execute(sql_command, data['values'])

	user_id = cur.fetchone()[0]

	message = "You successfully added new user with id: " + str(user_id)

	data_to_return = {
		'message': message,
	}

	return data_to_return

def prepare_crud_users_edit_user_data(cur, user_id):

	cur.execute("SELECT first_name, last_name, email, verification_status FROM users WHERE id = %s", (user_id,))
	user_row = cur.fetchall()[0]

	data_to_return = {
		'first_name': user_row['first_name'],
		'last_name': user_row['last_name'],
		'email': user_row['email'],
		'verification_status': user_row['verification_status'],
	}

	return data_to_return

def crud_users_edit_user(cur, form_data, files_data, user_id):

	data = helper.process_form('CRUD Users', 'edit', form_data, files_data)

	cur.execute("""

				UPDATE users 
				SET 
					first_name = %s, 
					last_name = %s, 
					email = %s, 
					verification_status = %s 
				WHERE id = %s

				""", (data['values'][0], data['values'][1], data['values'][2], data['values'][3], user_id))

	message = "You successfully edited user with id: " + str(user_id)

	data_to_return = {
		'message': message,
	}

	return data_to_return

def delete_crud_users_user(cur, user_id):

	cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
	# cur.execute("UPDATE users SET verification_status = False WHERE id = %s", (user_id,))

	message = "You successfully deleted user with id: " + str(user_id)

	data_to_return = {
		'message': message,
	}

	return data_to_return

def prepare_template_email_data(cur):

	cur.execute("SELECT * FROM email_template")
	email_templates_rows = cur.fetchall()

	cur.execute("SELECT * FROM settings")
	settings_row = cur.fetchone()

	for template in email_templates_rows:
		if template['name'] == "Verification Email":
			verification_email_values = [template['name'],template['subject'],template['body'], template['sender']]

		elif template['name'] == "Purchase Email":
			purchase_email_values = [template['name'],template['subject'],template['body'], template['sender']]

		elif template['name'] == "Payment Email":
			payment_email_values = [template['name'],template['subject'],template['body'], template['sender']]

		else:
			utils.AssertDev(False, "No information in db for email_template")

	if verification_email_values and purchase_email_values and payment_email_values:
		name, subject, body, sender = verification_email_values
		name_purchase, subject_purchase, body_purchase, sender_purchase = purchase_email_values
		name_payment, subject_payment, body_payment, sender_payment = payment_email_values

	data_to_return = {
		'subject': subject,
		'body': body,
		'subject_purchase': subject_purchase,
		'body_purchase': body_purchase,
		'subject_payment': subject_payment,
		'body_payment': body_payment,
		'background_color': settings_row['send_email_template_background_color'],
		'text_align': settings_row['send_email_template_text_align'],
		'border': settings_row['send_email_template_border'],
		'border_collapse': settings_row['send_email_template_border_collapse'],
	}

	return data_to_return

def edit_email_template(cur, template_name, form_data, files_data):

	data = helper.process_form(template_name, 'edit', form_data, files_data)

	cur.execute("""

				UPDATE email_template 
				SET 
					subject = %s, 
					body = %s
				WHERE name = %s

				""", (data['values'][0], data['values'][1], template_name))

	message = "You successfully updated template for: " + str(template_name)

	data_to_return = {
		'message': message,
	}

	return data_to_return

def prepare_role_permissions_data(cur, role, selected_role, interfaces):

	cur.execute("SELECT role_id, role_name FROM roles")
	roles = cur.fetchall()

	cur.execute("SELECT role_id, role_name FROM roles WHERE role_id = %s", (selected_role,))
	role_to_display = cur.fetchall()

	role_permissions = {role[0]: {interface: {'create': False, 'read': False, 'update': False, 'delete': False} for interface in interfaces} for role in role_to_display}

	cur.execute("""

				SELECT 
					role_permissions.role_id, 
					permissions.interface, 
					permissions.permission_name 
				FROM role_permissions 
					JOIN permissions ON role_permissions.permission_id=permissions.permission_id

				""")
	permissions = cur.fetchall()

	for role_id, interface, permission_name in permissions:
		if role_id in role_permissions and interface in role_permissions[role_id]:
			role_permissions[role_id][interface][permission_name] = True

	data_to_return = {
		'roles': roles,
		'interfaces': interfaces,
		'role_permissions': role_permissions,
	}

	return data_to_return

def role_permissions(cur, role_id, form_data, interfaces):

	cur.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))

	for interface in interfaces:
		for action in ['create', 'read', 'update', 'delete']:
			if f'{interface}_{action}' in form_data:

				cur.execute("SELECT permission_id FROM permissions WHERE permission_name = %s AND interface = %s", (action, interface))

				permission_id = cur.fetchone()[0]

				cur.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)", (role_id, permission_id))

	cur.execute("SELECT role_name FROM roles WHERE role_id = %s", (role_id,))
	role_name = cur.fetchone()[0]

	message = f'You successfully updated permissions for role: {role_name}'

	data_to_return = {
		'message': message,
	}

	return data_to_return

def download_report(form_data):

	if form_data['format'] == 'csv':
		def generate():
			conn = psycopg2.connect(dbname=config.database, user=config.user, password=config.password, host=config.host)

			si = io.StringIO()
			cw = csv.writer(si)
			headers = ['Date', 'Order ID', 'Customer Name', 'Total Price', 'Status']
			cw.writerow(headers)
			si.seek(0)
			yield si.getvalue()
			si.truncate(0)
			si.seek(0)

			offset = 0

			# while True:
			# rows_fetched = False
			batch = utils.fetch_batches(conn, form_data['date_from'], form_data['date_to'], offset)               

			for row in batch:
				rows_fetched = True

				for innerRow in row:

					utils.trace("innerRow")
					utils.trace(innerRow)

					cw.writerow(innerRow)
					si.seek(0)
					yield si.getvalue()
					si.truncate(0)

					# if not rows_fetched: 
					#     break
					offset += 10000

			si.close()
			conn.close()

		return generate

def edit_email_table(cur, background_color, text_align, border, border_collapse):

	utils.AssertUser(int(border) <= 10 and int(border) >= 1, "Border can be between 1 and 10")

	updates = []
	params = []

	if background_color:
		updates.append("send_email_template_background_color = %s")
		params.append(background_color)

	if text_align:
		updates.append("send_email_template_text_align = %s")
		params.append(text_align)

	if border:
		updates.append("send_email_template_border = %s")
		params.append(border)

	if border_collapse:
		updates.append("send_email_template_border_collapse = %s")
		params.append(border_collapse)

	if updates:
		query = "UPDATE settings SET " + ", ".join(updates)
		cur.execute(query, params)

	message = "You changed the email template table look successfully"

	data_to_return = {
	'message': message,
	}

	return data_to_return