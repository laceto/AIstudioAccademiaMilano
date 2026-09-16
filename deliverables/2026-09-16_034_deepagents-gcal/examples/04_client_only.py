"""No LLM: the typed client on its own.

`client`, `models`, `scheduling` and `timeutils` import without LangChain, so this
script is also the cheapest way to check that credentials and scopes are working.
"""

from deepagents_gcal import EventDraft, GoogleCalendarClient

client = GoogleCalendarClient.from_env(dry_run=True)

for calendar in client.list_calendars():
    print(f"{calendar.id:<30} {calendar.access_role}")

for event in client.list_events(time_min="today", time_max="+7d"):
    print(f"{event.start} → {event.end}  {event.summary}")

for slot in client.find_free_slots(60, time_min="tomorrow", time_max="+5d"):
    print(f"free: {slot.start:%a %d %b %H:%M} ({slot.duration_minutes} min)")

created = client.create_event(
    EventDraft(summary="Retro", start="tomorrow", duration_minutes=45, location="Milano")
)
print("created (dry run):", created.to_summary())
