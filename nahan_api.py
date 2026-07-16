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


# ------------------- rename service ------------------


def rename_service(old_name, new_name):

    headers = {
        "Authorization": f"Bearer {config.NAHAN_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "oldName": old_name,
        "newName": new_name,
    }

    r = requests.post(
        f"{config.NAHAN_API_URL}/rename",
        headers=headers,
        json=data,
        timeout=20,
    )

    return r.status_code == 200


# ------------------- get user services ------------------


def get_user_services(user_id):

    headers = {
        "Authorization": f"Bearer {config.NAHAN_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.get(
        config.NAHAN_API_URL,
        headers=headers,
        timeout=20,
    )

    print(response.status_code)
    print(response.text)

    data = response.json()

    if data.get("success"):
        return data.get("users", [])

    return []


# ------------------- get service by id ------------------


def get_service_by_id(service_id):

    headers = {
        "Authorization": f"Bearer {config.NAHAN_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.get(
        config.NAHAN_API_URL,
        headers=headers,
        timeout=20,
    )

    data = response.json()

    if data.get("success"):

        for service in data.get("users", []):

            if service.get("id") == service_id:

                return service

    return None


# ------------------- get service configs ------------------


def get_service_configs(service_id):

    headers = {
        "Authorization": f"Bearer {config.NAHAN_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.get(
        f"{config.NAHAN_API_URL}/{service_id}",
        headers=headers,
        timeout=20,
    )

    print(response.status_code)
    print(response.text)

    return response.json()
