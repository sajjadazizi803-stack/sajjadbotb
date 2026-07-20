import requests
import config

# ------------------- create nahan user ------------------


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

    r = requests.post(
        config.NAHAN_API_URL,
        headers=headers,
        json=data,
        timeout=20,
    )

    if r.status_code == 201:
        result = r.json()

        return {
            "subscription_url": result.get("subscriptionUrl"),
            "service_id": result.get("user", {}).get("id"),
        }

    return None


# ------------------- rename service ------------------


def rename_service(service_id, new_name):

    headers = {
        "Authorization": f"Bearer {config.NAHAN_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "name": new_name,
    }

    response = requests.put(
        f"{config.NAHAN_API_URL}?id={service_id}",
        headers=headers,
        json=data,
        timeout=20,
    )

    if response.status_code != 200:
        return False

    try:
        result = response.json()
        return result.get("success", False)
    except Exception:
        return False


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

    return response.text


# ------------------- test patch user ------------------


def test_patch_user(service_id):

    headers = {
        "Authorization": f"Bearer {config.NAHAN_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {"name": "TEST-NAME"}

    response = requests.patch(
        f"{config.NAHAN_API_URL}/{service_id}/name",
        headers=headers,
        json=payload,
        timeout=20,
    )


# ------------------- test api root ------------------


def test_api_root():

    headers = {
        "Authorization": f"Bearer {config.NAHAN_API_KEY}",
    }

    response = requests.get(
        config.NAHAN_API_URL.replace("/users", "/openapi.json"),
        headers=headers,
        timeout=20,
    )
