from flask import Flask, render_template, g, request, redirect, send_from_directory
import sqlite3 as sql
import os
#from waitress import serve

project_root = os.path.dirname(__file__)
template_path = os.path.join(project_root, './')
DATABASE = os.path.join(project_root, 'users.db')
EMPTYFILE = (' ',0)

app = Flask(__name__, template_folder=template_path)
app.config.from_object(__name__)

# Connect to database
def connect_to_database():
    return sql.connect(app.config['DATABASE'])

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

# Create table if not exist
def create_tb():
    insert_query('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, uname TEXT, pword TEXT,
                    fname TEXT, lname TEXT, email TEXT, filename TEXT DEFAULT '')''')
    return

# First webpage
@app.route('/')
def index():
    create_tb()
    return render_template('index.html')

# Get user id from username and password
def getuid(username, password):
    rows = execute_query("""SELECT id FROM users WHERE uname = ? AND pword = ?""",
                  (username, password))
    if len(rows) == 0:
        return -1
    return rows[0][0]

# Count the number of words in file
def cntwords(filename):
    number_of_words = 0
    with open(os.path.join(project_root, filename), 'r') as file:
        data = file.read()
        lines = data.split()
        for word in lines:
            if not (word.isnumeric() or word == ''):
                number_of_words += 1
    return number_of_words

# Check if user can log in
@app.route('/login', methods=['POST'])
def login():
    uname = request.form['uname']
    pword = request.form['pword']
    userid = getuid(uname,pword)
    return redirect("/user/{}".format(userid))

# Register user in database
@app.route('/register', methods=['POST'])
def register():
    uname = request.form['uname']
    pword = request.form['pword']
    fname = request.form['fname']
    lname = request.form['lname']
    email = request.form['email']

    userid = getuid(uname, pword)
    if userid == -1:
        insert_query("INSERT INTO users (uname, pword, fname, lname, email, filename) VALUES (?, ?, ?, ?, ?, ?)", (uname, pword, fname, lname, email, ''))
        userid = getuid(uname, pword)
    else:
        insert_query("UPDATE users SET fname = ?, lname = ?, email = ? WHERE id = ?",
                     (fname, lname, email, userid))

    return redirect("/user/{}".format(userid))

# Display user information
@app.route("/user/<userid>")
def getuser(userid):
    rows = execute_query("""SELECT * FROM users WHERE id = ?""", (userid,))
    if len(rows) == 0 or userid == -1:
        return "<h1>User info</h1> Incorrect username or password"
    filename = rows[0][6]
    if filename == '': #No file stored
        f = app.config['EMPTYFILE']
    else:
        f = (filename, cntwords(filename))
    return render_template("user.html", user = rows[0], file = f)

# Display database
@app.route("/viewdb")
def viewdb():
    rows = execute_query("""SELECT * FROM users""")
    return '<br>'.join(str(row) for row in rows)

# Upload user file and overwrite old file
@app.route('/upload/<userid>', methods=['POST'])
def upload_file(userid):
    f = request.files['file']
    filepath = os.path.join(project_root, f.filename)
    f.save(filepath)
    insert_query("""UPDATE users SET filename = ? WHERE id = ?""", (f.filename, userid))
    return redirect("/user/{}".format(userid))

# Download user file
@app.route('/download/<userid>:<filename>')
def download_file(userid,filename):
    if filename == '':
        return redirect("/user/{}".format(userid))
    return send_from_directory(project_root, filename, as_attachment=True)

if __name__ == '__main__':
    app.run()
    #serve(app, host='127.0.0.1', port=5000)
