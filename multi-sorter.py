from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

DATABASE = 'data.db'

# Database setup for demonstration
def query_database(sort_criteria, filters):
    query = "SELECT * FROM items"
    where_clauses = []

    for filter_item in filters:
        field = filter_item['field']
        operation = filter_item['operation']
        value = filter_item['value']
        if operation in ['=', '>', '<', '>=', '<=']:
            where_clauses.append(f"{field} {operation} ?")
        elif operation == 'contains':
            where_clauses.append(f"{field} LIKE ?")
            value = f"%{value}%"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    if sort_criteria:
        order_by = ", ".join([f"{item['field']} {item['direction'].upper()}" for item in sort_criteria])
        query += f" ORDER BY {order_by}"

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, [f['value'] for f in filters])
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/filter_sort', methods=['POST'])
def filter_and_sort_data():
    data = request.json
    sort_criteria = data.get('sort_criteria', [])
    filters = data.get('filters', [])
    sorted_and_filtered_data = query_database(sort_criteria, filters)
    return jsonify(sorted_and_filtered_data)

if __name__ == '__main__':
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            date TEXT,
            price REAL
        )
    """)
    cursor.executemany("""
        INSERT OR IGNORE INTO items (id, name, date, price)
        VALUES (?, ?, ?, ?)
    """, [
        (1, 'Item A', '2023-01-01', 10.99),
        (2, 'Item B', '2023-02-15', 5.49),
        (3, 'Item C', '2023-01-10', 7.99)
    ])
    conn.commit()
    conn.close()

    app.run(debug=True)
