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

def load_settings(filename=SETTINGS_FILE):
    """ Загружает конфигурацию из YAML-файла. """
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            return yaml.safe_load(file)
    return {"routes": []} 

def save_settings(settings, filename=SETTINGS_FILE):
  
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

def send_request(url, method, headers):
  
    try:
        response = requests.request(method, url, headers=headers, verify=True, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f' Error: {response.status_code}, Message: {response.text}')
            return None
    except requests.exceptions.RequestException as e:
        print(f" Request failed: {e}")
        return None

def get_all_servers(base_url, api_token, api_secret):
    
    url = f"{base_url}/server"
    headers = create_signature(api_token, api_secret, 'GET', '/server')

    servers = send_request(url, 'GET', headers)
    if servers:
        print(f" Found {len(servers)} servers in Pritunl.")
        print(" Example server response:")
        print(json.dumps(servers[:1], indent=2))  
        return servers
    else:
        print(" No servers found or error occurred.")
        return []

def get_server_details(base_url, api_token, api_secret, server_id):
    """ Получает конфигурацию сервера, включая сети. """
    url = f"{base_url}/server/{server_id}"
    headers = create_signature(api_token, api_secret, 'GET', f"/server/{server_id}")

    server_data = send_request(url, 'GET', headers)
    if server_data:
        print(f" Server {server_id} details:")
        print(json.dumps(server_data, indent=2))
        return server_data
    return {}

def get_server_routes(base_url, api_token, api_secret, server_id):
    """ Получает маршруты для указанного сервера. """
    url = f"{base_url}/server/{server_id}/route"
    headers = create_signature(api_token, api_secret, 'GET', f"/server/{server_id}/route")

    routes = send_request(url, 'GET', headers)
    if routes:
        return [route.get("network") for route in routes if "network" in route]  
    return []

def update_pritunl_settings(base_url, api_token, api_secret):
   
    settings = load_settings()

    
    existing_servers = {srv["server_id"] for srv in settings.get("routes", [])}

   
    servers = get_all_servers(base_url, api_token, api_secret)

    new_servers = []
    for server in servers:
        server_id = server.get("_id") or server.get("id") or server.get("uuid")
        server_name = server.get("name", f"Unknown-{server_id}")

        
        server_details = get_server_details(base_url, api_token, api_secret, server_id)
        networks = server_details.get("networks", [])  
        routes = get_server_routes(base_url, api_token, api_secret, server_id) 

        
        if not networks and routes:
            networks = routes

        if server_id and server_id not in existing_servers:
            print(f"Adding server {server_name} ({server_id}) with networks: {networks} and routes: {routes}")
            new_servers.append({
                "server_id": server_id,
                "server_name": server_name,  
                "network": networks, 
                "routes": routes,  
                "routes_to_delete": []
            })

    if new_servers:
        settings.setdefault("routes", []).extend(new_servers)
        save_settings(settings)
        print(f" Added {len(new_servers)} new servers with network settings to {SETTINGS_FILE}")
    else:
        print(" No new servers found to add.")

def main():
    settings = load_settings()
    base_url = settings.get('base_url')
    api_token = settings.get('api_token')
    api_secret = settings.get('api_secret')

    if not base_url or not api_token or not api_secret:
        print("Missing API credentials in pritunl_settings.yml")
        return

    print("\n Getting all servers from Pritunl with network settings and server names...")
    update_pritunl_settings(base_url, api_token, api_secret)

if __name__ == '__main__':
    main()
