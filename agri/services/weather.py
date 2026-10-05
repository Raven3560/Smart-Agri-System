"""Weather intelligence module (Open-Meteo API, no API key required).

Provides current conditions, a 7-day forecast and recent past days, including
FAO-56 reference evapotranspiration (ET0) which drives the irrigation module.

Resilience for demos and poor connectivity:
1. responses are cached in memory for 30 minutes,
2. the last good response per location is stored on disk and used if the API
   is unreachable (marked as "cached"),
3. if nothing is available, a clearly labelled seasonal estimate is returned.
"""
import datetime as dt
import json
import logging
import os
import threading
import time

import requests

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT = 12
MEMORY_TTL = 30 * 60

DAILY_VARS = [
    "weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "precipitation_probability_max", "et0_fao_evapotranspiration", "wind_speed_10m_max",
    "relative_humidity_2m_mean", "shortwave_radiation_sum", "sunrise", "sunset",
]
CURRENT_VARS = [
    "temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation",
    "weather_code", "wind_speed_10m", "is_day",
]

# WMO weather interpretation codes -> (label, icon name)
WMO = {
    0: ("Clear sky", "sun"), 1: ("Mainly clear", "sun"), 2: ("Partly cloudy", "cloud-sun"),
    3: ("Overcast", "cloud"), 45: ("Fog", "fog"), 48: ("Rime fog", "fog"),
    51: ("Light drizzle", "drizzle"), 53: ("Drizzle", "drizzle"), 55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"), 57: ("Freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"), 77: ("Snow grains", "snow"),
    80: ("Rain showers", "rain"), 81: ("Rain showers", "rain"), 82: ("Violent showers", "rain"),
    85: ("Snow showers", "snow"), 86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "storm"), 96: ("Thunderstorm with hail", "storm"), 99: ("Thunderstorm with hail", "storm"),
}

_memory = {}
_lock = threading.Lock()


class WeatherError(Exception):
    pass


def describe(code):
    return WMO.get(int(code) if code is not None else -1, ("Unknown", "cloud"))


def geocode(query, count=6):
    query = (query or "").strip()
    if len(query) < 2:
        return []
    resp = requests.get(GEOCODE_URL, params={"name": query, "count": count, "language": "en", "format": "json"},
                        timeout=TIMEOUT)
    resp.raise_for_status()
    out = []
    for r in resp.json().get("results", []) or []:
        parts = [r.get("name"), r.get("admin2") if r.get("admin2") != r.get("name") else None,
                 r.get("admin1"), r.get("country")]
        out.append({
            "name": r.get("name"),
            "label": ", ".join(p for p in parts if p),
            "lat": round(r["latitude"], 4),
            "lon": round(r["longitude"], 4),
        })
    return out


def _cache_path(cache_dir, lat, lon):
    return os.path.join(cache_dir, f"wx_{lat:.2f}_{lon:.2f}.json")


