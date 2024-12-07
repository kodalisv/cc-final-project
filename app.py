from flask import Flask, render_template, request
import pymssql

app = Flask(__name__)

# NWS API Base URL
NWS_API_BASE_URL = "https://api.weather.gov/points"

# Predefined list of major cities in Ohio with their coordinates
OHIO_CITIES = {
    "cincinnati": {"lat": 39.1031, "lon": -84.5120},
    "cleveland": {"lat": 41.4993, "lon": -81.6944},
    "columbus": {"lat": 39.9612, "lon": -82.9988},
    "dayton": {"lat": 39.7589, "lon": -84.1916},
    "toledo": {"lat": 41.6528, "lon": -83.5379},
    "akron": {"lat": 41.0814, "lon": -81.5190},
    "youngstown": {"lat": 41.0998, "lon": -80.6495},
    "mansfield": {"lat": 40.7584, "lon": -82.5154},
    "springfield": {"lat": 39.9242, "lon": -83.8088},
}

@app.route("/", methods=["GET", "POST"])
def login():
    weather_data = None
    error_message = None
    recommendations = None
    entered_city = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        entered_city = request.form.get("city")  # User input for the city
        min_temp = request.form.get("min_temp")  # User's minimum comfortable temperature
        max_temp = request.form.get("max_temp")  # User's maximum comfortable temperature

        if username and password and entered_city and min_temp and max_temp:
            try:
                min_temp = float(min_temp)
                max_temp = float(max_temp)
                city_key = entered_city.lower().replace(" ", "")  # Normalize input

                if city_key in OHIO_CITIES:
                    coords = OHIO_CITIES[city_key]
                    lat, lon = coords["lat"], coords["lon"]

                    # Step 1: Fetch forecast URL
                    point_url = f"{NWS_API_BASE_URL}/{lat},{lon}"
                    point_response = requests.get(point_url)
                    if point_response.status_code != 200:
                        error_message = f"Error fetching forecast URL for {entered_city}."
                    else:
                        point_data = point_response.json()
                        forecast_url = point_data["properties"]["forecast"]

                        # Step 2: Fetch forecast data
                        forecast_response = requests.get(forecast_url)
                        if forecast_response.status_code != 200:
                            error_message = f"Error fetching forecast data for {entered_city}."
                        else:
                            forecast_data = forecast_response.json()
                            weather_data = forecast_data["properties"]["periods"][0]  # First forecast period
                            current_temp = weather_data["temperature"]
                            short_forecast = weather_data["shortForecast"].lower()

                            # Step 3: Generate recommendations
                            if current_temp < min_temp:
                                if "snow" in short_forecast:
                                    recommendations = "It's snowy. Carry a jacket, gloves, and a muffler or scarf."
                                elif "rain" in short_forecast:
                                    recommendations = "It's rainy. Carry an umbrella and a jacket."
                                else:
                                    recommendations = "It's cool. Carry a jacket and a muffler."
                            elif current_temp > max_temp:
                                recommendations = "It's hot. Wear light clothes and a cap."
                            else:
                                recommendations = "The weather is comfortable. No special preparation needed."
                else:
                    error_message = f"City '{entered_city}' not found in Ohio. Please try a valid Ohio city."
            except Exception as e:
                error_message = f"Error: {e}"
        else:
            error_message = "Please enter valid login credentials, a city name, and comfortable temperature range."

    return render_template(
        "login.html",
        weather_data=weather_data,
        recommendations=recommendations,
        error_message=error_message,
        entered_city=entered_city
    )

# Let a user configure their account data, including cold/hot limits
# TODO: This is both incomplete and untested, which should be fixed!
@app.route("/configure/<user>", methods=["GET", "POST"])
def configure(user):
    if request.method == "POST":
        newHotLimit = request.form.get("hotlimit")
        newColdLimit = request.form.get("coldlimit")

        # Update the user's configuration
        try:
            conn = pymssql.connect(DB_SERVER, DB_USER, DB_PASSWORD, DB_NAME)
            cursor = conn.cursor(as_dict=True)
            cursor.execute("UPDATE dbo.users SET maxt=?, mint=? WHERE uname=?", newHotLimit, newColdLimit, user)
            cursor.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            weather_data = f"Error connecting to database: {e}"
    
    return render_template('configure.html')

@app.route("/predict/<user>")
def predict(user):
    currentDate = datetime.datetime.now()
    year = currentDate.year
    month = currentDate.month
    day = currentDate.day
    # Connect to the database
    connection = pymssql.connect(
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

    # Execute a second query for user temperature limits
    cursor.execute("SELECT maxt, mint FROM dbo.users WHERE uname=?;", user)

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
