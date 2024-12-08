import pymssql as sql

DB_SERVER = 'ccfinalprojectserver.database.windows.net'
DB_USER = 'finalprojectlogin'
DB_PASSWORD = 'weatherapp1!'
DB_NAME = 'ccfinalprojectdatabase'


query = """SELECT A.MONTH, A.HOT_DAYS, B.COLD_DAYS FROM
(SELECT AVG(WDSP) AS HOT_DAYS, MONTH(DATE) AS MONTH FROM dbo.HS_WEATHER WHERE TEMP > %s GROUP BY MONTH(DATE)) A JOIN 
(SELECT AVG(WDSP) AS COLD_DAYS, MONTH(DATE) AS MONTH FROM dbo.HS_WEATHER WHERE TEMP < %s GROUP BY MONTH(DATE)) B ON A.MONTH = B.MONTH;"""

args = (50, 75)

conn = sql.connect(server=DB_SERVER, 
                    user=DB_USER, 
                    password=DB_PASSWORD, 
                    database=DB_NAME)
cursor = conn.cursor()
cursor.execute(query, args)
print(cursor.fetchall())