from psycopg2.extensions import adapt, register_adapter, AsIs

class Point(obj):

	def __init__(self, x):
		self.x = x

def adapt_point(point):
	x = adapt(point.x).getquoted()

	return AsIs("'(%s)'" % (x,))

register_adapter(Point, adapt_point)