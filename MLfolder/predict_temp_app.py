import pandas as pd
from sklearn import ensemble, model_selection
import pymssql
from flask import Flask, redirect, url_for, request

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def start():
    return redirect(url_for("predict", user="test", year=2024, month=12, day=25))

# Take user's username, password, email
# @app.route("/register", methods=['POST'])
# def register():
#     return url_for("register")

# User logs in with username and password
# @app.route("/login", methods=['GET', 'POST'])
# def login():
#     return url_for("register")

# Decide which day to check, and thresholds for cold and hot days
@app.route("/configure/<user>", methods=['GET', 'POST'])
def configure(user):
    return "Hello " + str(user)

@app.route("/predict/<user>/<year>/<month>/<day>")
def predict(user, year, month, day):
    server = 'ccfinalprojectserver.database.windows.net' 
    database = 'ccfinalprojectdatabase'
    username = 'finalprojectlogin' 
    password = 'weatherapp1!' 

    # Connect to the database
    connection = pymssql.connect(
        server=server,
        user=username,
        password=password,
        database=database
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

if __name__ == '__main__':
    app.run(debug=True)