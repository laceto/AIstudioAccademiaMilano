import os
import requests
import streamlit as st
from datetime import datetime

API_URL = "https://api.openweathermap.org/data/2.5/weather"
CITY = "Milan"
COUNTRY = "IT"

WEATHER_ICONS = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧️",
    "Drizzle": "🌦️",
    "Thunderstorm": "⛈️",
    "Snow": "❄️",
    "Mist": "🌫️",
    "Fog": "🌫️",
    "Haze": "🌫️",
}


def get_api_key() -> str | None:
    try:
        return st.secrets["OPENWEATHERMAP_API_KEY"]
    except Exception:
        return os.environ.get("OPENWEATHERMAP_API_KEY")


def fetch_weather(api_key: str) -> dict:
    resp = requests.get(
        API_URL,
        params={"q": f"{CITY},{COUNTRY}", "units": "metric", "appid": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def render(data: dict):
    main = data["main"]
    wind = data["wind"]
    weather = data["weather"][0]
    sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
    sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")
    icon = WEATHER_ICONS.get(weather["main"], "🌡️")

    st.title(f"{icon} Milan Weather")
    st.caption(f"Updated {datetime.now().strftime('%H:%M:%S')}  ·  {weather['description'].capitalize()}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Temperature", f"{main['temp']:.1f} °C", f"Feels like {main['feels_like']:.1f} °C")
    col2.metric("Humidity", f"{main['humidity']} %")
    col3.metric("Wind", f"{wind['speed']} m/s")

    col4, col5, col6 = st.columns(3)
    col4.metric("Min / Max", f"{main['temp_min']:.1f} / {main['temp_max']:.1f} °C")
    col5.metric("Sunrise", sunrise)
    col6.metric("Sunset", sunset)

    if "visibility" in data:
        st.caption(f"Visibility: {data['visibility'] / 1000:.1f} km")


st.set_page_config(page_title="Milan Weather", page_icon="🌦️", layout="centered")

api_key = get_api_key()

if not api_key:
    st.warning("Set your OpenWeatherMap API key:")
    st.code("export OPENWEATHERMAP_API_KEY=your_key_here")
    st.markdown("Or add it to `.streamlit/secrets.toml`:")
    st.code('[secrets]\nOPENWEATHERMAP_API_KEY = "your_key_here"')
    st.stop()

if st.button("🔄 Refresh"):
    st.rerun()

try:
    data = fetch_weather(api_key)
    render(data)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        st.error("Invalid API key. Check your OPENWEATHERMAP_API_KEY.")
    else:
        st.error(f"Weather API error: {e}")
except requests.exceptions.ConnectionError:
    st.error("No internet connection.")
except Exception as e:
    st.error(f"Unexpected error: {e}")
