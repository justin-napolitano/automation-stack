import os
import time
import threading
from typing import Optional, Tuple

import requests
from croniter import croniter
from datetime import datetime
import pytz

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import uvicorn

# ------------ Config ------------
CITY = os.getenv("CITY", "Orlando")
STATE = os.getenv("STATE", "FL")
TZ = os.getenv("TZ", "America/New_York")
CRON = os.getenv("CRON_SCHEDULE", "0 7 * * *")  # default 7:00 AM daily
NOTIFY_URL = os.getenv("NOTIFY_URL")            # e.g. http://notifier-gateway:8787/notify
SOURCE_NAME = os.getenv("SOURCE_NAME", "weather-service")
NOTIFY_TO = os.getenv("NOTIFY_TO", "")
NOTIFY_TOKEN = os.getenv("NOTIFY_TOKEN", "")



LAT_ENV = os.getenv("LAT")
LON_ENV = os.getenv("LON")

STATE_MAP = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado",
    "CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho",
    "IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana",
    "ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi",
    "MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey",
    "NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma",
    "OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota",
    "TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
    "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming","DC":"District of Columbia",
}

# ------------ Helpers ------------
def _tz() -> pytz.BaseTzInfo:
    return pytz.timezone(TZ)

def tznow() -> datetime:
    return datetime.now(_tz())

def next_run(after: datetime, cron: str) -> datetime:
    return croniter(cron, after).get_next(datetime)

def geocode(city: str, state: Optional[str]) -> Tuple[float, float, str]:
    # 1) Allow explicit lat/lon to bypass geocoding
    if LAT_ENV and LON_ENV:
        return float(LAT_ENV), float(LON_ENV), city

    # 2) Build a set of increasingly lenient query names
    queries = []
    s = (state or "").strip()
    s_full = STATE_MAP.get(s.upper(), s) if s else s
    city_squeezed = city.strip()

    # Try with space, comma, full state name, and US qualifiers
    if s:
        queries += [
            f"{city_squeezed}, {s}",         # "Orlando, FL"
            f"{city_squeezed},{s}",          # "Orlando,FL"
        ]
        if s_full and s_full != s:
            queries += [
                f"{city_squeezed}, {s_full}",    # "Orlando, Florida"
            ]
        queries += [
            f"{city_squeezed}, {s}, US",
            f"{city_squeezed}, {s_full}, US" if s_full else None,
        ]
    # city-only and US variants
    queries += [
        city_squeezed,
        f"{city_squeezed}, US",
        f"{city_squeezed}, United States",
    ]
    queries = [q for q in queries if q]  # drop None

    last_err = None
    for q in queries:
        try:
            r = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": q, "count": 1},
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
            if data.get("results"):
                item = data["results"][0]
                lat = float(item["latitude"])
                lon = float(item["longitude"])
                label = item.get("name") or city_squeezed
                # Prefer including admin1/country for clarity if present
                admin1 = item.get("admin1")
                country = item.get("country")
                if admin1 and country:
                    label = f"{label}, {admin1}, {country}"
                return lat, lon, label
        except Exception as e:
            last_err = str(e)

    raise ValueError(f"Could not geocode '{city}{','+state if state else ''}' (tried: {queries}) — {last_err or ''}")

#def geocode(city: str, state: Optional[str]) -> Tuple[float, float, str]:
#    q = f"{city},{state}" if state else city
#    r = requests.get(
#        "https://geocoding-api.open-meteo.com/v1/search",
#        params={"name": q, "count": 1},
#        timeout=10
#    )
#    r.raise_for_status()
#    data = r.json()
#    if not data.get("results"):
#        raise ValueError(f"Could not geocode '{q}'")
#    item = data["results"][0]
#    lat = float(item["latitude"]); lon = float(item["longitude"])
#    label = item.get("name") or city
#    return lat, lon, label

WMO = {
    0:"Clear",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
    45:"Fog",48:"Rime fog",
    51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",
    61:"Light rain",63:"Rain",65:"Heavy rain",
    71:"Light snow",73:"Snow",75:"Heavy snow",
    80:"Rain showers",81:"Rain showers",82:"Violent rain showers",
    95:"Thunderstorm",96:"Thunderstorm w/ hail",99:"Thunderstorm w/ heavy hail"
}

def fetch_forecast(lat: float, lon: float, tzname: str):
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": tzname
        },
        timeout=15
    )
    r.raise_for_status()
    return r.json()

