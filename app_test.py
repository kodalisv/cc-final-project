from flask import Flask, render_template, request, g, redirect, send_file
import pymssql as sql
import os
import pandas as pd
from sklearn import ensemble
import datetime
import matplotlib.pyplot as plt
import io

#app = Flask(__name__)

# Database connection details
DB_SERVER = 'ccfinalprojectserver.database.windows.net'
DB_USER = 'finalprojectlogin'
DB_PASSWORD = 'weatherapp1!'
DB_NAME = 'ccfinalprojectdatabase'

project_root = os.path.dirname(__file__)
template_path = os.path.join(project_root, './templates')

app = Flask(__name__, template_folder=template_path)
app.config.from_object(__name__)

# Connect to database
def connect_to_database():
    print(app.config['DB_SERVER'], app.config['DB_USER'], app.config['DB_PASSWORD'], app.config['DB_NAME'])
    return sql.connect(server=app.config['DB_SERVER'], 
                       user=app.config['DB_USER'], 
                       password=app.config['DB_PASSWORD'], 
                       database=app.config['DB_NAME'])

# Get Database object
def get_db():
    db = getattr(g, 'db', None)
    conn = getattr(g, 'conn', None)
    if db is None:
        print("New connection")
        conn = g.conn = connect_to_database()
        db = g.db = conn.cursor() 
        #print(conn, db)
        #print(conn._conn.connected)
    return db, conn

# Run queries
def execute_query(query, args=()):
    db, conn = get_db()
    db.execute(query, args)
    rows=db.fetchall()
    conn.commit()
    return rows

# Run other queries
def insert_many(query, args=[]):
    db, conn = get_db()
    db.executemany(query, args)
    conn.commit()
    return

# Disconnect from database
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, 'db', None)
    conn = getattr(g, 'conn', None)
    if db is not None:
        db.close()
        conn.close()

# Get user id from username and password
def getuid(username, password):
    rows = execute_query("""SELECT id FROM dbo.users WHERE uname = %s AND pword = %s""",
                  (username, password))
    if len(rows) == 0:
        return -1
    return rows[0][0]

# First webpage
@app.route('/')
def index():
    return render_template('index.html')

# Register user in database
@app.route('/register', methods=['POST'])
def register():
    username = request.form.get("uname")
    password = request.form.get("pword")
    email = request.form.get("email")
    maxtemp = int(request.form.get("maxt"))
    mintemp = int(request.form.get("mint"))
    print(username, password, email, maxtemp, mintemp)

    userid = getuid(username, password)
    if userid == -1:
        execute_query("INSERT INTO dbo.users (uname, pword, email, maxt, mint) VALUES (%s, %s, %s, %s, %s)", (username, password, email, maxtemp, mintemp))
        userid = getuid(username, password)
    else:
        execute_query("UPDATE dbo.users SET maxt = %s, mint = %s WHERE id = %s",
                     (maxtemp, mintemp, userid))
    return redirect("/user/{}".format(userid))

# Register user in database
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get("uname")
    password = request.form.get("pword")
    userid = getuid(username, password)
    return redirect("/user/{}".format(userid))

@app.route('/user/<uid>', methods=['GET', 'POST'])
def main(uid):
    if uid == -1:
        return "<h1>User info</h1> Incorrect username or password"
    else:
        if request.method == 'POST':
            file = request.files['csv_file']
            cursor, connection = get_db()
            weatherResults = execute_query("SELECT * FROM dbo.HS_WEATHER;")
            columnNames = [column[0] for column in cursor.description]
            data = pd.DataFrame.from_records(weatherResults, columns=columnNames)

            sort_column = request.form.get('sort_column')
            sort_order = request.form.get('sort_order', 'asc')
            if file.filename == '':
                if sort_column:
                    data = data.sort_values(by=sort_column, ascending=(sort_order == 'asc'))
                return render_template('user.html', data=data.to_html())

            try:
                uploadedData = pd.read_csv(file)
                uploadedTuples = [tuple(x) for x in uploadedData.to_numpy()]
                sql_insert = "INSERT INTO dbo.HS_WEATHER (STATION, DATE, LATITUDE, LONGITUDE, " +\
                    "ELEVATION, NAME, TEMP, TEMP_ATTRIBUTES, DEWP, DEWP_ATTRIBUTES, SLP, " +\
                    "SLP_ATTRIBUTES, STP, STP_ATTRIBUTES, VISIB, VISIB_ATTRIBUTES, WDSP, " +\
                    "WDSP_ATTRIBUTES, MXSPD, GUST, MAX, MAX_ATTRIBUTES, MIN, " +\
                    "MIN_ATTRIBUTES, PRCP, PRCP_ATTRIBUTES, SNDP, FRSHTT) VALUES " +\
                    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                cursor.executemany(sql_insert, uploadedTuples)
                connection.commit()
                # Allow sorting
                sort_column = request.form.get('sort_column')
                sort_order = request.form.get('sort_order', 'asc')

                data = execute_query("SELECT * FROM dbo.HS_WEATHER;")
                dataframe = pd.DataFrame.from_records(data, columns=columnNames)
                if sort_column:
                    dataframe = dataframe.sort_values(by=sort_column, ascending=(sort_order == 'asc'))
                # Process the DataFrame here (e.g., display it, save it to a database)
                return render_template('user.html', data=dataframe.to_html())
            except Exception as e:
                return f'Error processing file: {e}'
        return render_template('user.html')


