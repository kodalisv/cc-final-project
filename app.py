from flask import Flask, render_template, request, redirect, url_for, flash
import pyodbc

app = Flask(__name__)
app.secret_key = "secret_key"

# Database Configuration
server = 'ccfinalprojectserver.database.windows.net'
database = 'ccfinalprojectdatabase'
username = 'finalprojectlogin'
password = 'weatherapp1!'
driver = '{ODBC Driver 18 for SQL Server}'

# Connect to Azure SQL Database
def get_db_connection():
    try:
        conn = pyodbc.connect(
            f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}')
        return conn
    except Exception as e:
        print("Error connecting to database:", e)
        return None

# Route for the Login Page
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        db_name = request.form['database_name']
        db_server_name = request.form['database_server_name']

        # Validate against the Azure database here
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM Users WHERE username = ? AND password = ? AND email = ?",
                               (username, password, email))
                user = cursor.fetchone()
                if user:
                    flash("Login successful!", "success")
                    return redirect(url_for('dashboard'))
                else:
                    flash("Invalid credentials. Please try again.", "danger")
            except Exception as e:
                flash(f"Database query failed: {e}", "danger")
            finally:
                cursor.close()
                conn.close()
        else:
            flash("Could not connect to database.", "danger")
    return render_template('login.html')

# Dashboard (dummy route for success)
@app.route('/dashboard')
def dashboard():
    return "<h1>Welcome to the Dashboard!</h1>"

if __name__ == '__main__':
    app.run(debug=True)
