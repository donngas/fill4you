# Polish plan

This branch strengthened the working MVP without changing its core user flow.

1. **Launch and security**
   - CSRF protection for browser-session form actions.
   - Production configuration checks and deployment assumptions.
   - Clearer OAuth and Google Calendar sync outcomes.
2. **Integration confidence**
   - Coverage for OAuth token storage/refresh and Google Calendar edge cases.
   - A repeatable live When2meet smoke checklist.
3. **Calendar selection**
   - Persist per-user calendar choices.
   - Primary calendar selected by default; others opt-in.
   - Sync selected calendars while retaining local event edits and exclusions.

Status: complete.
