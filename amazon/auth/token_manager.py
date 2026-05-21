import requests
from utils.config_loader import cfg, get_debug_mode

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """
    Refresh Token を使って Access Token を取得する
    """
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(LWA_TOKEN_URL, data=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        raise Exception(f"Access token request failed: {response.text}")
