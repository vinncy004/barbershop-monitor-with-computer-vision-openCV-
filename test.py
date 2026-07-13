import sqlite3
con=sqlite3.connect('shavelog.db')
con.execute('''
 CREATE TABLE test(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            password TEXT NOT NULL
            )
''')

con.close()