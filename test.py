from flask import Flask, render_template, request
import pymssql
import pandas as pd
from sklearn import model_selection, ensemble


# Database connection details
DB_SERVER = 'ccfinalprojectserver.database.windows.net'
DB_USER = 'finalprojectlogin'
DB_PASSWORD = 'weatherapp1!'
DB_NAME = 'ccfinalprojectdatabase'

if __name__ == "__main__":
    # Connect to the database
    connection = pymssql.connect(
        server=DB_SERVER,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

    # Create a cursor
    cursor = connection.cursor()
    username = 'csa'
    password = 'test'
    maxtemp = 78
    mintemp = 50
    # Execute a query
    cursor.execute("INSERT INTO dbo.users (uname, pword, maxt, mint) VALUES (%s, %s, %s, %s);", (username, password, maxtemp, mintemp))

    # Get column names
    columnNames = [column[0] for column in cursor.description]

    # Fetch the data
    queryData = cursor.fetchall()

    # Close the connection and cursor
    cursor.close()
    connection.close()
    print(queryData)