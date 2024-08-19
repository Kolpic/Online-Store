from project import cache_impl, sessions
from project import sessions
import os, re
from decimal import Decimal
from datetime import timedelta, datetime
from project import utils

def prepare_get_registration_return_data(cur, first_captcha_number, second_captcha_number):

    cur.execute("INSERT INTO captcha(first_number, second_number, result) VALUES (%s, %s, %s) RETURNING *", (first_captcha_number, second_captcha_number, first_captcha_number + second_captcha_number))
    captcha_row = cur.fetchone()
    captcha_id = captcha_row['id']

    country_codes = cache_impl.get_country_codes(cur=cur)

    prepared_data = {
        'first_captcha_number': first_captcha_number,
        'second_captcha_number': second_captcha_number,
        'captcha_result': captcha_row['result'],
        'country_codes': country_codes,
        'captcha_id': captcha_id
    }

    return prepared_data

def check_post_registration_fields_data(cur, first_name, last_name, email, password_, confirm_password_, phone, gender, captcha_id, captcha_,user_ip, hashed_password, verification_code, country_code, address):    
    regex_phone = r'^\d{7,15}$'

    utils.AssertUser(password_ == confirm_password_, "Password and Confirm Password fields are different")
    utils.AssertUser(re.fullmatch(regex_phone, phone), "Phone number format is not valid. The number should be between 7 and 15 digits")
    utils.AssertUser(gender == 'male' or gender == 'female', "Gender must be Male of Female")
    utils.AssertUser(len(first_name) >= 3 and len(first_name) <= 50, "First name is must be between 3 and 50 symbols")
    utils.AssertUser(len(last_name) >= 3 and len(last_name) <= 50, "Last name must be between 3 and 50 symbols")
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    utils.AssertUser(re.fullmatch(regex, email), "Email is not valid")

    cur.execute("SELECT id, last_attempt_time, attempts FROM captcha_attempts WHERE ip_address = %s", (user_ip,))
    attempt_record = cur.fetchone()

    attempts = 0
    max_attempts = int(utils.get_captcha_setting_by_name(cur, 'max_captcha_attempts'))
    timeout_minutes = int(utils.get_captcha_setting_by_name(cur,'captcha_timeout_minutes'))

    if attempt_record:
        attempt_id, last_attempt_time, attempts = attempt_record
        time_since_last_attempt = datetime.now() - last_attempt_time
        utils.AssertUser(not(attempts >= max_attempts and time_since_last_attempt < timedelta(minutes=timeout_minutes)), "You typed wrong captcha several times, now you have timeout " + str(timeout_minutes) + " minutes")
        if time_since_last_attempt >= timedelta(minutes=timeout_minutes):
            attempts = 0
            
    # captcha_id = session.get("captcha_id")
    cur.execute("SELECT result FROM captcha WHERE id = %s", (captcha_id,))
    result = cur.fetchone()[0]

    if captcha_ != result:
        utils.add_recovery_data_in_session(recovery_data)
        new_attempts = attempts + 1
        if attempt_record:
            cur.execute("UPDATE captcha_attempts SET attempts = %s, last_attempt_time = CURRENT_TIMESTAMP WHERE id = %s", (new_attempts, attempt_id))
        else:
            cur.execute("INSERT INTO captcha_attempts (ip_address, attempts, last_attempt_time) VALUES (%s, 1, CURRENT_TIMESTAMP)", (user_ip,))
        raise exception.WrongUserInputException("Invalid CAPTCHA. Please try again")
    else:
        if attempt_record:
            cur.execute("DELETE FROM captcha_attempts WHERE id = %s", (attempt_id,))

    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user_row = cur.fetchone()

    utils.AssertUser(user_row is None, "There is already registration with this email")

    cur.execute("SELECT * FROM country_codes WHERE code = %s", (country_code,))
    country_code_row = cur.fetchone()
    country_code_id = country_code_row['id']

    cur.execute("""
        INSERT INTO users 
            (first_name, last_name, email, password, verification_code, address, gender, phone, country_code_id) 
        VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, 
        (first_name, last_name, email, hashed_password, verification_code, address, gender, phone,country_code_id))

def post_verify_method(cur, email, verification_code):

    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user_row = cur.fetchone()
    utils.AssertUser(user_row is not None, "There is no registration with this mail")

    email_from_database = user_row['email']
    is_verified = user_row['verification_status']
    verification_code_database = user_row['verification_code']

    utils.AssertUser(email_from_database == email, "You entered different email")
    utils.AssertUser(not is_verified, "The account is already verified")
    utils.AssertUser(verification_code_database == verification_code, "The verification code you typed is different from the one we send you")
    
    cur.execute("UPDATE users SET verification_status = true WHERE verification_code = %s", (verification_code,))

def post_login_method(cur, email, password_):
    cur.execute("""
                    SELECT 
                        *
                    FROM 
                        users
                    WHERE 
                        email = %s
                    """, (email,))
    user_data = cur.fetchone()

    utils.AssertUser(user_data, "There is no registration with this email")
    utils.AssertUser(utils.verify_password(password_, user_data['password']), "Invalid email or password")
    utils.AssertUser(user_data['verification_status'], "Your account is not verified or has been deleted")

    return user_data

def get_home_query_data(cur, sort_by, sort_order, products_per_page, page, offset, product_name, product_category, price_min, price_max):

    name_filter = f" AND products.name ILIKE %s" if product_name else ''
    category_filter = f" AND category ILIKE %s" if product_category else ''
    price_filter = ""
    query_params = []

    if product_name:
        query_params.append(f"%{product_name}%")
    if product_category:
        query_params.append(f"%{product_category}%")

    if price_min and price_max:
        price_filter = " AND price BETWEEN %s AND %s"
        query_params.extend([price_min, price_max])

    query = f"""
                SELECT 
                    products.id, 
                    products.name, 
                    products.price, 
                    products.quantity, 
                    products.category, 
                    currencies.symbol, 
                    settings.vat 
                FROM products 
                    JOIN currencies ON products.currency_id = currencies.id
                    JOIN settings   ON products.vat_id      = settings.id
                WHERE TRUE{name_filter}{category_filter}{price_filter} 
                ORDER BY {sort_by} {sort_order}
                LIMIT %s 
                OFFSET %s
            """

    utils.trace(query)

    query_params.extend([products_per_page, offset])

    cur.execute(query,tuple(query_params))
    products = cur.fetchall()

    count_query = f"SELECT COUNT(*) as count FROM products WHERE TRUE{name_filter}{category_filter}{price_filter}"
    cur.execute(count_query, tuple(query_params[:-2]))

    total_products = cur.fetchone()['count']

    utils.AssertUser(total_products, 'No results with this filter')

    total_pages = (total_products // products_per_page) + (1 if total_products % products_per_page > 0 else 0)

    data_to_return = {
        'products': products,
        'total_pages': total_pages,
    }

    return data_to_return

def get_profile_data(cur, authenticated_user):

    cur.execute("""
                SELECT 
                    users.*,
                    country_codes.* 
                FROM users
                JOIN country_codes ON users.country_code_id = country_codes.id
                WHERE email = %s

            """, (authenticated_user,))

    user_details = cur.fetchone()

    country_codes = cache_impl.get_country_codes(cur)

    data_to_return = {
        'first_name': user_details['first_name'],
        'last_name': user_details['last_name'],
        'email': user_details['email'],
        'phone': user_details['phone'],
        'address': user_details['address'],
        'gender': user_details['gender'],
        'code': user_details['code'],
        'country_codes': country_codes
    }

    return data_to_return

def post_update_profile(cur, conn, first_name, last_name, email, password_, address, phone, country_code, gender, session_id):

    query_string = "UPDATE users SET "
    fields_list = []
    updated_fields = []

    name_regex = r'^[A-Za-z]+$'

    if first_name:
        if len(first_name) < 3 or len(first_name) > 50 or not re.match(name_regex, first_name):
            session['settings_error'] = 'First name must be between 3 and 50 letters and contain no special characters or digits'
            return redirect('/profile')
        query_string += "first_name = %s, "
        fields_list.append(first_name)
        updated_fields.append("first name")
    if last_name:
        if len(last_name) < 3 or len(last_name) > 50 or not re.match(name_regex, last_name):
            session['settings_error'] = 'Last name must be between 3 and 50 letters'
            return redirect('/profile')
        query_string += "last_name = %s, "
        fields_list.append(last_name)
        updated_fields.append("last name")
    if email:
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
        if not (re.fullmatch(regex, email)):
            session['settings_error'] = 'Invalid email'
            return redirect('/profile')
        query_string += "email = %s, "
        fields_list.append(email)
        updated_fields.append("email")
    if password_:
        if len(password_) < 8 or len(password_) > 20:
            session['settings_error'] = 'Password must be between 8 and 20 symbols'
            return redirect('/profile')
        query_string += "password = %s, "
        hashed_password = utils.hash_password(password_)
        fields_list.append(hashed_password)
        updated_fields.append("password")
    if address:
        if len(address) < 5 or len(address) > 50:
            session['settings_error'] = 'Address must be between 3 and 50 letters'
            return redirect('/profile')
        query_string +="address = %s, "
        fields_list.append(address)
        updated_fields.append("address")
    else:
        query_string +="address = %s, "
        fields_list.append(address)
        # updated_fields.append("address")

    if phone:
        if len(str(phone)) < 7 or len(str(phone)) > 15:
            session['settings_error'] = 'Phone must be between 7 and 15 digits'
            return redirect('/profile')
        query_string += "phone = %s, "
        fields_list.append(phone)
        updated_fields.append("phone")

    if country_code:
        cur.execute("SELECT * FROM country_codes WHERE code = %s", (country_code,))
        country_code_row = cur.fetchone()

        query_string += "country_code_id = %s, "
        fields_list.append(country_code_row['id'])
        updated_fields.append("country code")

    if gender:
        if gender != 'male' and gender != 'female' and gender != 'other':
            session['settings_error'] = 'Gender must be between male, female or other'
        query_string += "gender = %s, "
        fields_list.append(gender)
        updated_fields.append("gender")

    if first_name == "" and last_name == "" and email == "" and password_ == "" and address == "" and phone == "" and gender == "":
        session['settings_error'] = 'You have to insert data in at least one field'
        return redirect('/profile')

    query_string = query_string[:-2]
    query_string += " WHERE email = %s"

    email_in_session = sessions.get_current_user(session_id=session_id, cur=cur, conn=conn)
    fields_list.append(email_in_session)

    cur.execute(query_string, (fields_list))
    
    updated_fields_message = ', '.join(updated_fields)

    data_to_return = {
        'updated_fields_message': updated_fields_message
    }

    return data_to_return

def add_to_cart(conn, cur, user_id, product_id, quantity, session_cookie_id):
    authenticated_user =  sessions.get_current_user(session_id=session_cookie_id, cur=cur, conn=conn)

    cur.execute("""
                    SELECT 
                        products.*,
                        settings.vat 
                    FROM products
                        JOIN settings ON products.vat_id = settings.id
                    WHERE 
                        products.id = %s
            """, (product_id, ))

    products_settings_rows = cur.fetchone()

    vat = products_settings_rows['vat']

    if authenticated_user == None:

        utils.trace("ENTERED authenticated_user == None")

        cur.execute("SELECT * FROM carts WHERE session_id = %s", (user_id,))
        cart_row = cur.fetchone()

        if cart_row:
            utils.trace("ENTERED already present cart")
            cart_id = cart_row['cart_id']
        else:
            utils.trace("ENTERED inserted new cart with anonym sesession")
            cur.execute("INSERT INTO carts(session_id) VALUES (%s) RETURNING cart_id", (user_id,))
            cart_id = cur.fetchone()['cart_id']

    else:

        utils.trace("ENTERED authenticated_user IS NOT NONE")

        cur.execute("SELECT * FROM carts WHERE user_id = %s", (user_id,))
        cart_row = cur.fetchone() 

        if cart_row:

            utils.trace("ENTERED ALREADY CREATED CART FOR AUTH USER")

            cart_id = cart_row['cart_id']
        else:

            utils.trace("ENTERED CREATING CART FOR AUTH USER")

            cur.execute("INSERT INTO carts(user_id) VALUES (%s) RETURNING cart_id", (user_id,))
            cart_id = cur.fetchone()['cart_id']
       
    utils.trace("cart_id")
    utils.trace(cart_id)

    cur.execute("SELECT * FROM cart_items WHERE cart_id = %s AND product_id = %s", (cart_id, product_id))
    cart_items_row = cur.fetchone()

    if cart_items_row is not None:
        cart_items_id = cart_items_row['id']

    if cart_items_row:
        utils.trace("ENTERED cart_items_row is NOT None")

        cur.execute("UPDATE cart_items SET quantity = quantity + %s WHERE id = %s", (quantity, cart_items_id))

        utils.trace("added same item, quantity was increased")

        return "You successfully added same item, quantity was increased."
    else:
        utils.trace("ENTERED cart_items_row is None")

        cur.execute("INSERT INTO cart_items (cart_id, product_id, quantity, vat) VALUES (%s, %s, %s, %s)", (cart_id, product_id, quantity, vat))

        utils.trace("INSERTED ITEMS")

        return "You successfully added item."

def get_cart_items_count(conn, cur, user_id):

    query = """
            SELECT 
                products.name, 
                products.price, 
                cart_items.quantity, 
                products.id 
            FROM carts 
                JOIN cart_items  ON carts.cart_id         = cart_items.cart_id 
                JOIN products    ON cart_items.product_id = products.id 
            WHERE
    """

    if isinstance(user_id, str):
        query += f" carts.session_id = %s"

    else:
        query += f" carts.user_id = %s"

    cur.execute(query, (user_id,))

    items = cur.fetchall()

    utils.AssertDev(len(items) <= 1000, "Fetched too many rows in get_cart_items_count function")

    return len(items)

def remove_from_cart(conn, cur, item_id):
    cur.execute("DELETE FROM cart_items where product_id = %s", (item_id,))
    return "You successfully deleted item."

def view_cart(conn, cur, user_id):
    cur.execute("""
                SELECT 
                    products.name, 
                    products.price, 
                    cart_items.quantity, 
                    products.id, 
                    currencies.symbol, 
                    settings.vat
                FROM carts
                    JOIN cart_items  ON carts.cart_id         = cart_items.cart_id 
                    JOIN products    ON cart_items.product_id = products.id
                    JOIN currencies  ON products.currency_id  = currencies.id
                    JOIN settings    ON products.vat_id       = settings.id
                WHERE carts.user_id = %s
                """, (user_id,))

    items = cur.fetchall()

    utils.AssertDev(len(items) <= 1000, "Fetched too many rows in view_cart function")

    return items

def merge_cart(conn, cur, user_id, session_id):
    cur.execute("SELECT * FROM carts WHERE session_id = %s", (session_id,))
    cart_row = cur.fetchone()
    cart_id = cart_row['cart_id']
    cur.execute("UPDATE carts SET user_id = %s, session_id = null WHERE cart_id = %s and session_id = %s", (user_id, cart_id, session_id))
    # if cart_row:
    #     old_cart_id = cart_row['cart_id']
        
    #     cur.execute("SELECT * FROM cart_items WHERE cart_id = %s", (old_cart_id,))
    #     items = cur.fetchall()

    #     cur.execute("INSERT INTO carts (user_id) VALUES (%s) RETURNING cart_id", (user_id,))
    #     new_cart_id = cur.fetchone()['cart_id']

    #     for item in items:
    #         cur.execute("INSERT INTO cart_items (cart_id, product_id, quantity, added_at, vat) VALUES (%s, %s, %s, %s, %s)",
    #                     (new_cart_id, item['product_id'], item['quantity'], item['added_at'], item['vat']))

    #     cur.execute("DELETE FROM cart_items WHERE cart_id = %s", (old_cart_id,))
    #     cur.execute("DELETE FROM carts WHERE session_id = %s", (session_id,))

def get_cart_method_data(cur, conn, authenticated_user):

    cur.execute("SELECT users.*, settings.vat FROM users, settings WHERE email = %s", (authenticated_user,))
    user_settings_row = cur.fetchone()

    user_id = user_settings_row['id']
    first_name = user_settings_row['first_name']
    last_name = user_settings_row['last_name']
    #TODO -> name
    vat_in_persent = user_settings_row['vat']

    country_codes = cache_impl.get_country_codes(cur=cur)

    items = view_cart(conn, cur, user_id)

    total_sum = 0

    total_sum_with_vat = 0

    for item in items:
        vat_float = (Decimal(item['vat']) / 100)
        items_sum_without_vat = item['price'] * item['quantity']
        total_sum += items_sum_without_vat
        vat = items_sum_without_vat * vat_float
        total_sum_with_vat += items_sum_without_vat + vat

    data_to_return = {
        'items': items,
        'total_sum_with_vat': total_sum_with_vat,
        'total_sum': total_sum,
        'country_codes': country_codes,
        'first_name': first_name,
        'last_name': last_name,
        'vat_in_persent': vat_in_persent,
    }

    return data_to_return

def post_cart_method(cur, email, first_name, last_name, town, address, country_code, phone):

    regex_phone = r'^\d{7,15}$'
    regex_email = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

    # Check fields 
    utils.AssertUser(len(first_name) >= 3 and len(first_name) <= 50, "First name is must be between 3 and 50 symbols")
    utils.AssertUser(len(last_name) >= 3 and len(last_name) <= 50, "Last name must be between 3 and 50 symbols")
    utils.AssertUser(re.fullmatch(regex_email, email), "Email is not valid")
    utils.AssertUser(re.fullmatch(regex_phone, phone), "Phone number format is not valid. The number should be between 7 and 15 digits")
    utils.AssertUser(phone[0] != "0", "Phone number format is not valid.")

    # Retrieve cart items for the user
    cur.execute("""
                SELECT 
                    *
                FROM users      
                JOIN carts ON users.id = carts.user_id
                WHERE users.email = %s
                """, 
                (authenticated_user,))

    users_carts_row = cur.fetchone()
    user_id = users_carts_row['id']
    user_first_name = users_carts_row['first_name']
    user_last_name = users_carts_row['last_name']
    cart_id = users_carts_row['cart_id']

    #------------------------------------------------ edna zaqvka
    cur.execute("""
                SELECT 
                    cart_items.product_id, 
                    products.name, 
                    cart_items.quantity, 
                    products.price, 
                    currencies.symbol, 
                    cart_items.vat 
                FROM cart_items
                JOIN products   ON cart_items.product_id = products.id
                JOIN currencies ON products.currency_id  = currencies.id
                WHERE cart_items.cart_id = %s
                """,
                (cart_id,))

    cart_items = cur.fetchall()

    db_items_quantity = []

    for item in cart_items:
        cur.execute("""
                    SELECT 
                        quantity 
                    FROM products 
                    WHERE id = %s
                    """, 
                    (item['product_id'],))

        item_quantity_db = cur.fetchone()[0]

        db_items_quantity.append(item_quantity_db)

    #------------------------------------------------
    # TODO: CODE REVIEW - I/O read - write
    # Check and change quantity 
    for item in cart_items:

        product_id_, name, quantity, price, symbol, vat = item
        quantity_db = db_items_quantity.pop(0)

        if quantity > quantity_db:
            session['cart_error'] = "We don't have " + str(quantity) + " from product: " + str(name) + " in our store. You can purchase less or to remove the product from your cart"
            utils.add_recovery_data_in_session(session.get('recovery_data'))
            return redirect('/cart')

        cur.execute("UPDATE products SET quantity = quantity - %s WHERE id = %s", (quantity, product_id_))

    price_mismatch = False
    for item in cart_items:

        product_id, name, quantity, cart_price, symbol, vat = item

        cur.execute("SELECT price FROM products WHERE id = %s", (product_id,))
        current_price = cur.fetchone()['price']

        if current_price != cart_price:
            # Price can be updated here
            price_mismatch = True
            break

    utils.AssertUser(not price_mismatch, "The price on some of your product's in the cart has been changed, you can't make the purchase")

    # First make order, then make shipping_details #
    formatted_datetime = datetime.now().strftime('%Y-%m-%d')
    cur.execute("""
                INSERT INTO orders (
                    user_id, 
                    status, 
                    order_date) 
                VALUES (%s, %s, CURRENT_TIMESTAMP) 
                RETURNING order_id
                """, 
                (user_id, "Ready for Paying")) #formatted_datetime

    order_id = cur.fetchone()['order_id']

    # Insert order products into order_items table
    for item in cart_items:

        item_id = item['product_id']
        item_quantity = item['quantity']
        item_price = item['price']
        item_vat = item['vat']

        cur.execute("""
                    INSERT INTO order_items (
                        order_id, 
                        product_id, 
                        quantity, 
                        price, 
                        vat) 
                    VALUES (%s, %s, %s, %s, %s)
                    """, 
                    (order_id, item_id, item_quantity, item_price, item_vat))

    cur.execute("""
                SELECT 
                    * 
                FROM country_codes 
                WHERE code = %s
                """, 
                (country_code,))

    country_code_row = cur.fetchone()
    country_code_id = country_code_row['id']

    cur.execute("""
                INSERT INTO shipping_details (
                        order_id, 
                        email, 
                        first_name, 
                        last_name, 
                        town, 
                        address, 
                        phone, 
                        country_code_id  ) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, 
                (order_id, email, first_name, last_name, town, address, phone, country_code_id))

    # Total sum to be passed to the payment.html
    # Total sum with vat to be passed to the payment.html
    total_sum = 0

    total_sum_with_vat = 0

    for item in cart_items:
        vat_float = (float(item['vat']) / 100)
        items_sum_without_vat = float(item['quantity'] * item['price'])
        total_sum += items_sum_without_vat
        vatt = items_sum_without_vat * vat_float
        total_sum_with_vat += items_sum_without_vat + vatt

    # When the purchase is made we empty the user cart
    # TODO: cart_items -> CART_ITEMS 
    cur.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))

    cur.execute("""
                SELECT 
                    shipping_details.*, 
                    country_codes.code 
                FROM shipping_details
                    JOIN orders        ON shipping_details.order_id        = orders.order_id 
                    JOIN country_codes ON shipping_details.country_code_id = country_codes.id 
                WHERE orders.order_id = %s
                """, 
                (order_id,))

    shipping_details = cur.fetchall()

    cur.execute("SELECT * FROM settings")
    settings_row = cur.fetchone()

    data_to_return = {
        'order_id': order_id,
        'cart_items': cart_items,
        'shipping_details': shipping_details,
        'total_sum_with_vat': total_sum_with_vat,
        'total_sum': total_sum,
        'user_first_name': user_first_name,
        'user_last_name': user_last_name,
        'vat_in_persent': settings_row['vat'],
    }

    return data_to_return