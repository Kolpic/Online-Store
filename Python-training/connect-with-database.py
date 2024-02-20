import psycopg2

database = "helloworld"
user = "myuser"
password = "1234"
host = "localhost"

conn = psycopg2.connect(dbname = database, user=user, password=password, host=host)

cur = conn.cursor()

cur.execute("SELECT message FROM messages")

row = cur.fetchone()

print(row[0])

cur.close()
conn.close()