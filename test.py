from flask import Flask, render_template, request, g, redirect, send_from_directory
import sql as sql
import os
import pandas as pd
from sklearn import model_selection, ensemble

#app = Flask(__name__)

# Database connection details
DB_SERVER = 'ccfinalprojectserver.database.windows.net'
DB_USER = 'finalprojectlogin'
DB_PASSWORD = 'weatherapp1!'
DB_NAME = 'ccfinalprojectdatabase'

project_root = os.path.dirname(__file__)
template_path = os.path.join(project_root, './')
EMPTYFILE = (' ',0)

app = Flask(__name__, template_folder=template_path)
app.config.from_object(__name__)

# Connect to database
def connect_to_database():
    return sql.connect(app.config['DB_SERVER'], 
                       app.config['DB_USER'], 
                       app.config['DB_PASSWORD'], 
                       app.config['DB_NAME'])

# Run Select queries
def execute_query(query, args=()):
    db = get_db()
    rows = db.execute(query, args).fetchall()
    db.commit()
    return rows

# Run other queries
def insert_query(query, args=()):
    db = get_db()
    db.execute(query, args)
    db.commit()
    return

# Get Database object
def get_db():
    db = getattr(g, 'db', None)
    if db is None:
        db = g.db = connect_to_database()
    return db

# Disconnect from database
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

# Get user id from username and password
def getuid(username, password):
    rows = execute_query("""SELECT id FROM users WHERE uname = ? AND pword = ?""",
                  (username, password))
    if len(rows) == 0:
        return -1
    return rows[0][0]


# Register user in database
@app.route('/', methods=["GET", 'POST'])
def register():
    username = request.form.get("username")
    password = request.form.get("password")

    userid = getuid(username, password)
    if userid == -1:
        insert_query("INSERT INTO users (uname, pword) VALUES (?, ?, ?, ?, ?, ?)", (username, password))
        userid = getuid(username, password)
    else:
        insert_query("UPDATE users SET fname = ?, lname = ?, email = ? WHERE id = ?",
                     (username, password, userid))

    return redirect("/user/{}".format(userid))

@app.route('/user/<uid>', methods=["GET", 'POST'])
def main(uid):
    weather_data = {"temperature: 70"}
    return render_template(
        "login.html",
        weather_data=weather_data
    )

@app.route("/predict/<uid>/<year>/<month>/<day>")
def predict(uid, year, month, day):
    # Connect to the database
    connection = sql.connect(
        server=DB_SERVER,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

    # Create a cursor
    cursor = connection.cursor()

    # Execute a query
    cursor.execute("SELECT * FROM dbo.HS_WEATHER;")

    # Get column names
    columnNames = [column[0] for column in cursor.description]

    # Fetch the data
    queryData = cursor.fetchall()

    # Close the connection and cursor
    cursor.close()
    connection.close()

    # Import data
    data = pd.DataFrame.from_records(queryData, columns=columnNames)

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
    coldLimit = 40
    hotLimit = 80
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
