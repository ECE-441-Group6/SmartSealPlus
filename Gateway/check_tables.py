# Small development utility that lists tables in the local SQLite database.

import sqlite3

# This assumes the command is run from the directory containing the database.
conn = sqlite3.connect("smartseal.db")

cur = conn.cursor()

# Ask SQLite for all user tables so the schema can be checked manually.
cur.execute("""
SELECT name
FROM sqlite_master
WHERE type='table';
""")

print(cur.fetchall())

conn.close()