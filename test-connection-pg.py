import psycopg2
from psycopg2 import OperationalError

def test_postgres_connection():
    conn_params = {
        'host': 'localhost',
        'port': '5432',
        'database': 'oi',
        'user': 'dbuser',
        'password': 'dbuser',
        'connect_timeout': 5
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        cursor.execute('SELECT version();')
        db_version = cursor.fetchone()
        print(f"✅ Connected successfully!")
        print(f"PostgreSQL version: {db_version[0]}")
        cursor.close()
        conn.close()
        return True
    except OperationalError as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_postgres_connection()
