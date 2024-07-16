from flask_sqlalchemy import SQLAlchemy
import json
from datetime import datetime

db = SQLAlchemy()

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    value = db.Column(db.Integer, nullable=False)

class EmailTemplate(db.Model):
    __tablename__ = 'email_template'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.String(255), nullable=False)
    sender = db.Column(db.String(255), nullable=False)

class Currency(db.Model):
    __tablename__ = 'currencies'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(50), nullable=True)
    symbol = db.Column(db.String(10), nullable=True)

    products = db.relationship('Product', backref='currency', lazy=True)

class CustomSession(db.Model):
    __tablename__ = 'custom_sessions'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(40), default=lambda:uuid.uuid4().hex)
    data = db.Column(db.Text)
    expires_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now() + timedelta(hours=1))
    is_active = db.Column(db.Boolean, default=False, nullable=False)

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.cart_id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

class Cart(db.Model):
    __tablename__ = 'carts'
    cart_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    items = db.relationship('CartItem', backref='cart', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(255), nullable=False)
    image = db.Column(db.LargeBinary, nullable=True)
    cart_items = db.relationship('CartItem', backref='product', lazy=True)

    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'), nullable=False)

class ShippingDetail(db.Model):
    __tablename__ = 'shipping_details'
    shipping_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id'), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    town = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    country_code_id = db.Column(db.Integer, db.ForeignKey('country_codes.id'), nullable=False)

class Order(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    # product_details = db.Column(db.JSON, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    shipping_details = db.relationship('ShippingDetail', backref='order', lazy=True)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric, nullable=False)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    verification_status = db.Column(db.Boolean, nullable=False, default=False)
    verification_code = db.Column(db.String(255), nullable=True)
    token_id = db.Column(db.Integer, db.ForeignKey('tokens.id'), nullable=True)
    carts = db.relationship('Cart', backref='user', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)
    last_active = db.Column(db.DateTime, default=db.func.current_timestamp())
    address = db.Column(db.String(255))
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    country_code_id = db.Column(db.Integer, db.ForeignKey('country_codes.id'))

    def update_last_active(self):
        self.last_active = db.func.current_timestamp()
        db.session.commit()

class Token(db.Model):
    __tablename__ = 'tokens'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    login_token = db.Column(db.String(255), nullable=False, unique=True)
    expiration = db.Column(db.DateTime, nullable=False)

class CountryCode(db.Model):
    __tablename__ = 'country_codes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    code = db.Column(db.String(10), nullable=False)

class StaffRole(db.Model):
    __tablename__ = 'staff_roles'
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), primary_key=True)

class Staff(db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    roles = db.relationship('StaffRole', backref='staff', lazy=True)

class Role(db.Model):
    __tablename__ = 'roles'
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(255), nullable=False)
    permissions = db.relationship('RolePermission', backref='role', lazy=True)

class Permission(db.Model):
    __tablename__ = 'permissions'
    permission_id = db.Column(db.Integer, primary_key=True)
    permission_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    interface = db.Column(db.String(255), nullable=False)

class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.permission_id'), primary_key=True)

class CaptchaSetting(db.Model):
    __tablename__ = 'captcha_settings'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    value = db.Column(db.String(255), nullable=False)

class CaptchaAttempt(db.Model):
    __tablename__ = 'captcha_attempts'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(255), nullable=False)
    last_attempt_time = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    attempts = db.Column(db.Integer, nullable=False)

class Captcha(db.Model):
    __tablename__ = 'captcha'
    id = db.Column(db.Integer, primary_key=True)
    first_number = db.Column(db.Integer, nullable=False)
    second_number = db.Column(db.Integer, nullable=False)
    result = db.Column(db.Integer, nullable=False)
    created = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

class ExceptionLog(db.Model):
    __tablename__ = 'exception_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=True)
    exception_type = db.Column(db.String(255), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    time = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

def order_items_to_json(order_id):
    order = Order.query.get(order_id)
    if not order:
        return None

    order_items_json = []
    for item in order.items:
        product = Product.query.get(item.product_id)
        order_items_json.append({
            'product_id': item.product_id,
            'name': product.name,
            'quantity': item.quantity,
            'price': str(item.price)
        })

    return json.dumps(order_items_json)