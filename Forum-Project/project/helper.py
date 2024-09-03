import io

from decimal import Decimal
from datetime import timedelta, datetime
from werkzeug.utils import secure_filename

from project import utils

ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # Maximum file size in bytes (e.g., 10MB)

def handle_image_field(image_data):
    print("image_data.filename.split('.')[-1]", flush=True)
    print(image_data, flush=True)
    print(image_data.filename.split('.')[-1], flush=True)

    utils.AssertUser(image_data.filename.split('.')[-1] in FIELD_CONFIG['CRUD Products']['create']['image']['conditions_image'], "Invalid image file extension (must be one of jpg, jpeg, png)")
    filename = secure_filename(image_data.filename)
    image_data = validate_image_size(image_data.stream)
    return image_data

FIELD_CONFIG = {
    'CRUD Products': {
        'create': {
            'name': {'type': str, 'required': True},
            'price': {'type': float, 'required': True, 'conditions': [(lambda x: x > 0, "Price must be a positive number")]},
            'quantity': {'type': int, 'required': True, 'conditions': [(lambda x: x > 0, "Quantity must be a positive number")]},
            'category': {'type': str, 'required': True},
            'image': {'type': 'file', 'required': True, 'conditions_image': ALLOWED_EXTENSIONS,'handler': handle_image_field},
            'currency_id': {'type': int, 'required': True},
        },
        'edit': {
            'name': {'type': str, 'required': True},
            'price': {'type': float, 'required': True, 'conditions': [(lambda x: x > 0, "Price must be a positive number")]},
            'quantity': {'type': int, 'required': True, 'conditions': [(lambda x: x >= 0, "Quantity must not be negative")]},
            'category': {'type': str, 'required': True},
            'currency': {'type': int, 'required': True},
        }
    },
    'Staff roles': {
        'create_staff_roles': {
            'staff_id': {'type': str, 'required': True},
            'role_id': {'type': str, 'required': True}
        },
        'create_staff':{
            'username': {'type': str, 'required': True, 'conditions': [(lambda x: len(x.split(' ')) == 1, "You have to type name without intervals")]},
            'password': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) <= 20, "Password must be below 20 symbols")]},
        }
    },
    'CRUD Orders': {
        'create': {
            'orders': {
                'user_id': {'type': int, 'required': True, 'conditions': [(lambda x: x > 0, "User id must be possitive")]},
                'status': {'type': str, 'required': True},
                'order_date': {'type': datetime, 'required': True, 'conditions': [(lambda x: datetime.strptime(x, '%Y-%m-%dT%H:%M') <= datetime.now(), "You can't make orders with future date")]},
            },
            'order_items': {
                'product_id': {'type': int, 'required': True, 'conditions': [(lambda x: x > 0, "Product id must be possitive")]},
                'price': {'type': float, 'required': True, 'conditions': [(lambda x: x > 0, "Price must be possitive")]},
                'quantity': {'type': int, 'required': True, 'conditions': [(lambda x: x > 0, "Quantity must be possitive")]},
                'vat': {'type': int, 'required': True, 'conditions': [(lambda x: x > 5 and x < 50 , "VAT must be between 5 and 50")]},
            }
        },
        'edit': {
            'status': {'type': str, 'required': True},
            'order_date': {'type': datetime, 'required': True},
        }
    },
    'CRUD Users': {
        'create': {
            'first_name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=4 and len(x) <= 15, "First name must be al least 4 symbols long and under 16 symbols")]},
            'last_name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >= 4 and len(x) <= 15, "Last name must be al least 4 symbols long and under 16 symbols")]},
            'email': {'type': str, 'required': True, 'conditions': [(lambda x: '@' in x, "Invalid email")]},
            'password': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=4 and len(x) <= 20, "Password must be between 4 and 20 symbols")]},
            # 'confirm_password': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=4 and len(x) <= 20, "Password must be between 4 and 20 symbols")]},
            'verification_code': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=10 and len(x) <= 20, "Verification code must be between 10 and 20 symbols")] },
            'verification_status': {'type': bool, 'required': True, 'conditions': [(lambda x: x == True or x == False, "The status can be only true or false")]}
        },
        'edit': {
            'first_name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >=4 and len(x) <= 15, "First name must be al least 4 symbols long and under 16 symbols")]},
            'last_name': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) >= 4 and len(x) <= 15, "Last name must be al least 4 symbols long and under 16 symbols")]},
            'email': {'type': str, 'required': True, 'conditions': [(lambda x: '@' in x, "Invalid email")]},
            'verification_status': {'type': bool, 'required': True, 'conditions': [(lambda x: x == True or x == False, "The status can be only true or false")]}
        }
    },
    'Verification Email': {
        'edit': {
            'subject': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 5 and len(x) <= 30, "Email subject should be between 5 and 30 symbols")]},
            'body': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 10 and len(x) <= 255, "Email subject should be under 255 symbols")]},
        }
    },
    'Purchase Email': {
        'edit': {
            'subject_purchase': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 5 and len(x) <= 30, "Email subject should be between 5 and 30 symbols")]},
            'body_purchase': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 10 and len(x) <= 255, "Email subject should be under 255 symbols")]},
        }
    },
    'Payment Email': {
        'edit': {
            'subject_payment': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 5 and len(x) <= 30, "Email subject should be between 5 and 30 symbols")]},
            'body_payment': {'type': str, 'required': True, 'conditions': [(lambda x: len(x) > 10 and len(x) <= 255, "Email subject should be under 255 symbols")]},
        }
    }
}

