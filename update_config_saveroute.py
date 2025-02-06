import requests
import json
import hmac
import hashlib
import base64
import time
import uuid
import yaml
import os

SETTINGS_FILE = 'pritunl_settings.yml'
BACKUP_DIR = 'routes_backup'

def load_settings(filename=SETTINGS_FILE):
    """ Загружает конфигурацию из YAML-файла. """
    with open(filename, 'r') as file:
        return yaml.safe_load(file)

def save_settings(settings, filename=SETTINGS_FILE):
    """ Сохраняет обновленные настройки в YAML-файл. """
    with open(filename, 'w') as file:
        yaml.dump(settings, file, default_flow_style=False, allow_unicode=True)

    print(f"Settings updated in {filename}")

def create_signature(api_token, api_secret, method, path):
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    auth_string = f"{api_token}&{timestamp}&{nonce}&{method.upper()}&{path}"
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
            response = requests.request(method, url, headers=headers, json=data, verify=True, timeout=30)
        else:
            response = requests.request(method, url, headers=headers, verify=True, timeout=30)
        
        if response.status_code == 200:
            return response.json()  
        else:
            print(f'Error: {response.status_code}, Message: {response.text}')
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def get_server_routes(base_url, api_token, api_secret, server_id):
   
    url = f'{base_url}/server/{server_id}/route'
    headers = create_signature(api_token, api_secret, 'GET', f'/server/{server_id}/route')
    
    routes = send_request(url, 'GET', headers)
    if routes is not None:
        print(f'Routes for server {server_id}: {json.dumps(routes, indent=2)}')
        save_routes_to_yaml(server_id, routes)
        update_main_settings(server_id, routes)
    return routes

def save_routes_to_yaml(server_id, routes):
    """ Сохраняет список маршрутов в отдельный YAML-файл. """
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    filename = os.path.join(BACKUP_DIR, f'server_{server_id}_routes.yml')
    with open(filename, 'w') as file:
        yaml.dump({'server_id': server_id, 'routes': routes}, file, default_flow_style=False, allow_unicode=True)

    print(f"Routes saved to {filename}")

def update_main_settings(server_id, routes):
    
    settings = load_settings()

   
    for item in settings.get('routes', []):
        if item['server_id'] == server_id:
            item['network'] = [route['network'] for route in routes]
            break
    else:
       
        settings.setdefault('routes', []).append({
            'server_id': server_id,
            'network': [route['network'] for route in routes]
        })

    save_settings(settings)

def main():
    settings = load_settings()
    base_url = settings['base_url']
    api_token = settings['api_token']
    api_secret = settings['api_secret']

    for item in settings.get('routes', []):
        server_id = item['server_id']
        print(f"\nGetting routes for server: {server_id}")
        get_server_routes(base_url, api_token, api_secret, server_id)

if __name__ == '__main__':
    main()
