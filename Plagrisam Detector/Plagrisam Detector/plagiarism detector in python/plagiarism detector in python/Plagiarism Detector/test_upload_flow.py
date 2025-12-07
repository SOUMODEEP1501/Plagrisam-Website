import requests
import os

# Create two small text files to upload
with open('test_a.txt', 'w', encoding='utf-8') as f:
    f.write('This is sample file A for upload test.')
with open('test_b.txt', 'w', encoding='utf-8') as f:
    f.write('This is sample file B for upload test.')

files = [
    ('files', ('test_a.txt', open('test_a.txt', 'rb'), 'text/plain')),
    ('files', ('test_b.txt', open('test_b.txt', 'rb'), 'text/plain')),
]

data = {'input_mode': 'files'}

url = 'http://127.0.0.1:5000/'
print('Posting files to', url)

r = requests.post(url, files=files, data=data)
print('POST response status:', r.status_code)

# After POST with requests, requests follows redirects and returns final page content
content_after_post = r.text
print('Contains test_a.txt after POST+redirect?', 'test_a.txt' in content_after_post)
print('Contains test_b.txt after POST+redirect?', 'test_b.txt' in content_after_post)

# Now simulate reload (another GET)
r2 = requests.get(url)
print('GET after reload status:', r2.status_code)
print('Contains test_a.txt after reload?', 'test_a.txt' in r2.text)
print('Contains test_b.txt after reload?', 'test_b.txt' in r2.text)

# Check uploaded_documents folder
upload_folder = 'uploaded_documents'
if os.path.exists(upload_folder):
    files_on_disk = os.listdir(upload_folder)
else:
    files_on_disk = []
print('Files remaining in uploaded_documents:', files_on_disk)

# Cleanup local test files
try:
    os.remove('test_a.txt')
    os.remove('test_b.txt')
except Exception:
    pass

# Result summary
if ('test_a.txt' in content_after_post and 'test_b.txt' in content_after_post) and ('test_a.txt' not in r2.text and 'test_b.txt' not in r2.text) and (not files_on_disk):
    print('\nTEST PASSED: PRG and cleanup behavior is working.')
else:
    print('\nTEST FAILED: See above outputs for details.')
