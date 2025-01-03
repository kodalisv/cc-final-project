from flask import Flask, render_template, request, g, redirect, send_file, abort
import pymssql as sql
import os
import pandas as pd
from sklearn import ensemble
import datetime
import matplotlib.pyplot as plt
import io

# Database connection details
DB_SERVER = 'ccfinalprojectserver.database.windows.net'
DB_USER = 'finalprojectlogin'
DB_PASSWORD = 'weatherapp1!'
DB_NAME = 'ccfinalprojectdatabase'
MINT = 50
MAXT = 78

# Get file paths for this file and templates folder
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
def execute_query(query:str, args=()):
    db, conn = get_db()
    db.execute(query, args)
    if query.lower().startswith(("select")):
        return db.fetchall()
    else:
        conn.commit()

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
def getuid(username, password, email):
    rows = execute_query("""SELECT id FROM dbo.users WHERE uname = %s AND pword = %s and email = %s""",
                  (username, password, email))
    if len(rows) == 0:
        return -1
    return rows[0][0]

# Sets the max and min temperatures for a user, even if they're missing
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

    
# First webpage, leads instantly to register page
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

    # If user doesn't exist, add them to the database
    # Otherwise, update their hot and cold temperature limits
    userid = getuid(username, password, email)
    if userid == -1:
        execute_query("INSERT INTO dbo.users (uname, pword, email, maxt, mint) VALUES (%s, %s, %s, %s, %s)", (username, password, email, maxtemp, mintemp))
        userid = getuid(username, password, email)
    else:
        execute_query("UPDATE dbo.users SET maxt = %s, mint = %s WHERE id = %s",
                     (maxtemp, mintemp, userid))
    return redirect("/user/{}".format(userid))

# Register user in database
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get("uname")
    password = request.form.get("pword")
    email = request.form.get("email")
    userid = getuid(username, password, email)
    return redirect("/user/{}".format(userid))

# Get weather predictions and recommend them to users
@app.route('/predict/<uid>', methods=['GET'])
def getPredictions(uid):
    if int(uid) == -1:
        return "<h1>User info</h1> Incorrect username or password"
    else:
        # Get weather predictions
        minTemp, maxTemp = settemp(uid)
        predictions = predict(datetime.date.today(), 0)
        temperature = predictions['Temp'][0]
        rain = predictions['Rain'][0]
        # Create prediction string based on conditions
        pred_str = ""
        pred_str += "The predicted temperature for tomorrow is: " + str(round(temperature, 2)) + " degrees Fahrenheit. \n"
        if rain == 1:
            pred_str += "It is also expected to rain tomorrow." "\n"
        recString = ""
        match temperature:
            case temperature if temperature < minTemp:
                recString = recString + "You should bring thick clothes or a coat"
            case temperature if temperature > maxTemp:
                recString = recString + "You should wear thin clothes and drink water"
        if rain == 1:
            if recString == "":
                recString = recString + "You should bring an umbrella or a raincoat."
            else:
                recString = recString + " as well as an umbrella or raincoat."
        else:
            if recString == "":
                recString = "No recommendations. Enjoy the weather!"  
            else:
                recString += "." 
        pred_str = pred_str + recString
        return render_template('predict.html', pred=pred_str, uid=uid)

