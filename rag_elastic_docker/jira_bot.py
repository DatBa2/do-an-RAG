import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
load_dotenv()

# ✅ Cấu hình thông tin
JIRA_URL = "https://cntt.vnpt.vn/rest/api/2/search"
USERNAME = os.getenv("JIRA_USERNAME", "badat")
PASSWORD = os.getenv("JIRA_PASSWORD", "badat")

params = {
    "jql": "project=VNPTEDU ORDER BY created DESC",
    "maxResults": 10
}

# ✅ Gửi request
print(PASSWORD)
response = requests.get(JIRA_URL, params=params, auth=HTTPBasicAuth(USERNAME, PASSWORD))

# ✅ Xử lý kết quả
if response.status_code == 200:
    data = response.json()
    for issue in data["issues"]:
        key = issue["key"]
        summary = issue["fields"]["summary"]
        status = issue["fields"]["status"]["name"]
        print(f"{key} | {status} | {summary}")
else:
    print("❌ Lỗi khi truy vấn Jira:", response.status_code)
