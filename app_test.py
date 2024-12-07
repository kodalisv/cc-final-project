from flask import Flask, render_template, request, g, redirect, send_from_directory, abort, jsonify
import pymssql as sql
import os
import pandas as pd
from sklearn import model_selection, ensemble
import datetime

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
        print(conn, db)
        print(conn._conn.connected)
    return db, conn

# Run queries
def execute_query(query, args=()):
    db, conn = get_db()
    db.execute(query, args)
    rows=db.fetchall()
    conn.commit()
    return rows

# Run other queries
def insert_query(query, args=()):
    db, conn = get_db()
    db.execute(query, args)
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
        insert_query("INSERT INTO dbo.users (uname, pword, email, maxt, mint) VALUES (%s, %s, %s, %s, %s)", (username, password, email, maxtemp, mintemp))
        userid = getuid(username, password)
    else:
        insert_query("UPDATE dbo.users SET maxt = %s, mint = %s WHERE id = %s",
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
            if file.filename == '':
                cursor, connection = get_db()
                weatherResults = execute_query("SELECT * FROM dbo.HS_WEATHER;")
                columnNames = [column[0] for column in cursor.description]
                data = pd.DataFrame.from_records(weatherResults, columns=columnNames)

                sort_column = request.form.get('sort_column')
                sort_order = request.form.get('sort_order', 'asc')

                if sort_column:
                    data = data.sort_values(by=sort_column, ascending=(sort_order == 'asc'))
                return render_template('user.html', data=data.to_html())

            try:
                df = pd.read_csv(file)
                # Allow sorting
                sort_column = request.form.get('sort_column')
                sort_order = request.form.get('sort_order', 'asc')

                if sort_column:
                    df = df.sort_values(by=sort_column, ascending=(sort_order == 'asc'))
                # Process the DataFrame here (e.g., display it, save it to a database)
                return render_template('user.html', data=df.to_html())
            except Exception as e:
                return f'Error processing file: {e}'
        return render_template('user.html')


def get_data(query=None, args=()):
    """Fetch data from the database and return as a Pandas DataFrame."""
    responses = {
        "what were the highest and lowest temperatures for this month "
        "in the previous years": "SELECT MAX(TEMP) AS MAX_TEMP, MIN(TEMP) AS MIN_TEMP FROM "
                                "(SELECT TEMP, DATE FROM dbo.HS_WEATHER WHERE MONTH(DATE) = MONTH(GETDATE()) "
                                "AND YEAR(DATE) = YEAR(GETDATE()) - 1) LM;"
    }
    query = responses.get(query, "")
    return execute_query(query, args)

@app.route('/query', methods=['POST'])
def query():
    """Handle user queries and return data as chart values."""
    user_query = request.json.get('query')
    try:
        data = get_data(user_query)
        categories = data['MAX_TEMP'].tolist()
        values = data['MIN_TEMP'].tolist()
        response = {"categories": categories, "values": values}
    except Exception as e:
        response = {"error": str(e)}
    return response


@app.route("/predict/<uid>")
def predict(uid):
    cursor, connection = get_db()
    currentDate = datetime.datetime.now()
    year = currentDate.year
    month = currentDate.month
    day = currentDate.day
    # Execute a query
    weatherResults = execute_query("SELECT * FROM dbo.HS_WEATHER;")
    # Get column names
    columnNames = [column[0] for column in cursor.description]
    # Get user data
    coldLimit = execute_query("SELECT mint FROM dbo.users WHERE id=%s;", (uid))
    hotLimit = execute_query("SELECT maxt FROM dbo.users WHERE id=%s;", (uid))

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
    Y_set_temp = data["NEXT_TEMP"]
    X_train_temp, X_test_temp, y_train_temp, y_test_temp = model_selection.train_test_split(X_set_temp, Y_set_temp, test_size=0.2)

    X_set_rain = data.drop(["NEXT_TEMP", "RAIN"], axis=1)
    Y_set_rain = data["RAIN"]
    X_train_rain, X_test_rain, y_train_rain, y_test_rain = model_selection.train_test_split(X_set_rain, Y_set_rain, test_size=0.2)

    # Build and run model
    tempForest = ensemble.RandomForestRegressor(max_depth=2, random_state=0)
    tempForest.fit(X_train_temp, y_train_temp)

    rainForest = ensemble.RandomForestClassifier()
    rainForest.fit(X_train_rain, y_train_rain)

    # Predict temperature
    # Filter historic data to only matching date
    prevData = data.loc[data["DAY"] == day]
    prevData = prevData.loc[prevData['MONTH'] == month]
    prevData.drop(["NEXT_TEMP", "RAIN"], axis=1, inplace=True)
    # Create one-row dataframe on average day (from historical data)
    average_day = pd.DataFrame([prevData.mean()])
    average_day['YEAR'] = year
    # Run prediction on average day
    predictedTemp = tempForest.predict(average_day)[0]
    predictedRain = rainForest.predict(average_day)[0]

    # Create recommendation based on predictions
    recString = ""
    match predictedTemp:
        case predictedTemp if predictedTemp < coldLimit:
            recString = recString + "You should bring a coat"
        case predictedTemp if predictedTemp > hotLimit:
            recString = recString + "You should bring some water"
    if predictedRain == 1:
        if recString == "":
            recString = recString + "You should bring an umbrella"
        else:
            recString = recString + " and an umbrella"
    else:
        if recString == "":
            recString = "No recommendations. Enjoy the weather!"
    return recString

if __name__ == "__main__":
    app.run(debug=True)
