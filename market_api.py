import requests

API_KEY = "freeXFyGc1kNBzQPu5a3NldyEsBvCZ7v"


def format_number(value):
    try:
        number = float(str(value).replace(",", ""))

        if number.is_integer():
            return f"{int(number):,}"

        text = f"{number:,.2f}".rstrip("0").rstrip(".")
        return text

    except Exception:
        return "-"


def format_crypto(value):
    try:
        number = float(str(value).replace(",", ""))

        if number.is_integer():
            return f"{int(number):,}"

        text = f"{number:,.2f}".rstrip("0").rstrip(".")
        return text

    except Exception:
        return "-"


def get_market_prices():
    try:
        url = f"https://api.navasan.tech/latest/" f"?api_key={API_KEY}&dollar_rate=true"

        data = requests.get(url, timeout=10).json()

        prices = {
            "usd": format_number(data.get("usd_sell", {}).get("value")),
            "gold": format_number(data.get("18ayar", {}).get("value")),
            "bitcoin": format_crypto(data.get("btc", {}).get("dollar_rate")),
            "ton": format_crypto(data.get("ton", {}).get("dollar_rate")),
        }

        return prices

    except Exception:
        return {
            "usd": "-",
            "gold": "-",
            "bitcoin": "-",
            "ton": "-",
        }
