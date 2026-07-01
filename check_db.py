import sqlite3

def check():
    conn = sqlite3.connect('rapidrelief.db')
    try:
        devs = len(conn.execute('SELECT * FROM zone_nodes').fetchall())
        print(f"Nodes: {devs}")
    except Exception as e:
        print(f"Nodes error: {e}")

if __name__ == '__main__':
    check()
