# fill4you

fill4you creates a first-draft availability for When2meet from a university timetable, Google Calendar events, and manual busy-time blocks.

## Roadmap

- Korean-first interface with an English option.
- Google sign-in for accounts and Google Calendar access.
- Asia/Seoul timezone for MVP calculations.
- Three busy-time sources:
  - Recurring weekly timetable blocks.
  - Google Calendar events, busy by default, with calendar selection.
  - Editable manual one-time and recurring blocks.
- Form-based editing on the left and a read-only calendar preview on the right.
- Periodic Google Calendar sync and a refresh when the bookmarklet runs.
- FastAPI backend serving a simple HTML/CSS/JavaScript frontend.
- uv-based Python workflow; keep Docker and deployment in mind.
- A bookmarklet that runs on When2meet, reads poll slots and current availability, requests an availability mask, and updates only changed ranges after confirmation.
- A copyable and revocable scoped helper token for the bookmarklet.
- No exposure of Google OAuth tokens, calendar event details, or When2meet credentials to the bookmarklet.
- Keep undocumented When2meet integration isolated behind a small adapter.
