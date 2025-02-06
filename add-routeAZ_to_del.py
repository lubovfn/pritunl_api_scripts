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
AZURE_JSON_FILE = 'ServiceTags_Public_20250203.json' 
ROUTES_DELETE_FILE = 'routes_to_delete.txt'  
CERT_PATH = ('/etc/ssl/my.crt', '/etc/ssl/my.key')  


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
            print(f'API Error {response.status_code}: {response.text}')
            return None
    except requests.exceptions.RequestException as e:
        print(f" Request failed: {e}")
        return None


def load_routes_to_delete():
    if not os.path.exists(ROUTES_DELETE_FILE):
        return set()
    
    with open(ROUTES_DELETE_FILE, 'r') as file:
        return {line.strip() for line in file.readlines() if line.strip()}


def save_routes_to_delete(routes):
    if not routes:
        print("No routes to save in routes_to_delete.txt.")
        return

    with open(ROUTES_DELETE_FILE, 'w') as file:
        for route in sorted(routes):
            file.write(route + '\n')

    print(f" Saved {len(routes)} routes to {ROUTES_DELETE_FILE}")


def get_existing_routes(base_url, api_token, api_secret, server_id):
    url = f"{base_url}/server/{server_id}/route"
    headers = create_signature(api_token, api_secret, 'GET', f"/server/{server_id}/route")

    routes = send_request(url, 'GET', headers)
    if routes:
        return {route["network"] for route in routes}  
    return set()


def add_route_to_server(base_url, api_token, api_secret, server_id, route):
    url = f"{base_url}/server/{server_id}/route"
    headers = create_signature(api_token, api_secret, 'POST', f"/server/{server_id}/route")
    data = {"network": route}

    response = send_request(url, 'POST', headers, data)
    if response:
        print(f" Added route {route} to server {server_id}")
        return True
    else:
        print(f" Failed to add route {route} to server {server_id}")
        return False

def get_azure_ips():
    if not os.path.exists(AZURE_JSON_FILE):
        print(f" JSON file {AZURE_JSON_FILE} not found!")
        return set()

    try:
        with open(AZURE_JSON_FILE, 'r') as file:
            data = json.load(file)
            azure_ips = set()

      
            if "values" in data:
                for entry in data["values"]:
                    if entry.get("name") in ["AzureDevOps", "AzureCloud.westeurope"] or \
                       entry.get("id") in ["AzureDevOps", "AzureCloud.westeurope"] or \
                       entry.get("systemService") in ["AzureDevOps", "AzureCloud.westeurope"]:
                        if "properties" in entry and "addressPrefixes" in entry["properties"]:
                            for ip in entry["properties"]["addressPrefixes"]:
                                azure_ips.add(ip)

            print(f" Found {len(azure_ips)} Azure IPs from JSON file")
            return azure_ips
    except json.JSONDecodeError as e:
        print(f" JSON parsing error: {e}")
        return set()
    except Exception as e:
        print(f" Failed to read JSON: {e}")
        return set()


def add_azure_routes_to_server(base_url, api_token, api_secret, server_id):
    azure_ips = get_azure_ips()
    if not azure_ips:
        print("No Azure IP found.")
        return

    routes_to_delete = load_routes_to_delete()

   
    existing_routes = get_existing_routes(base_url, api_token, api_secret, server_id)

    added_routes = set()
    for route in azure_ips:
        if route in existing_routes or route in routes_to_delete:
            print(f"🔹 Route {route} already exists or skipping.")
        else:
            if add_route_to_server(base_url, api_token, api_secret, server_id, route):
                added_routes.add(route)

    return added_routes


def manage_server(base_url, api_token, api_secret, server_id, server_name):
    print(f"\n Managing server: {server_name} ({server_id})")


    stop_url = f'{base_url}/server/{server_id}/operation/stop'
    stop_headers = create_signature(api_token, api_secret, 'PUT', f'/server/{server_id}/operation/stop')
    stop_response = send_request(stop_url, 'PUT', stop_headers)
    print(f'Server stop response: {stop_response}')

 
    added_routes = add_azure_routes_to_server(base_url, api_token, api_secret, server_id)

   
    if added_routes:
        save_routes_to_delete(added_routes)


    start_url = f'{base_url}/server/{server_id}/operation/start'
    start_headers = create_signature(api_token, api_secret, 'PUT', f'/server/{server_id}/operation/start')
    start_response = send_request(start_url, 'PUT', start_headers)
    print(f'Server start response: {start_response}')

def main():
    settings = load_settings()
    base_url = settings['base_url']
    api_token = settings['api_token']
    api_secret = settings['api_secret']

    servers = settings.get("servers", [])
    if not servers:
        print("No servers found in pritunl_settings.yml")
        return


    for server in servers:
        server_id = server.get("id")
        server_name = server.get("name", "Unknown Server")
        manage_server(base_url, api_token, api_secret, server_id, server_name)

if __name__ == '__main__':
    main()
