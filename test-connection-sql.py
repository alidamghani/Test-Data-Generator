import pyodbc
import socket

def test_connection():
    # Try to resolve DNS first
    try:
        ip = socket.gethostbyname('localhost')
        print(f"DNS resolved to: {ip}")
    except socket.gaierror:
        print("DNS resolution failed - check server name")
        return
    
    conn_str = (
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=172.27.80.1,1433;'
        'DATABASE=reindexing-db;'
        'UID=python;'
        'PWD=python;'
        'Encrypt=yes;'
        'TrustServerCertificate=yes;'  # Remove for production
        'Connection Timeout=30;'
    )
    
    try:
        conn = pyodbc.connect(conn_str)
        print("Connected successfully!")
        conn.close()
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        print(f"SQLState: {sqlstate}")
        print(f"Error: {ex}")

test_connection()