def _fetch(lat, lon, past_days):
    params = {
        "latitude": lat, "longitude": lon, "timezone": "auto",
        "current": ",".join(CURRENT_VARS), "daily": ",".join(DAILY_VARS),
        "past_days": past_days, "forecast_days": 7,
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _normalise(raw, source):
    daily = raw["daily"]
    days = []
    for i, date in enumerate(daily["time"]):
        def val(key, default=0.0):
            v = daily.get(key, [None] * len(daily["time"]))[i]
            return default if v is None else v

        code = val("weather_code", 0)
        label, icon = describe(code)
        days.append({
            "date": date,
            "code": int(code), "label": label, "icon": icon,
            "tmax": round(val("temperature_2m_max"), 1), "tmin": round(val("temperature_2m_min"), 1),
            "rain": round(val("precipitation_sum"), 1),
            "rain_prob": int(val("precipitation_probability_max", 0)),
            "et0": round(val("et0_fao_evapotranspiration"), 2),
            "wind": round(val("wind_speed_10m_max"), 1),
            "rh": round(val("relative_humidity_2m_mean", 60)),
            "radiation": round(val("shortwave_radiation_sum"), 1),
            "sunrise": (val("sunrise", "") or "")[-5:], "sunset": (val("sunset", "") or "")[-5:],
        })
    cur = raw.get("current", {})
    label, icon = describe(cur.get("weather_code"))
    current = {
        "time": cur.get("time"), "temp": cur.get("temperature_2m"), "feels_like": cur.get("apparent_temperature"),
        "rh": cur.get("relative_humidity_2m"), "rain": cur.get("precipitation"), "wind": cur.get("wind_speed_10m"),
        "code": cur.get("weather_code"), "label": label, "icon": icon, "is_day": cur.get("is_day", 1),
    }
    today = (cur.get("time") or "")[:10] or dt.date.today().isoformat()
    if source == "cached":
        # Saved data may be days old: align "today" with the real date.
        today = dt.date.today().isoformat()
    today_index = next((i for i, d in enumerate(days) if d["date"] == today), None)
    if today_index is None:
        today_index = len(days) if days and days[-1]["date"] < today else max(0, len(days) - 7)
    if today_index >= len(days):
        raise ValueError("Saved weather data is too old to use")
    return {
        "source": source,
        "timezone": raw.get("timezone"),
        "elevation": raw.get("elevation"),
        "current": current,
        "days": days,
        "today_index": today_index,
        "today": today,
        "past": days[:today_index],
        "forecast": days[today_index:],
        "fetched_at": raw.get("_fetched_at"),
    }


def estimated_weather(past_days=14):
    """Clearly labelled fallback when no live or cached data exists."""
    today = dt.date.today()
    days = []
    for offset in range(-past_days, 7):
        d = today + dt.timedelta(days=offset)
        days.append({"date": d.isoformat(), "code": 1, "label": "Estimated", "icon": "cloud-sun",
                     "tmax": 32.0, "tmin": 20.0, "rain": 0.0, "rain_prob": 0, "et0": 4.5, "wind": 8.0,
                     "rh": 60, "radiation": 18.0, "sunrise": "06:10", "sunset": "18:00"})
    return {
        "source": "estimated", "timezone": None, "elevation": None,
        "current": {"time": None, "temp": None, "feels_like": None, "rh": None, "rain": None, "wind": None,
                    "code": None, "label": "Unavailable", "icon": "cloud", "is_day": 1},
        "days": days, "today_index": past_days, "today": today.isoformat(),
        "past": days[:past_days], "forecast": days[past_days:], "fetched_at": None,
    }


def get_weather(lat, lon, cache_dir, past_days=14, allow_estimate=True):
    """Return normalised weather for a location.

    ``source`` is one of ``live``, ``cached`` (API unreachable, last saved
    data used) or ``estimated``.
    """
    lat, lon = round(float(lat), 2), round(float(lon), 2)
    past_days = max(0, min(int(past_days), 60))
    key = (lat, lon, past_days)
    with _lock:
        hit = _memory.get(key)
        if hit and time.time() - hit[0] < MEMORY_TTL:
            return hit[1]

    try:
        raw = _fetch(lat, lon, past_days)
        raw["_fetched_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        result = _normalise(raw, "live")
        os.makedirs(cache_dir, exist_ok=True)
        with open(_cache_path(cache_dir, lat, lon), "w", encoding="utf-8") as fh:
            json.dump({"past_days": past_days, "raw": raw}, fh)
        with _lock:
            _memory[key] = (time.time(), result)
        return result
    except (requests.RequestException, KeyError, ValueError) as exc:
        log.warning("Weather API failed for %s,%s: %s", lat, lon, exc)

    path = _cache_path(cache_dir, lat, lon)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            return _normalise(saved["raw"], "cached")
        except (OSError, ValueError, KeyError):
            pass
    if allow_estimate:
        return estimated_weather(past_days)
    raise WeatherError("Weather service is unreachable and no cached data is available.")


def farm_advisories(wx):
    """Short weather-based farming advisories for the next 3 days."""
    out = []
    nxt = wx["forecast"][:3]
    if not nxt:
        return out
    rain_days = [d for d in nxt if d["rain"] >= 2 and d["rain_prob"] >= 50]
    if rain_days:
        d = rain_days[0]
        out.append({"level": "info", "icon": "rain", "title": "Rain expected",
                    "text": f"About {d['rain']} mm of rain is likely on {pretty_date(d['date'])} "
                            f"({d['rain_prob']}% chance). Hold irrigation and avoid spraying before rain."})
    hot = [d for d in nxt if d["tmax"] >= 38]
    if hot:
        out.append({"level": "warning", "icon": "sun", "title": "Heat stress risk",
                    "text": f"Temperature may reach {hot[0]['tmax']} °C. Irrigate in the early morning or evening "
                            "and use mulch to reduce evaporation."})
    cold = [d for d in nxt if d["tmin"] <= 4]
    if cold:
        out.append({"level": "warning", "icon": "snow", "title": "Frost risk",
                    "text": f"Night temperature may drop to {cold[0]['tmin']} °C. A light irrigation in the evening "
                            "helps protect crops from frost."})
    windy = [d for d in nxt if d["wind"] >= 20]
    if windy:
        out.append({"level": "info", "icon": "wind", "title": "Windy conditions",
                    "text": f"Winds up to {windy[0]['wind']} km/h on {pretty_date(windy[0]['date'])}. "
                            "Avoid pesticide spraying and sprinkler irrigation in strong wind."})
    humid = [d for d in nxt if d["rh"] >= 85 and 15 <= (d["tmax"] + d["tmin"]) / 2 <= 30]
    if humid:
        out.append({"level": "warning", "icon": "fog", "title": "Fungus weather",
                    "text": "Humid weather ahead favours fungal diseases such as blights and mildews. "
                            "Inspect crops closely and keep leaves dry."})
    if not out:
        out.append({"level": "good", "icon": "check", "title": "Nothing to worry about",
                    "text": "No weather problems in the next 3 days. A good time for field work and spraying."})
    return out


def pretty_date(iso, today=None):
    try:
        d = dt.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso
    today = today or dt.date.today()
    if d == today:
        return "today"
    if d == today + dt.timedelta(days=1):
        return "tomorrow"
    return d.strftime("%a %d %b")
