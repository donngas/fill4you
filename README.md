# fill4you

fill4you creates a first-draft availability for When2meet from a university timetable, Google Calendar events, and manual busy-time blocks.

## Run locally

Copy `.env.example` to `.env`, set a secure `SESSION_SECRET`, then run `docker compose up --build`.
Set `APP_PORT` if port 8000 is already in use.
Replace the example PostgreSQL and session values before deployment.
Configuration loads from `.env`; deployed process environment variables take precedence.
Google Calendar sync also requires a `GOOGLE_TOKEN_ENCRYPTION_KEY`; generate one with the command in `.env.example`, then sign out and sign in again so fill4you can store a refreshable token securely.
For the When2meet bookmarklet, set `CORS_ALLOWED_ORIGINS` to `["https://when2meet.com", "https://www.when2meet.com"]`.

## Deployment notes

- Use HTTPS and set `APP_ENV=production`, `SESSION_HTTPS_ONLY=true`, a 32+-character `SESSION_SECRET`, non-default PostgreSQL credentials, and real `ALLOWED_HOSTS`.
- Store OAuth credentials and `GOOGLE_TOKEN_ENCRYPTION_KEY` in deployment secrets. Keep the encryption key stable or users must reconnect Google.
- Keep `APP_WORKERS=1` until periodic Calendar sync moves to an external scheduler. Back up PostgreSQL, including encrypted OAuth-token rows.

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
7. Google Calendar OAuth and busy-event sync across the configured 7-day-past/90-day-future window; a 15-minute periodic sync and bookmarklet refresh keep it current, while local edits and exclusions survive normal refreshes.
8. Google Calendar selection: primary calendar selected by default; other subscribed/shared calendars are opt-in.
9. Security and operational hardening: CSRF protection, production configuration checks, encrypted OAuth-token refresh, tests, and deployment guidance.
10. Optional visual bookmarklet diff/undo experience and browser extension.