def format_message(city_label: str, tzname: str, daily: dict) -> str:
    code = int(daily["weathercode"][0])
    hi = round(float(daily["temperature_2m_max"][0]))
    lo = round(float(daily["temperature_2m_min"][0]))
    precip = int(daily.get("precipitation_probability_max", [0])[0] or 0)
    desc = WMO.get(code, f"Code {code}")
    today = tznow().strftime("%A, %b %d")
    return (
        f"Good morning! {city_label} forecast for {today}\n"
        f"{desc}\nHigh {hi}° / Low {lo}°   •   💧 {precip}%"
    )

#def notify(msg: str):
#    if not NOTIFY_URL:
#        print("[notify] NOTIFY_URL not set — printing message:\n", msg)
#        return
#    payload = {"source": SOURCE_NAME, "message": msg}
#    try:
#        r = requests.post(NOTIFY_URL, json=payload, timeout=10)
#        print(f"[notify] {r.status_code} {r.text[:120]!r}")
#    except Exception as e:
#        print("[notify-error]", e)

def notify(msg: str):
    if not NOTIFY_URL:
        print("[notify] NOTIFY_URL not set — printing message:\n", msg)
        return
    if not NOTIFY_TO:
        print("[notify] NOTIFY_TO not set — gateway requires a recipient. Printing message:\n", msg)
        return

    # Try common payloads your gateway may accept
    attempts = []

    # A) Preferred: Authorization header, minimal body
    headers = {"Authorization": f"Bearer {NOTIFY_TOKEN}"} if NOTIFY_TOKEN else {}
    attempts.append( ({"to": NOTIFY_TO, "message": msg}, headers) )

    # B) Fallback: include token in body
    if NOTIFY_TOKEN:
        attempts.append( ({"to": NOTIFY_TO, "message": msg, "token": NOTIFY_TOKEN}, {}) )

    last_err = None
    for body, headers in attempts:
        try:
            r = requests.post(NOTIFY_URL, json=body, headers=headers, timeout=15)
            if 200 <= r.status_code < 300:
                print(f"[notify] {r.status_code} OK")
                return
            last_err = f"{r.status_code} {r.text[:160]!r}"
        except Exception as e:
            last_err = str(e)

    print("[notify] delivery failed:", last_err)
    print("[notify] payload tried:", body)


def run_once(city: Optional[str]=None, state: Optional[str]=None) -> dict:
    c = (city or CITY).strip()
    s = (state or STATE).strip() if (state or STATE) else None
    lat, lon, label = geocode(c, s)
    data = fetch_forecast(lat, lon, TZ)
    daily = data.get("daily", {})
    if not daily:
        raise RuntimeError("No daily forecast returned")
    msg = format_message(label, TZ, daily)
    return {"city": label, "message": msg, "raw": daily}

#def run_once(city: Optional[str]=None, state: Optional[str]=None) -> dict:
#    c = (city or CITY).strip()
#    s = (state or STATE).strip() if (state or STATE) else None
#    lat, lon, label = geocode(c, s)
#    data = fetch_forecast(lat, lon, TZ)
#    daily = data.get("daily", {})
#    if not daily:
#        raise RuntimeError("No daily forecast returned")
#    msg = format_message(label, TZ, daily)
#    return {"city": label, "message": msg, "raw": daily}

# ------------ Scheduler thread ------------
def scheduler_loop():
    print(f"[sched] cron='{CRON}' tz='{TZ}' (source={SOURCE_NAME})")
    # fire once on boot
    try:
        out = run_once()
        notify(out["message"])
    except Exception as e:
        print("[sched] initial run failed:", e)
    # compute next
    nxt = next_run(tznow(), CRON)
    print(f"[sched] next run at {nxt.isoformat()}")
    while True:
        now = tznow()
        if now >= nxt:
            try:
                out = run_once()
                notify(out["message"])
            except Exception as e:
                print("[sched] run failed:", e)
            nxt = next_run(tznow(), CRON)
            print(f"[sched] next run at {nxt.isoformat()}")
        time.sleep(1)

# ------------ FastAPI app ------------
app = FastAPI(title="weather-service", version="1.0.0")

@app.get("/health")
def health():
    return {"ok": True, "tz": TZ, "cron": CRON, "city": CITY, "state": STATE, "notify_url": bool(NOTIFY_URL)}

@app.get("/today")
def today(city: Optional[str] = Query(None), state: Optional[str] = Query(None)):
    try:
        out = run_once(city, state)
        return out
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

def main():
    # start scheduler in background
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
    # start HTTP server
    uvicorn.run(app, host="0.0.0.0", port=8789, log_level="info")

if __name__ == "__main__":
    main()
