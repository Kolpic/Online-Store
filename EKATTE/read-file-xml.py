import pandas
import psycopg2
from psycopg2.extras import execute_batch

excel_file_obl = 'excel/ek_obl.xlsx'
df = pandas.read_excel(excel_file_obl, skiprows=3,usecols=['Име на областния център','Код на областта','Име на областта'])

conn_params = {
    "dbname":"ekatte",
    "user": "myuser",
    "password": "1234",
    "host": "localhost"
}

conn = psycopg2.connect(**conn_params)
cur = conn.cursor()

insert_query = 'INSERT INTO regions(center_name, code, name) VALUES (%s, %s, %s)'

data_tuples = [tuple(x) for x in df.to_numpy()]
print(data_tuples)

execute_batch(cur, insert_query, data_tuples)

conn.commit()
cur.close()