import os
import sys
import requests

file_path = sys.argv[1]
file_name = os.path.basename(file_path)

headers = {'accept': 'application/json'}
files = {'file': (file_name, open(file_path, 'rb'))}

response = requests.post('http://127.0.0.1:8009/uploadfile', headers=headers, files=files)
print(response.text)
