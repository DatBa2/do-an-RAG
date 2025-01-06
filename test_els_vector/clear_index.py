import requests

url = "http://localhost:9200/_cat/indices?format=json"
response = requests.get(url)

if response.status_code == 200:
    indices = response.json()
    for index in indices:
        index_name = index['index']
        delete_url = f"http://localhost:9200/{index_name}"
        del_response = requests.delete(delete_url)
        if del_response.status_code == 200:
            print(f"Index {index_name} deleted.")
        else:
            print(f"Error deleting index {index_name}: {del_response.status_code}")
else:
    print(f"Error fetching indices: {response.status_code}")
