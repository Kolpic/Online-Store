from project import utils

def _country_codes_from_db(cur):
	cur.execute("SELECT * FROM country_codes")
	all_country_codes = cur.fetchall()
	return all_country_codes

# def get_cache(key, cache, CACHE_TIMEOUT, time, cur):
# 	if key in cache:
# 		data, timestamp = cache[key]
# 		if time.time() - timestamp < CACHE_TIMEOUT:
# 			utils.trace("Returned cached data successfully")
# 			return data
# 		else:
# 			utils.trace(cache)
# 			utils.trace("Deleted cached data due to CACHE_TIMEOUT")
# 			cache = {}
# 			utils.trace(cache)
# 			return get_cache(key, cache, CACHE_TIMEOUT, time, cur)
# 	else:
# 		country_codes = _country_codes_from_db(cur)
# 		_set_cache(key, country_codes, cache, time)
# 		utils.trace("Init cache successfully")
# 		return get_cache(key, cache, CACHE_TIMEOUT, time, cur)

def _set_cache(key, data, cache, time):
	cache[key] = (data, time.time())
	utils.trace("Set cache data successfully, because cache was empty")
	utils.trace(cache[key][0])
	return cache[key][0]

def _delete_and_make_new_cache(key, cache, time, cur):
	utils.trace(cache)
	utils.trace("Deleted cached data due to CACHE_TIMEOUT")
	cache = {}
	utils.trace(cache)
	country_codes = _country_codes_from_db(cur)
	utils.trace("Init cache successfully")
	return _set_cache(key=key, data=country_codes, cache=cache, time=time)

def get_country_codes(key, cache, CACHE_TIMEOUT, time, cur):
	if key in cache:
		data, timestamp = cache[key]
		if time.time() - timestamp < CACHE_TIMEOUT:
			utils.trace("Returned cached data successfully")
			return data
		else:
			return _delete_and_make_new_cache(key=key, cache=cache, time=time, cur=cur)
	country_codes = _country_codes_from_db(cur=cur)
	return _set_cache(key=key, data=country_codes, cache=cache, time=time)

# def init_cache(cur, cache, time, CACHE_TIMEOUT):
# 	cache_key = 'country_codes'

# 	cached_data = get_cache(cache_key, cache, CACHE_TIMEOUT, time)
# 	if cached_data is not None:
# 		utils.trace("Passed init cache, because we have already cache with this key")
# 		pass
# 	else:
# 		country_codes = _country_codes_from_db(cur)
# 		_set_cache(cache_key, country_codes, cache, time)
# 		utils.trace("Init cache successfully")