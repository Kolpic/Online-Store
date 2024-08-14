from project import utils
import time
from project.config import cache, CACHE_TIMEOUT


def _country_codes_from_db(cur):
	cur.execute("SELECT * FROM country_codes")
	all_country_codes = cur.fetchall()
	return all_country_codes

def _set_cache(data):
	global cache
	cache = (data, time.time())
	utils.trace("Set cache data successfully, because cache was empty")
	# utils.trace("cache")
	# utils.trace(cache)
	return cache[0]

def _refresh_cache(cur):
	global cache
	# utils.trace(cache)
	utils.trace("Deleted cached data due to CACHE_TIMEOUT")
	cache.clear()
	# utils.trace(cache)
	country_codes = _country_codes_from_db(cur)
	utils.trace("Init cache successfully")
	return _set_cache(data=country_codes)

def get_country_codes(cur):
	global cache
	# utils.trace(cache)
	# utils.trace(CACHE_TIMEOUT)
	# utils.trace(len(cache))

	if len(cache) > 0:
		data, timestamp = cache
		if time.time() - timestamp < CACHE_TIMEOUT:
			utils.trace("Returned cached data successfully")
			return data
		else:
			return _refresh_cache(cur=cur)

	country_codes = _country_codes_from_db(cur=cur)
	return _set_cache(data=country_codes)