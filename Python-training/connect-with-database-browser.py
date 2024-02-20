from flask import Flask
import psycopg2

app = Flask(__name__)

@app.route('/')
def hello_world():
    database = "helloworld"
    user = "myuser"
    password = "1234"
    host = "localhost"

    conn = psycopg2.connect(dbname = database, user=user, password=password, host=host)

    cur =conn.cursor()
    cur.execute("SELECT message FROM messages LIMIT 1")

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row[0] if row else 'No message found'

    if __name__ == '__main__':
        app.run(debug=True, port=5000)