def get_field_config(interface, method):
    return FIELD_CONFIG.get(interface, {}).get(method, {}) # return the right fields for the interface with the metod we provided

def validate_image_size(image_stream):
    image_stream.seek(0, io.SEEK_END) # Seek to the end of the file
    file_size = image_stream.tell() # Get the current position, which is the file size
    image_stream.seek(0) # Reset the stream position to the start
    utils.AssertUser(file_size < MAX_FILE_SIZE, "The image file size must not exceed 10MB.")
    return image_stream.read()

def validate_field(field_name, value, config):

    print("==== Entered validate_field method ======",flush=True)
    print(isinstance(value, str), flush=True)

    utils.AssertUser(config['required'] and value, f"You must add information in every field: {field_name}")

    if 'type' in config and config['type'] in [float, int, bool]:
        print("==== Entered type validation ======",flush=True)
        try:
            value = config['type'](value)
        except ValueError:
            raise ValueError(f"{field_name} is not a valid {config['type'].__name__}")

    if 'conditions' in config:
        print("==== Entered conditions validation ======",flush=True)
        for condition, message in config['conditions']:
            print("==== Entered conditions validation ======",flush=True)
            print("condition", flush=True)
            print(condition, flush=True)
            print("value", flush=True)
            print(value, flush=True)
            utils.AssertUser(condition(value), message)

    if field_name == 'password':
        value = utils.hash_password(value)

    return value

def process_form(interface, method, form_data_fields, files_data):
    form_data = {}
    nested_data = {}
    nested_flag = False

    field_config = get_field_config(interface, method)

    print("form_data_fields", flush=True)
    print(form_data_fields, flush=True)
    print("files_data", flush=True)
    print(files_data, flush=True)
    print("field_config", flush=True)
    print(field_config, flush=True)

    for section, config_dict in field_config.items():
        nested_data[section] = {}

        print("section", flush=True)
        print(section, flush=True)
        print("config_dict", flush=True)
        print(config_dict, flush=True)
        print("field_config.items()", flush=True)
        print(field_config.items(), flush=True)

        if section != 'orders' and section != 'order_items':
            print("No nested for", flush=True)
            value = None

            if config_dict['type'] == 'file':
                value = files_data.get(section)
                value = config_dict['handler'](value)
            else:
                value = form_data_fields.get(section)

            print("section", flush=True)
            print(section, flush=True)
            print("value", flush=True)
            print(value, flush=True)
            print("config_dict", flush=True)
            print(config_dict, flush=True)

            validated_value = validate_field(section, value, config_dict)
            form_data[section] = validated_value

            print("form_data[section]", flush=True)
            print(form_data[section], flush=True)
        else:
            print("Nested for", flush=True)
            for field, config in config_dict.items():

                value = None

                if config['type'] == 'file':
                    value = files_data.get.get(field)
                    value = special_field_handlers['image'](value) if field == 'image' else value
                else:
                    value = form_data_fields.get(field)

                validated_value = validate_field(field, value, config)
                nested_data[section][field] = validated_value

            form_data.update(nested_data)
            nested_flag = True

    values_to_insert_db = {}

    print("form_data", flush=True)
    print(form_data, flush=True)
    print("nested_flag", flush=True)
    print(nested_flag, flush=True)

    if nested_flag == False:
        print("YES", flush=True)
        values_to_insert_db = {
            'fields': ', '.join(form_data.keys()),
            'placeholders': ', '.join(['%s'] * len(form_data)),
            'values': tuple(form_data.values())
        }

        print("values_to_insert_db", flush=True)
        print(values_to_insert_db, flush=True)
    else:
        print("NO", flush=True)
        for table_name, fields_data in form_data.items():

            fields = ', '.join(fields_data.keys())
            placeholders = ', '.join(['%s'] * len(fields_data))
            values = tuple(fields_data.values())

            table_data = {
                'fields': fields,
                'placeholders': placeholders,
                'values': values
            }

            values_to_insert_db[table_name] = table_data

            print("values_to_insert_db", flush=True)
            print(values_to_insert_db, flush=True)
    
    return values_to_insert_db