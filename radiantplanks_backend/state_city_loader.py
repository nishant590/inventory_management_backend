import json
import sqlite3

# Function to read JSON data from a file
def read_json_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Path to your JSON file
json_file_path = 'usa_state_city.json'  # Change this to your actual file path

# Read the data from the JSON file
state_city_mapping = read_json_file(json_file_path)

# Connect to SQLite database (or create it)
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Create tables
# cursor.execute('''
# CREATE TABLE IF NOT EXISTS users_state (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     state_name TEXT NOT NULL UNIQUE
# )
# ''')

# cursor.execute('''
# CREATE TABLE IF NOT EXISTS users_city (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     state_id INTEGER,
#     city_name TEXT NOT NULL,
#     FOREIGN KEY (state_id) REFERENCES users_statemaster(id)
# )
# ''')

# Insert states and cities into the database
state_ids = {}

for state_name, cities in state_city_mapping.items():
    # Insert state if it doesn't exist
    if state_name not in state_ids:
        cursor.execute('INSERT OR IGNORE INTO customers_state (name) VALUES (?)', (state_name,))
        state_ids[state_name] = cursor.lastrowid  # Store the newly created state ID

    # Get the state ID
    state_id = state_ids[state_name]

    # Insert cities for the state
    for city_name in cities:
        cursor.execute('INSERT INTO customers_city (state_id, name) VALUES (?, ?)', (state_id, city_name))

# Commit changes and close the connection
conn.commit()
conn.close()

print("Data has been inserted successfully.")