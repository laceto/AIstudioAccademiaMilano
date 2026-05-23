"""
event_parser.py — Extract a structured CalendarEvent from any natural language message.
Uses GPT-4o-mini with Pydantic structured output.
"""

import os
from datetime import date
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    title: str = Field(description="Short event title")
    date: str = Field(description="ISO 8601 date, e.g. '2026-05-25'")
    start_time: str = Field(description="HH:MM in 24h")
    end_time: str = Field(description="HH:MM in 24h. Default: start_time + 1h")
    location: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    timezone: str = Field(default="Europe/Rome")


def extract_event(message: str, today: Optional[str] = None) -> CalendarEvent:
    today = today or date.today().isoformat()
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Today is {today}. Extract calendar event details. Resolve relative dates to ISO 8601. Default end_time = start_time + 1h. Timezone default: Europe/Rome."},
            {"role": "user", "content": message},
        ],
        response_format=CalendarEvent,
    )
    return resp.choices[0].message.parsed


if __name__ == "__main__":
    samples = [
        "Pranzo di lavoro con Marco domani alle 13 al Ristorante Borghese, Milano",
        "Board meeting Friday 9:00-11:00 via Zoom https://zoom.us/j/123",
    ]
    for msg in samples:
        ev = extract_event(msg)
        print(f"{msg}\n  → {ev.title} | {ev.date} {ev.start_time}-{ev.end_time}\n")
