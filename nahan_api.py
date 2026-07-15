import requests
import config


def create_nahan_user(username, traffic_gb=1, expiry_days=30):

    headers = {
        "Authorization": f"Bearer {config.NAHAN_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "name": username,
        "trafficLimit": traffic_gb,
        "expiryDays": expiry_days,
        "connLimit": 0,
    }

    r = requests.post(config.NAHAN_API_URL, headers=headers, json=data, timeout=20)

    if r.status_code == 201:
        result = r.json()
        print(result)
        return result.get("subscriptionUrl")

    return None
