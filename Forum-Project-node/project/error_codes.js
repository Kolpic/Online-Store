const REGISTERED_EMAIL_ERROR_CODE = 'ERR001';
const PASSWORD_LENGTH_ERROR_CODE = 'ERR002';
const PASSWORD_MATCH_ERROR_CODE = 'ERR003';
const PHONE_FORMAT_ERROR_CODE = 'ERR004';
const GENDER_ERROR_CODE = 'ERR005';
const NAME_LENGTH_ERROR_CODE = 'ERR006';
const CAPTCHA_ERROR_CODE = 'ERR007';
const CAPTCHA_TIMEOUT_ERROR_CODE = 'ERR008';
const INVALID_EMAIL_ERROR_CODE = 'ERR009';
const INVALID_URL = 'ERR010';
const ALREADY_REGISTERED_EMAIL = 'ERR011';
const DIFFERENT_EMAIL = 'ERR012';
const ALREADY_VERIFIED_ACCOUNT = 'ERR013';
const DIFFERENT_VERIFICATION_CODE = 'ERR014';
const NOT_VERIFIED_ACCOUNT = 'ERR015';
const TOO_MANY_REQUESTED_PRODUCTS = 'ERR016';
const INVALID_PRODUCT_QUANTITY = 'ERR017';
const NOT_ENOUGHT_QUANTITY = 'ERR018';
const NOT_LOGGED_USER_FOR_MAKEING_ORDER = 'ERR019';
const NOT_LOGGED_USER_FOR_MAKEING_PURCHASE = 'ERR020';
const NOT_LOGGED_USER_FOR_MAKEING_PAYMENT = 'ERR021';
const NOT_LOGGED_USER_FOR_MAKEING_PROFILE_CHANGES = 'ERR022';
const INVALID_FIELD_FROM_PROFILE_SCHEMA = 'ERR023';
const INVALID_FIELD_FROM_CREATE_PRODUCT_SCHEMA = 'ERR024';
const NOT_FOUND_BOUNDARY = 'ERR025';
const NOT_FOUND_MULTYPART_FROM_DATA = 'ERR026';
const PAYMENT_METHOD_FAILED = 'ERR027';
const NO_SUCH_ENTITY_WITH_APLIED_FILTERS = 'ERR028';
const INVALID_SORT_ORDER = 'ERR029';
const NEGATIVE_MIN_PRICE_ERROR = 'ERR030';
const NEGATIVE_MAX_PRICE_ERROR = 'ERR031';

// PayPal errors
const ERROR_GENERATING_ACCESS_TOKEN = 'PP001';
const ERROR_GENERATING_ORDER = 'PP002';
const ERROR_CAPTURE_ORDER = 'PP003';
const INVALID_PAYMENT_METHOD = 'PP004';

module.exports = {
	REGISTERED_EMAIL_ERROR_CODE,
	PASSWORD_LENGTH_ERROR_CODE,
	PASSWORD_MATCH_ERROR_CODE,
	PHONE_FORMAT_ERROR_CODE,
	GENDER_ERROR_CODE,
	NAME_LENGTH_ERROR_CODE,
	CAPTCHA_ERROR_CODE,
	CAPTCHA_TIMEOUT_ERROR_CODE,
	INVALID_EMAIL_ERROR_CODE,
	INVALID_URL,
	ALREADY_REGISTERED_EMAIL,
	DIFFERENT_EMAIL,
	ALREADY_VERIFIED_ACCOUNT,
	DIFFERENT_VERIFICATION_CODE,
	NOT_VERIFIED_ACCOUNT,
	TOO_MANY_REQUESTED_PRODUCTS,
	INVALID_PRODUCT_QUANTITY,
	NOT_ENOUGHT_QUANTITY,
	NOT_LOGGED_USER_FOR_MAKEING_ORDER,
	NOT_LOGGED_USER_FOR_MAKEING_PURCHASE,
	NOT_LOGGED_USER_FOR_MAKEING_PROFILE_CHANGES,
	INVALID_FIELD_FROM_PROFILE_SCHEMA,
	INVALID_FIELD_FROM_CREATE_PRODUCT_SCHEMA,
	NOT_FOUND_BOUNDARY,
	NOT_FOUND_MULTYPART_FROM_DATA,
	PAYMENT_METHOD_FAILED,
	NO_SUCH_ENTITY_WITH_APLIED_FILTERS,
	INVALID_SORT_ORDER,
	NEGATIVE_MIN_PRICE_ERROR,
	NEGATIVE_MAX_PRICE_ERROR,
	ERROR_GENERATING_ACCESS_TOKEN,
	ERROR_GENERATING_ORDER,
	INVALID_PAYMENT_METHOD,
}