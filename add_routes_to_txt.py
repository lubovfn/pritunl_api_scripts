import yaml
import requests
import hmac
import hashlib
import base64
import time
import uuid
import json
import os

SETTINGS_FILE = 'pritunl_settings.yml'
ROUTES_FILE = 'routes_to_add.txt'
CERT_PATH = ('/etc/ssl/my.crt', '/etc/ssl/my.key')  
# Загрузка настроек из YAML файла
def load_settings(filename=SETTINGS_FILE):
    with open(filename, 'r') as file:
        return yaml.safe_load(file)


def create_signature(api_token, api_secret, method, path):
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    auth_string = '&'.join([api_token, timestamp, nonce, method.upper(), path])
    signature = hmac.new(api_secret.encode(), auth_string.encode(), hashlib.sha256).digest()
    return {
        'Auth-Token': api_token,
        'Auth-Timestamp': timestamp,
        'Auth-Nonce': nonce,
        'Auth-Signature': base64.b64encode(signature).decode()
    }


def send_request(url, method, headers, data=None):
    try:
        if data:
            response = requests.request(method, url, headers=headers, json=data, cert=CERT_PATH, verify=True)
        else:
            response = requests.request(method, url, headers=headers, cert=CERT_PATH, verify=True)

        if response.status_code in [200, 201, 204]:
            return response.json() if response.text else None
        else:
            print(f' API Error {response.status_code}: {response.text}')
            return None
    except requests.exceptions.RequestException as e:
        print(f" Request failed: {e}")
        return None

def get_existing_routes(base_url, api_token, api_secret, server_id):
    """ Получает список уже существующих маршрутов на сервере. """
    url = f"{base_url}/server/{server_id}/route"
    headers = create_signature(api_token, api_secret, 'GET', f"/server/{server_id}/route")

    routes = send_request(url, 'GET', headers)
    if routes:
        return {route["network"] for route in routes}  
    return set()

def add_route_to_server(base_url, api_token, api_secret, server_id, route):
    """ Добавляет новый маршрут в сервер Pritunl. """
    url = f"{base_url}/server/{server_id}/route"
    headers = create_signature(api_token, api_secret, 'POST', f"/server/{server_id}/route")
    data = {"network": route}

    response = send_request(url, 'POST', headers, data)
    if response:
        print(f" Added route {route} to server {server_id}")
    else:
        print(f" Failed to add route {route} to server {server_id}")

def add_routes_from_file(base_url, api_token, api_secret, server_id):
    """ Читает маршруты из файла и добавляет их в Pritunl. """
    if not os.path.exists(ROUTES_FILE):
        print(f" No {ROUTES_FILE} file found.")
        return

    with open(ROUTES_FILE, 'r') as file:
        routes_to_add = {line.strip() for line in file.readlines() if line.strip()}  # Загружаем маршруты без дубликатов

    if not routes_to_add:
        print(" No routes found in file.")
        return

    
    existing_routes = get_existing_routes(base_url, api_token, api_secret, server_id)

    for route in routes_to_add:
        if route in existing_routes:
            print(f"Route {route} already exists on server {server_id}, skipping.")
        else:
            add_route_to_server(base_url, api_token, api_secret, server_id, route)

def manage_server(base_url, api_token, api_secret, server_id):
   
    
    
    stop_url = f'{base_url}/server/{server_id}/operation/stop'
    stop_headers = create_signature(api_token, api_secret, 'PUT', f'/server/{server_id}/operation/stop')
    stop_response = send_request(stop_url, 'PUT', stop_headers)
    print(f'Server stop response: {stop_response}')

    
    add_routes_from_file(base_url, api_token, api_secret, server_id)

    
    start_url = f'{base_url}/server/{server_id}/operation/start'
    start_headers = create_signature(api_token, api_secret, 'PUT', f'/server/{server_id}/operation/start')
    start_response = send_request(start_url, 'PUT', start_headers)
    print(f' Server start response: {start_response}')

def main():
    settings = load_settings()
    base_url = settings['base_url']
    api_token = settings['api_token']
    api_secret = settings['api_secret']

    servers = settings.get("servers", [])
    if not servers:
        print(" No servers found in pritunl_settings.yml")
        return

    
    for server in servers:
        server_id = server.get("id")
        server_name = server.get("name", "Unknown Server")
        print(f"\n Managing server: {server_name} ({server_id})")
        manage_server(base_url, api_token, api_secret, server_id)

if __name__ == '__main__':
    main()
