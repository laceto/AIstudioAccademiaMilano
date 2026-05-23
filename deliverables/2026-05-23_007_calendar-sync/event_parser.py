"""
event_parser.py — Extract structured calendar event from any natural language message.

Uses GPT-4o-mini with structured output (guaranteed JSON schema).
No regex. No brittle string parsing.
"""

import os
from datetime import date
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    title: str = Field(description="Short event title, e.g. 'Team standup'")
    date: str = Field(description="ISO 8601 date, e.g. '2026-05-25'")
    start_time: str = Field(description="HH:MM in 24h, e.g. '14:30'")
    end_time: str = Field(description="HH:MM in 24h. Default: start_time + 1h")
    location: Optional[str] = Field(default=None, description="Physical address or video URL")
    description: Optional[str] = Field(default=None, description="Any additional context")
    timezone: str = Field(default="Europe/Rome")


def extract_event(message: str, today: Optional[str] = None) -> CalendarEvent:
    """Parse natural language message into a CalendarEvent."""
    today = today or date.today().isoformat()
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    resp = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Today is {today}. "
                    "Extract calendar event details from the user message. "
                    "Resolve relative dates ('tomorrow', 'next Monday') to ISO 8601. "
                    "If end_time is not specified, add 1 hour to start_time. "
                    "Timezone default: Europe/Rome."
                ),
            },
            {"role": "user", "content": message},
        ],
        response_format=CalendarEvent,
    )
    return resp.choices[0].message.parsed


if __name__ == "__main__":
    samples = [
        "Pranzo di lavoro con Marco domani alle 13 al Ristorante Borghese, Milano",
        "Call with London team next Tuesday at 3pm",
        "Board meeting Friday 9:00-11:00 at HQ via Zoom https://zoom.us/j/123",
    ]
    for msg in samples:
        event = extract_event(msg)
        print(f"Input: {msg}")
        print(f"  → {event.title} | {event.date} {event.start_time}-{event.end_time} | {event.location}")
        print()
