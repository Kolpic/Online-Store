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
    {% if request.method == 'POST' %}
        {% if results is not none and results %}
            <h3>Town Information:</h3>
            <table border="1">
                <tr>
                    <th>Type (Вид) </th>
                    <th>Name (Име) </th>
                    <th>Region (Област) </th>
                    <th>Municipality (Община)</th>
                    <th>Town hall (Име на кметството)</th>
                </tr>
                {% for row in results %}
                <tr>
                    <td>{{ row[0] }}</td>
                    <td>{{ row[1] }}</td>
                    <td>{{ row[2] }}</td>
                    <td>{{ row[3] }}</td>
                    <td>{{ row[4] }}</td>
                </tr>
                {% endfor %}
            </table>
        {% else %}
            <p>No results found.</p>
        {% endif %}
    {% endif %}

    {% if request.method == 'POST' %}
        {% if regions_count is not none %}
        <h3>Total Number of Regions: {{ regions_count }} </h3>
        {% endif %}
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def search_town():
    results = None
    regions_count = None

    if request.method == 'POST':
        town_name = request.form['town']
        print(town_name)
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        # cur.execute("SELECT s.type, s.name, r.name, m.name FROM settlements as s JOIN regions AS r ON s.region_code = r.code JOIN municipalities as m ON s.municipalities_code = m.code WHERE s.name = %s", (town_name,))
        cur.execute("""SELECT s.type, s.name, r.name, m.name, COALESCE(th.name, '-') 
                    FROM settlements as s 
                    JOIN regions AS r ON s.region_code = r.code 
                    JOIN municipalities as m ON s.municipalities_code = m.code 
                    LEFT JOIN town_halls AS th ON s.town_hall_code = th.code 
                    WHERE s.name = %s""", (town_name,))
        results = cur.fetchall()
        cur.close()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(name) FROM regions")
        regions_count = cur.fetchone()[0]

        print(len(results))
        print(regions_count)
        cur.close()
        conn.close()
        print(results)
        for row in results:
            type = row[0]
            town_namee = row[1]
            obl = row[2]
            obsht = row[3]
            # kmets = row[4]
            if row:
                towns_info = f"Вид: {type}, {town_namee}, област: {obl}, община: {obsht}"
                print(towns_info)
            else:
                towns_info = "Town not found."

    return render_template_string(HTML_TEMPLATE, results=results, regions_count=regions_count)

if __name__ == '__main__':
    app.run(debug=True)