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
MINT = 50
MAXT = 78

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

def settemp(uid):
    rows = execute_query("""SELECT mint, maxt FROM dbo.users WHERE id = %s""", (uid,))
    if len(rows) == 0:
        app.config['MINT'] = 50
        app.config['MAXT'] = 78
    else:
        app.config['MINT'] = rows[0][0]
        app.config['MAXT'] = rows[0][1]
    print("temps: {}, {}".format(app.config['MINT'], app.config['MAXT']))
    return app.config['MINT'], app.config['MAXT']

    
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

@app.route('/user/<uid>')
def main(uid):
    if uid == -1:
        return "<h1>User info</h1> Incorrect username or password"
    else:
        settemp(uid)
        return render_template('user.html')

@app.route('/user/<uid>', methods=['POST'])
def uploadcsv(uid):
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


def get_data(query=None):
    """Fetch data from the database and return as a Pandas DataFrame."""
    q1 = "highest_lowest_temperatures"
    q2 = "average_wind_speed_hot_cold_days"
    q3 = "coldest_day_this_month"
    q4 = "dew_by_day"
    q5 = "rain_by_month"
    
    mint = app.config['MINT']
    maxt = app.config['MAXT']
    print("Query Temps: {}, {}".format(mint, maxt))   
    responses = {
        q1 : ("SELECT YEAR(DATE) AS YEAR, MAX(TEMP) AS MAX_TEMP, MIN(TEMP) AS MIN_TEMP FROM " +\
        "(SELECT TEMP, DATE FROM dbo.HS_WEATHER WHERE MONTH(DATE) = MONTH(GETDATE())) LM " +\
        "GROUP BY YEAR(DATE);", ("YEAR", "MAX_TEMP", "MIN_TEMP"), "bar", "", "Temperature (F)", 
        "Previous Years Temperature chart of current month", ()),
        q2:  ("""SELECT A.MONTH, A.HOT_DAYS, B.COLD_DAYS FROM
(SELECT AVG(WDSP) AS HOT_DAYS, MONTH(DATE) AS MONTH FROM dbo.HS_WEATHER WHERE TEMP > %s GROUP BY MONTH(DATE)) A JOIN 
(SELECT AVG(WDSP) AS COLD_DAYS, MONTH(DATE) AS MONTH FROM dbo.HS_WEATHER WHERE TEMP < %s GROUP BY MONTH(DATE)) B ON A.MONTH = B.MONTH ORDER BY A.MONTH;""",
            ("MONTH", "HOT_DAYS", "COLD_DAYS"), "bar", "", "Wind Speed (knots)",
            "Average wind speed for hot and cold days each month", (mint, maxt)),
        q3: ("SELECT A.YEAR, B.DAY FROM (SELECT MIN(TEMP) AS TEMP, YEAR(DATE) AS YEAR FROM dbo.HS_WEATHER " +\
            "WHERE MONTH(DATE) = MONTH(GETDATE()) GROUP BY YEAR(DATE)) A JOIN (SELECT TEMP, " +\
            "DAY(DATE) AS DAY, YEAR(DATE) AS YEAR FROM dbo.HS_WEATHER) B ON A.YEAR = B.YEAR " +\
            "AND A.TEMP = B.TEMP;", ("YEAR", "DAY"), "bar", "", "Day of month",
            "Coldest day this month across all years", ()),
        q4: ("SELECT DAY(DATE) AS DAY, AVG(DEWP) AS DEWP  FROM dbo.HS_WEATHER GROUP BY DAY(DATE) ORDER BY DAY",
            ("DAY", "DEWP"), "line", "", "Dew point", "Average dew point by day", ()),
        q5: ("SELECT YEAR(DATE) AS YEAR, COUNT(*) AS RAIN_FREQ FROM dbo.HS_WEATHER WHERE FLOOR(FRSHTT / 10000) % 10 = 1 GROUP BY YEAR(DATE)",
            ("YEAR", "RAIN_FREQ"),"line", "", "Number of rainy days", "Number of rainy days by year", ())
    }
    try:
        
        quest = responses[query]
        args = quest[6]
        print(quest[0], args)
        data = execute_query(quest[0], args)
        cols = quest[1]
        ctype = quest[2]
        x_title = quest[3]
        y_title = quest[4]
        c_title = quest[5]
    except KeyError as e:
        data = []
        cols = set()
        ctype = ""
        x_title = ""
        y_title = ""
        c_title = ""
    
    return data, cols, ctype, x_title, y_title, c_title

def get_chart(data, cols, ctype = "bar", x_title="", y_title="", c_title="Data Chart"):
    """Generate a chart using Matplotlib."""
    df = pd.DataFrame.from_records(data, columns=cols)
    emp = lambda x, y: x if x != "" else y
    print(df)
    
    match ctype:
        case "bar":
            df.plot(x=cols[0], kind=ctype, stacked=False)
        case "line":
            df.plot(x=cols[0], y=cols[1], ax=plt.gca())
            
    plt.xticks(rotation=0, ha='right')
    plt.xlabel(emp(x_title, cols[0]))
    plt.ylabel(y_title)
    plt.title(c_title)
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
        data, cols, ctype, x_title, y_title, c_title = get_data(user_query)
        chart = get_chart(data, cols, ctype, x_title, y_title, c_title)
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
