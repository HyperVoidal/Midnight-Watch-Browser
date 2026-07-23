import sqlite3
from pathlib import Path

db = Path(r"C:\Users\saman\OneDrive\Documents\GitHub\Midnight-Engine-Browser\Main_Repo\src\data\Browser_Data\User_Profile\Cookies")

with sqlite3.connect(db) as conn:
    print("Opened!")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cookies")
    print(cur.fetchone())