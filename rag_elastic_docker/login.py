from mysql_util import execute_sql_query, insert_data
from fastapi.responses import HTMLResponse

def verify_login(username: str, password: str) -> bool:
    query = f"SELECT * FROM users WHERE username = '{username}'"
    result = execute_sql_query(query)
    if not result:
        return False
    stored_password = result[0]['hashed_password']
    if password == stored_password:
        return True  # Mật khẩu đúng
    else:
        return False  # Mật khẩu sai
    

def register_chatbot(username: str, password: str) -> dict:
    try:
        query = f"SELECT * FROM users WHERE username = '{username}'"
        existing = execute_sql_query(query)
        if existing:
            return {"status": False, "message": "Tên người dùng đã tồn tại."}

        # Nếu chưa tồn tại thì thêm vào
        insert_query = "INSERT INTO users (username, hashed_password) VALUES (%s, %s)"
        success = insert_data(insert_query, params=(username, password))
        if success:
            return {"status": True, "message": "Đăng ký thành công."}
        else:
            return {"status": False, "message": "Lỗi khi thêm người dùng."}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}
