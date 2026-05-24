# Milan Weather Dashboard

Minimal Streamlit app showing current weather for Milan.

## Credentials

| Variable | Where to get it | Required |
|---|---|---|
| `OPENWEATHERMAP_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) — free tier | Yes |

Free tier: 60 calls/min, 1M calls/month. Key activates ~10 min after signup.

## Run

```bash
pip install -r requirements.txt

export OPENWEATHERMAP_API_KEY=your_key_here
streamlit run main.py
```

Or with Streamlit secrets — create `.streamlit/secrets.toml`:

```toml
OPENWEATHERMAP_API_KEY = "your_key_here"
```

Then just:

```bash
streamlit run main.py
```

## What it shows

- Temperature + feels like
- Humidity
- Wind speed
- Min / max temperature
- Sunrise / sunset times
- Visibility
- Refresh button
