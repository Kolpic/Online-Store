from flask import Flask, request, render_template_string
import psycopg2

app = Flask(__name__)

conn_params = {
    "dbname": "ekatte",
    "user": "myuser",
    "password": "1234",
    "host": "localhost"
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Search Town</title>
</head>
<body>
    <h2>Search for a Town</h2>
    <form method="post">
        <label for="town">Town Name:</label>
        <input type="text" id="town" name="town">
        <input type="submit" value="Search">
    </form>
    {% if town_info %}
        <h3>Town Information:</h3>
        <p>{{ town_info }}</p>
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def search_town():
    town_info = None
    if request.method == 'POST':
        town_name = request.form['town']
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        cur.execute("SELECT s.type, s.name, r.name, m.name FROM settlements as s JOIN regions AS r ON s.region_code = r.code JOIN municipalities as m ON s.municipalities_code = m.code WHERE s.name = %s", (town_name,))
        result = cur.fetchone()
        print(result)
        type = result[0]
        town_namee = result[1]
        obl = result[2]
        obsht = result[3]
        cur.close()
        if result:
            town_info = f"Вид: {type}, {town_namee}, област: {obl}, община: {obsht}"
        else:
            town_info = "Town not found."
    return render_template_string(HTML_TEMPLATE, town_info=town_info)

if __name__ == '__main__':
    app.run(debug=True)