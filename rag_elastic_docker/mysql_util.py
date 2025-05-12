import os
import mysql.connector

def execute_sql_query(query: str):
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "myuser"),
            password=os.getenv("DB_PASSWORD", "mypass"),
            database=os.getenv("DB_NAME", "mydb"),
        )
        cursor = conn.cursor(dictionary=True)  # 👈 Quan trọng: trả về dict
        cursor.execute(query)
        result = cursor.fetchall()
        conn.close()
        return result
    except mysql.connector.Error as err:
        return {"error": str(err)}
    

def insert_data(query: str, params: tuple = None) -> bool:
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "myuser"),
            password=os.getenv("DB_PASSWORD", "mypass"),
            database=os.getenv("DB_NAME", "mydb"),
        )
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"[INSERT ERROR] {err}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def update_data(query: str, params: tuple = None) -> bool:
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "myuser"),
            password=os.getenv("DB_PASSWORD", "mypass"),
            database=os.getenv("DB_NAME", "mydb"),
        )
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        print(query)
        conn.commit()
        conn.close()
        return True
    except mysql.connector.Error as err:
        print(f"[UPDATE ERROR] {err}")
        return False

def delete_data(query: str, params: tuple = None) -> bool:
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "myuser"),
            password=os.getenv("DB_PASSWORD", "mypass"),
            database=os.getenv("DB_NAME", "mydb"),
        )
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        conn.close()
        return True
    except mysql.connector.Error as err:
        print(f"[DELETE ERROR] {err}")
        return False
