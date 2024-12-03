import pymssql

if __name__ == "__main__":
    server = 'ccfinalprojectserver.database.windows.net'
    user = 'finalprojectlogin'
    password = 'weatherapp1!'
    db = 'ccfinalprojectdatabase'
    conn = pymssql.connect(server, user, password, db)
    cursor = conn.cursor(as_dict=True)

    cursor.execute('SELECT WDSP, DATE FROM dbo.HS_WEATHER WHERE TEMP > 76;')
    for row in cursor:
        print(row)

    conn.close()