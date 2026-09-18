# fill4you

fill4you creates a first-draft availability for When2meet from a university timetable, Google Calendar events, and manual busy-time blocks.

## Run locally

Copy `.env.example` to `.env`, set a secure `SESSION_SECRET`, then run `docker compose up --build`.
Set `FILL4YOU_PORT` if port 8000 is already in use.
Replace the example PostgreSQL and session values before deployment.
Google sign-in requires the credentials in `.env`; the development login is available until then.

## Roadmap

- Korean-first interface with an English option.
- Google sign-in for accounts and Google Calendar access.
- Asia/Seoul timezone for MVP calculations.
- Three busy-time sources:
  - Recurring weekly timetable blocks.
  - Google Calendar events, busy by default, with calendar selection and local-only per-event overrides.
  - Editable manual one-time and recurring blocks.
- Represent all three sources through one shared, editable busy-block model and a common left-side editing experience; preserve source-specific metadata separately.
- Keep timetable, Google Calendar, and manual blocks in separate categories (user-facing UI wise) while reusing the shared architecture and forms.
- Preserve a user's local Google Calendar event edit or exclusion across later syncs; do not write it back to Google.
- Form-based editing on the left and a read-only calendar preview on the right.
- Periodic Google Calendar sync and a refresh when the bookmarklet runs.
- FastAPI backend serving a simple HTML/CSS/JavaScript frontend.
- PostgreSQL for local and production environments, with Docker Compose as the canonical run method.
- uv-based Python workflow; keep Docker and deployment in mind.
- A bookmarklet that runs on When2meet, reads poll slots and current availability, requests an availability mask, and updates only changed ranges after confirmation.
- A copyable and revocable scoped helper token for the bookmarklet.
- No exposure of Google OAuth tokens, calendar event details, or When2meet credentials to the bookmarklet.
- Keep undocumented When2meet integration isolated behind a small adapter.

## Implementation phases

1. App foundation: FastAPI, configuration, database/migrations, base UI, i18n, and Dockerfile.
2. Accounts: local development login, then Google sign-in.
3. Shared busy-block model, timetable/manual block editing, and calendar preview.
4. Availability engine: normalize busy blocks and produce slot-aligned availability masks.
5. Bookmarklet helper tokens and the availability API contract.
6. Bookmarklet and isolated When2meet adapter: inspect slots, confirm changes, and apply changed ranges.
7. Google Calendar OAuth, calendar selection, periodic sync, and bookmarklet-triggered refresh.
8. Calendar availability integration, tests, error handling, security hardening, and deployment configuration.