def get_data(query=None, args=()):
    """Fetch data from the database and return as a Pandas DataFrame."""
    q1 = "what were the highest and lowest temperatures for this month in the previous years"
    q2 = ""
    
    responses = {
        q1 : "SELECT MAX(TEMP) AS MAX_TEMP, " +\
        "MIN(TEMP) AS MIN_TEMP FROM " +\
        "(SELECT TEMP, DATE FROM dbo.HS_WEATHER WHERE MONTH(DATE) = MONTH(GETDATE()) " +\
        "AND YEAR(DATE) = YEAR(GETDATE()) - 1) LM;"
    }
    cols = {
        q1: ("MAX_TEMP", "MIN_TEMP")
    }
    
    try:
        sql_query = responses[query]
        sql_cols = cols[query]
    except KeyError as e:
        sql_query = "Invalid Question"
        sql_cols = set()
    print(query, sql_query, sql_cols)
    
    return execute_query(sql_query, args), sql_cols

def get_chart(data, cols, ctype):
    """Generate a chart using Matplotlib."""
    df = pd.DataFrame.from_records(data, columns=cols)
    plt.figure(figsize=(10, 6))
    
    match ctype:
        case "bar":
            plt.bar(df[cols[0]], df[cols[1]], color='skyblue')
            plt.title('Data Chart', fontsize=16)
            plt.xlabel(cols[0], fontsize=14)
            plt.ylabel(cols[1], fontsize=14)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()
    return img


@app.route('/query', methods=['POST'])
def query():
    """Handle user queries and return data as chart values."""
    user_query = request.json.get('query').lower()
    print("query: {}".format(user_query))
    try:
        data, cols = get_data(user_query)
        chart = get_chart(data, cols,'bar')
        return send_file(chart, mimetype='image/png')
    except Exception as e:
        response = {"error": str(e)}
    return response

# Given a date, returns temp/rain prediction for the next day and (daysAhead) more days after that
def predict(date, daysAhead):
    # Create date list
    dateList = []
    for x in range(0, daysAhead+1):
        dateList.append(date + datetime.timedelta(x))
    
    cursor, connection = get_db()
    # Execute a query
    weatherResults = execute_query("SELECT * FROM dbo.HS_WEATHER;")
    # Get column names
    columnNames = [column[0] for column in cursor.description]

    # Import data
    data = pd.DataFrame.from_records(weatherResults, columns=columnNames)

    # Modify data
    # Separate dates first
    data['DATE'] = pd.to_datetime(data['DATE'])
    data['YEAR'] = data['DATE'].dt.year
    data['MONTH'] = data['DATE'].dt.month
    data['DAY'] = data['DATE'].dt.day

    # Create RAIN column, to see if it has rained
    data['RAIN'] = [1 if int(x / 10000) % 10 == 1 else 0 for x in data['FRSHTT']]

    # Remove unneeded columns
    removedColumns = ["STATION", "DATE", "LATITUDE", "LONGITUDE", "ELEVATION", "NAME", "TEMP_ATTRIBUTES", "DEWP_ATTRIBUTES", "SLP_ATTRIBUTES", "STP_ATTRIBUTES", "VISIB_ATTRIBUTES", "WDSP_ATTRIBUTES", "MAX_ATTRIBUTES", "MIN_ATTRIBUTES", "PRCP_ATTRIBUTES", "SNDP", "FRSHTT"]
    data.drop(labels=removedColumns, axis=1, inplace=True)

    # Fix faulty STP column 
    data.loc[data['STP'] < 100, "STP"] = data['STP'] + 1000

    # Remove missing data in GUST and PRCP
    data = data[data['PRCP'] != 99.99]
    data = data[data['GUST'] != 999.9]

    # Add temperature difference between days
    data["NEXT_TEMP"] = data["TEMP"].shift(-1)
    # Remove the last column (it has no NEXT_TEMP)
    data = data.iloc[:-1]

    # Create train test splits
    X_set_temp = data.drop(["NEXT_TEMP", "RAIN"], axis=1)
    y_set_temp = data["NEXT_TEMP"]

    X_set_rain = data.drop(["NEXT_TEMP", "RAIN"], axis=1)
    y_set_rain = data["RAIN"]

    # Build and run model
    tempForest = ensemble.RandomForestRegressor(max_depth=2, random_state=0)
    tempForest.fit(X_set_temp, y_set_temp)

    rainForest = ensemble.RandomForestClassifier()
    rainForest.fit(X_set_rain, y_set_rain)

    # Predict temperature
    # Group days into average of day + month combinations
    data["COM_DATE"] = list(zip(data['DAY'], data['MONTH']))
    avgDayDF = data.groupby(["COM_DATE"]).mean().reset_index()
    # Create list of dates to keep
    combinedDateList = []
    for y in range(0, len(dateList)):
        combinedDateList.append((dateList[y].day, dateList[y].month))
    # Filter anything not in the list
    filteredDF = avgDayDF[avgDayDF["COM_DATE"].isin(combinedDateList)]
    filteredDF.drop(["NEXT_TEMP", "RAIN", "COM_DATE"], axis=1, inplace=True)
    # Make predictions
    predictedTemp = tempForest.predict(filteredDF)
    predictedRain = rainForest.predict(filteredDF)
    # Store predictions for each day in dataframe
    predictedData = {"Date": dateList, "Temp": predictedTemp, "Rain": predictedRain}
    predictDF = pd.DataFrame(predictedData)
    return predictDF

@app.route('/testing')
def predictTest():
    return predict(datetime.datetime(2024, 12, 25), 8).to_string()

if __name__ == "__main__":
    app.run(debug=True)
