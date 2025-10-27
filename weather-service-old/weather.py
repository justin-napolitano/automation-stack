import requests

def get_weather(city: str = "Orlando") -> str:
    try:
        txt = requests.get(f"https://wttr.in/{city}?format=3", timeout=8).text.strip()
        return txt
    except Exception as e:
        return f"Weather error: {e}"
