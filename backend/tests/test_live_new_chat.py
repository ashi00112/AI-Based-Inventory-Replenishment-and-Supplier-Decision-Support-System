import urllib.request
import json

def test():
    # 1. Login
    login_data = json.dumps({'email': 'admin@smartsupply.ai', 'password': 'AdminPassword123!'}).encode('utf-8')
    req = urllib.request.Request('http://localhost:8000/api/v1/auth/login', data=login_data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode('utf-8'))['access_token']
    print('Login SUCCESS, token acquired.')

    # 2. Create conversation (New Chat)
    req_create = urllib.request.Request('http://localhost:8000/api/v1/chat/conversations', data=b'{}', headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req_create) as resp:
        conv = json.loads(resp.read().decode('utf-8'))
    conv_id = conv['id']
    print(f'Create Conversation (New Chat) SUCCESS! Conv ID: {conv_id}, Title: {conv["title"]}')

    # 3. List conversations
    req_list = urllib.request.Request('http://localhost:8000/api/v1/chat/conversations?limit=10', headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req_list) as resp:
        convs = json.loads(resp.read().decode('utf-8'))
    print(f'List Conversations SUCCESS! Count: {len(convs)}')

    # 4. Clean up created test conversation
    req_del = urllib.request.Request(f'http://localhost:8000/api/v1/chat/conversations/{conv_id}', headers={'Authorization': f'Bearer {token}'}, method='DELETE')
    with urllib.request.urlopen(req_del) as resp:
        print(f'Delete test conversation SUCCESS! Status: {resp.status}')

if __name__ == '__main__':
    test()
