import requests

# Địa chỉ Elasticsearch của bạn
url = "http://localhost:9200/_cat/indices?format=json"

# Gửi yêu cầu GET đến Elasticsearch API
response = requests.get(url)

if response.status_code == 200:
    indices = response.json()
    print(f"Total number of indices: {len(indices)}")
    print("List of indices:")
    for index in indices:
        print(index['index'])
else:
    print("Error fetching indices:", response.status_code)
