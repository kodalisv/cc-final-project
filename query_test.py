import pymssql as sql

DB_SERVER = 'ccfinalprojectserver.database.windows.net'
DB_USER = 'finalprojectlogin'
DB_PASSWORD = 'weatherapp1!'
DB_NAME = 'ccfinalprojectdatabase'


query = """UPDATE dbo.users SET maxt = %s, mint = %s WHERE id = %s"""

args = (50, 75, 12)

conn = sql.connect(server=DB_SERVER, 
                    user=DB_USER, 
                    password=DB_PASSWORD, 
                    database=DB_NAME)
cursor = conn.cursor()
cursor.execute(query, args)
if query.lower().startswith(("update", "insert")):
    conn.commit()
else:
    print(cursor.fetchall())