# Allow the user to sort and filter database items for analysis
@app.route('/user/<uid>', methods=['GET', 'POST'])
def sortfilter(uid):
    # If the UID is invalid, the profile doesn't exist
    if int(uid) == -1:
        return "<h1>User info</h1> Incorrect username or password"
    elif request.method == "POST":
        settemp(uid)
        # When user attempts to upload, get data from database
        cursor, connection = get_db()
        weatherResults = execute_query("SELECT * FROM dbo.HS_WEATHER;")
        columnNames = [column[0] for column in cursor.description]
        data = pd.DataFrame.from_records(weatherResults, columns=columnNames)
        
        # Create filters for each date part
        year_filter = request.form.get('year')
        if year_filter != "":
            year_filter = int(year_filter)
        month_filter = request.form.get('month')
        if month_filter != "":
            month_filter = int(month_filter)
        day_filter = request.form.get('day')
        if day_filter != "":
            day_filter = int(day_filter)

        sort_column = request.form.getlist('sort_column')
        sort_order = request.form.get('sort_order', 'asc')

        # Get database data, then sort it
        data['DATE'] = pd.to_datetime(data['DATE'])
        data['YEAR'] = data['DATE'].dt.year
        data['MONTH'] = data['DATE'].dt.month
        data['DAY'] = data['DATE'].dt.day

        # Filter database if date values exist
        if year_filter != '':
            data = data[data['YEAR'] == year_filter]
        if month_filter != '':
            data = data[data['MONTH'] == month_filter]
        if day_filter != '':
            data = data[data['DAY'] == day_filter]
        data.drop(labels=['YEAR', 'MONTH', 'DAY'], axis=1, inplace=True)

        if sort_column:
            data = data.sort_values(by=sort_column, ascending=(sort_order == 'asc'))
        # Return the dataframe as an HTML table, to display it to users
        return render_template('user.html', data=data.to_html(), uid=uid)
    settemp(uid)
    return render_template('user.html', uid=uid)

# Allow the user to sort and filter database items for analysis
@app.route('/upload/<uid>', methods=['GET', 'POST'])
def uploadData(uid):
    uploadMessage = ""
    # If the UID is invalid, the profile doesn't exist
    if int(uid) == -1:
        return "<h1>User info</h1> Incorrect username or password"
    elif request.method == "POST":
        settemp(uid)
        # When user attempts to upload, get data from database
        file = request.files["csv_file"]
        if file.filename != '':
                uploadedData = pd.read_csv(file)
                uploadedTuples = [tuple(x) for x in uploadedData.to_numpy()]
                sql_insert = "INSERT INTO dbo.HS_WEATHER (STATION, DATE, LATITUDE, LONGITUDE, " +\
                    "ELEVATION, NAME, TEMP, TEMP_ATTRIBUTES, DEWP, DEWP_ATTRIBUTES, SLP, " +\
                    "SLP_ATTRIBUTES, STP, STP_ATTRIBUTES, VISIB, VISIB_ATTRIBUTES, WDSP, " +\
                    "WDSP_ATTRIBUTES, MXSPD, GUST, MAX, MAX_ATTRIBUTES, MIN, " +\
                    "MIN_ATTRIBUTES, PRCP, PRCP_ATTRIBUTES, SNDP, FRSHTT) VALUES " +\
                    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                insert_many(sql_insert, uploadedTuples)
                uploadMessage = "Upload complete!"
    return render_template('upload.html', uid=uid, message=uploadMessage)

