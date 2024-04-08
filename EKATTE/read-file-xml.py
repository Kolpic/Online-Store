import pandas
import psycopg2
from psycopg2.extras import execute_batch
import time

excel_file_obl = 'excel/ek_obl.xlsx'
excel_file_obst = 'excel/ek_obst.xlsx'
excel_file_kemt = 'excel/ek_kmet.xlsx'
excel_file_sett = 'excel/ek_atte.xlsx'

df_obl = pandas.read_excel(excel_file_obl, skiprows=3,usecols=['Име на областния център','Код на областта','Име на областта','NUTS1','NUTS2','NUTS3'])
df_obst = pandas.read_excel(excel_file_obst, skiprows=3,usecols=['Код на общината','Код на общинския център','Име на общинския център', 'Име на общината', 'NUTS1','NUTS2','NUTS3'])
df_kmet = pandas.read_excel(excel_file_kemt, skiprows=3, usecols=['Идентификационен код', 'Име','NUTS1','NUTS2','NUTS3'])
df_sett = pandas.read_excel(excel_file_sett, skiprows=3, usecols=['Вид', 'Име на населено място', 'Код на областта', 'Код на общината', 'Кметство', 'NUTS1','NUTS2','NUTS3'])

# config
conn_params = { 
    "dbname":"ekatte",
    "user": "myuser",
    "password": "1234",
    "host": "localhost"
}

conn = psycopg2.connect(**conn_params)
cur = conn.cursor()

insert_query_obl = 'INSERT INTO regions(center_name, code, name, NUTS1, NUTS2, NUTS3) VALUES (%s, %s, %s, %s, %s, %s)'
insert_query_obst = 'INSERT INTO municipalities(code, center_code, center_name, name, NUTS1, NUTS2, NUTS3) VALUES (%s, %s, %s, %s, %s, %s, %s)'
insert_query_kmet = 'INSERT INTO town_halls(code, name, NUTS1, NUTS2, NUTS3) VALUES (%s, %s, %s, %s, %s)'
insert_query_sett = 'INSERT INTO settlements(type, name, region_code, municipalities_code, town_hall_code, nuts1, nuts2, nuts3) VALUES (%s, %s, %s, %s,%s, %s, %s, %s)'

data_tuples_obl = [tuple(x) for x in df_obl.to_numpy()]
databa_tuples_obst = [tuple(x) for x in df_obst.to_numpy()]
data_tuples_kmet = [tuple(x) for x in df_kmet.to_numpy()]
data_tuples_sett = [tuple(x) for x in df_sett.to_numpy()]

print(data_tuples_obl)
print(databa_tuples_obst)
print(data_tuples_kmet)
print(data_tuples_sett)

start_time = time.time()

"""
Consider a DataFrame df with columns ['A', 'B', 'C']. 
When you call df.itertuples(index=True), 
the resulting tuples will look something like (index, A_value, B_value, C_value). 
If your INSERT statement is designed to insert values into three columns 
corresponding to A, B, and C, the presence of the index would cause an error or mismatch.
However, with df.itertuples(index=False), the tuples are 
(A_value, B_value, C_value), aligning perfectly with the expected structure for insertion.
"""

for row in df_obl.itertuples(index=False):
    cur = conn.cursor()
    cur.execute(insert_query_obl, row)
    cur.close()
for row in df_obst.itertuples(index=False):
    cur = conn.cursor()
    cur.execute(insert_query_obst, row)
    cur.close()
for row in df_kmet.itertuples(index=False):
    cur = conn.cursor()
    cur.execute(insert_query_kmet,row)
    cur.close()
for row in df_sett.itertuples(index=False):
    cur = conn.cursor()
    cur.execute(insert_query_sett, row)
    cur.close()

# execute_batch(cur, insert_query_obl, data_tuples_obl)
# execute_batch(cur, insert_query_obst, databa_tuples_obst)
# execute_batch(cur, insert_query_kmet, data_tuples_kmet)
# execute_batch(cur, insert_query_sett, data_tuples_sett)

end_time = time.time()

filled_database_time = end_time - start_time
print("Time for database to be filled is: " + str(filled_database_time))

conn.commit()
cur.close()