import requests
import json
import hmac
import hashlib
import base64
import time
import uuid
import yaml
import os

BACKUP_DIR = 'routes_backup'
SETTINGS_FILE = 'pritunl_settings.yml'
ROUTES_DELETE_FILE = 'routes_to_delete.txt'

def load_settings(filename=SETTINGS_FILE):
   
    with open(filename, 'r') as file:
        return yaml.safe_load(file)

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

        if response.status_code in [200, 204]:
            return response.json() if response.text else None  
        else:
            print(f'Error: {response.status_code}, Message: {response.text}')
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def load_backup_routes(server_id):
  
    filename = os.path.join(BACKUP_DIR, f'server_{server_id}_routes.yml')

    if os.path.exists(filename):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            return {route['network']: route['id'] for route in data.get('routes', [])}  
        print(f"No backup routes found for {server_id}")
        return {}

def load_routes_to_delete():
   
    if os.path.exists(ROUTES_DELETE_FILE):
        with open(ROUTES_DELETE_FILE, 'r') as file:
            return {line.strip() for line in file.readlines() if line.strip()}  
    else:
        print(f"No routes_to_delete.txt file found")
        return set()

def manage_server(base_url, api_token, api_secret, server_id, routes):
  
    
   
    stop_url = f'{base_url}/server/{server_id}/operation/stop'
    stop_headers = create_signature(api_token, api_secret, 'PUT', f'/server/{server_id}/operation/stop')
    stop_response = send_request(stop_url, 'PUT', stop_headers)
    print(f'Server stop response: {stop_response}')

    
    backup_routes = load_backup_routes(server_id)  
    routes_to_delete = load_routes_to_delete()  

    
    matched_routes = {network: route_id for network, route_id in backup_routes.items() if network in routes_to_delete}

    
    if matched_routes:
        for network, route_id in matched_routes.items():
            delete_route_url = f'{base_url}/server/{server_id}/route/{route_id}'
            delete_route_headers = create_signature(api_token, api_secret, 'DELETE', f'/server/{server_id}/route/{route_id}')
            delete_route_response = send_request(delete_route_url, 'DELETE', delete_route_headers)
            print(f'Deleted route {network} (ID: {route_id}): {delete_route_response}')
    else:
        print("No matching routes found for deletion.")

   
    start_url = f'{base_url}/server/{server_id}/operation/start'
    start_headers = create_signature(api_token, api_secret, 'PUT', f'/server/{server_id}/operation/start')
    start_response = send_request(start_url, 'PUT', start_headers)
    print(f'Server start response: {start_response}')

def main():
    settings = load_settings()
    base_url = settings['base_url']
    api_token = settings['api_token']
    api_secret = settings['api_secret']

    
    for item in settings.get('routes', []):
        server_id = item['server_id']
        routes = item.get('network', [])
        
        print(f"\nManaging server: {server_id}")
        manage_server(base_url, api_token, api_secret, server_id, routes)

if __name__ == '__main__':
    main()