# Contains and processes all queries the user may enter
def get_data(query=None):
    """Fetch data from the database and return as a Pandas DataFrame."""
    q1 = "highest_lowest_temperatures"
    q2 = "average_wind_speed_hot_cold_days"
    q3 = "lowest_snow_temp_per_year"
    q4 = "dew_by_day"
    q5 = "rain_by_year"
    q6 = "predicted_temperature_next_7_days"
    q7 = "rainy_days_next_10_days"
    
    mint = app.config['MINT']
    maxt = app.config['MAXT']
    print("Query Temps: {}, {}".format(mint, maxt))   
    responses = {
        q1 : ("""SELECT MA.YEAR, MAX AS MAX_TEMP, MIN AS MIN_TEMP FROM 
            (SELECT MAX(MAX) AS MAX, YEAR(DATE) AS YEAR FROM dbo.HS_WEATHER WHERE MONTH(DATE) = MONTH(GETDATE()) AND MAX < 9999.9 GROUP BY YEAR(DATE)) MA JOIN
            (SELECT MIN(MIN) AS MIN, YEAR(DATE) AS YEAR FROM dbo.HS_WEATHER WHERE MONTH(DATE) = MONTH(GETDATE()) AND MIN < 9999.9 GROUP BY YEAR(DATE)) MI ON MA.YEAR = MI.YEAR;""",
            ("YEAR", "MAX_TEMP", "MIN_TEMP"), "bar", "", "Temperature (F)", 
            "Previous Years Temperature chart of current month", ()),
        q2:  ("""SELECT A.MONTH, A.HOT_DAYS, B.COLD_DAYS FROM
            (SELECT AVG(WDSP) AS HOT_DAYS, MONTH(DATE) AS MONTH FROM dbo.HS_WEATHER WHERE TEMP > %s AND TEMP < 9999.9 GROUP BY MONTH(DATE)) A JOIN 
            (SELECT AVG(WDSP) AS COLD_DAYS, MONTH(DATE) AS MONTH FROM dbo.HS_WEATHER WHERE TEMP < %s AND TEMP < 9999.9 GROUP BY MONTH(DATE)) B ON A.MONTH = B.MONTH ORDER BY A.MONTH;""",
            ("MONTH", "HOT_DAYS", "COLD_DAYS"), "bar", "", "Wind Speed (knots)",
            "Average wind speed for hot and cold days each month", (mint, maxt)),
        q3: ("SELECT YEAR(DATE) AS YEAR, MIN(MIN) AS MIN_TEMP FROM dbo.HS_WEATHER " +\
            "WHERE FLOOR(FRSHTT / 1000) % 10 = 1 GROUP BY YEAR(DATE) ORDER BY YEAR(DATE);", 
            ("DATE", "TEMP"), "line", "", "Temperature (F)", "Lowest temperature for snowy days by year", ()),
        q4: ("SELECT DAY(DATE) AS DAY, AVG(DEWP) AS DEWP  FROM dbo.HS_WEATHER WHERE DEWP < 9999.9 GROUP BY DAY(DATE) ORDER BY DAY",
            ("DAY", "DEWP"), "line", "", "Dew point (F)", "Average dew point by day", ()),
        q5: ("SELECT YEAR(DATE) AS YEAR, COUNT(*) AS RAIN_FREQ FROM dbo.HS_WEATHER WHERE FLOOR(FRSHTT / 10000) % 10 = 1 GROUP BY YEAR(DATE)",
            ("YEAR", "RAIN_FREQ"), "line", "", "Number of rainy days", "Number of rainy days by year", ())
    }
    predictors = {
        q6: (datetime.date.today(), 6, 2, "line", "", "Temperature (F)", "Predicted Average Temperature in the next 7 days"),
        q7: (datetime.date.today(), 9, 1, "bar", "", "Number of days", "Predicted Number of Rainy Days in the next 10 days") 
    }
    
    try:
        if query in responses.keys():
            quest = responses[query]
            print(quest[0], quest[6])
            data = execute_query(quest[0], quest[6])
            print("Query result: {}".format(data))
            cols = quest[1]
            ctype = quest[2]
            x_title = quest[3]
            y_title = quest[4]
            c_title = quest[5]
        elif query in predictors.keys():
            quest = predictors[query]
            data = predict(quest[0], quest[1])
            cols = list(data.keys())
            data[cols[0]] = list(map(lambda x: x.strftime("%m-%d"), data["Date"]))
            data[cols[1]] = list(data[cols[1]])
            #col_name = data.columns[0]
            data.pop(cols[quest[2]])
            cols.pop(quest[2])
            print(data)
            ctype = quest[3]
            x_title = quest[4]
            y_title = quest[5]
            c_title = quest[6]
            if query == q7:
                data["Rainy days"] = sum(data["Rain"])
                data["Non-rainy days"] = len(data["Rain"]) - sum(data["Rain"])
                data["Date"] = [data["Date"][0]]
                cols = list(data.keys())
                data.pop(cols[1])
                cols.pop(1)
                print(data)
        else:
            print("Invalid Question")
            data = []
            cols = set()
            ctype = ""
            x_title = ""
            y_title = ""
            c_title = ""
    except Exception as e:
        print("error: {}".format(e))
    
    return data, cols, ctype, x_title, y_title, c_title

# Plot the chart for a given set of data and return it
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

# Processes user queries and returns charts from get_chart
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
    return predictedData

if __name__ == "__main__":
    app.run(debug=True)
