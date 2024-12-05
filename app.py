from flask import Flask, render_template, request
import pymssql

app = Flask(__name__)

# Database connection details
DB_SERVER = 'ccfinalprojectserver.database.windows.net'
DB_USER = 'finalprojectlogin'
DB_PASSWORD = 'weatherapp1!'
DB_NAME = 'ccfinalprojectdatabase'
@app.route("/", methods=["GET", "POST"])
def login():
    weather_data = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")

        # Example database query
        try:
            conn = pymssql.connect(DB_SERVER, DB_USER, DB_PASSWORD, DB_NAME)
            cursor = conn.cursor(as_dict=True)
            cursor.execute("SELECT WDSP, DATE FROM dbo.HS_WEATHER WHERE TEMP > 76;")
            weather_data = cursor.fetchall()
            conn.close()
        except Exception as e:
            weather_data = f"Error connecting to database: {e}"

    return render_template(
        "login.html",
        weather_data=weather_data
    )

if __name__ == "__main__":
    app.run(debug=True)
