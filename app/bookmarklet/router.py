# ruff: noqa: E501

import json
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.accounts.service import get_user
from app.bookmarklet import service
from app.core.csrf import require_csrf
from app.core.database import get_db

router = APIRouter(prefix="/bookmarklet", tags=["bookmarklet"])


def _user_id(request: Request, db: Session) -> int:
    user = get_user(db, request.session.get("user_id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign-in required")
    return user.id


@router.post("/tokens")
def create_token(
    request: Request,
    label: str = Form("When2meet bookmarklet"),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    _, raw_token = service.create_token(db, _user_id(request, db), label)
    request.session["new_bookmarklet_token"] = raw_token
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/tokens/{token_id}/revoke")
def revoke_token(
    token_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if not service.revoke_token(db, _user_id(request, db), token_id):
        raise HTTPException(status_code=404, detail="Bookmarklet token not found")
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/script.js")
def bookmarklet_script(request: Request, token: str):
    api_base = str(request.base_url).rstrip("/")
    script = _script(api_base, token)
    return PlainTextResponse(
        script, media_type="application/javascript", headers={"Cache-Control": "no-store"}
    )


def bookmarklet_url(api_base: str, raw_token: str) -> str:
    script_url = f"{api_base.rstrip('/')}/bookmarklet/script.js?{urlencode({'token': raw_token})}"
    return f"javascript:(()=>{{const s=document.createElement('script');s.src={json.dumps(script_url)};document.body.appendChild(s)}})()"


def _script(api_base: str, token: str) -> str:
    return f"""(() => {{
  const API_BASE = {json.dumps(api_base)};
  const TOKEN = {json.dumps(token)};
  const adapter = {{
    validatePage() {{ return Array.isArray(window.TimeOfSlot) && Array.isArray(window.AvailableAtSlot); }},
    isLoggedIn() {{ return Number(window.UserID) !== 0; }},
    getSlots() {{
      return window.TimeOfSlot.map((value) => {{
        const numeric = Number(value);
        return new Date(Math.abs(numeric) < 100000000000 ? numeric * 1000 : numeric).toISOString();
      }});
    }},
    getCurrentAvailability() {{
      return window.AvailableAtSlot.map((users) => Array.isArray(users) && users.includes(window.UserID));
    }},
    async applyAvailability(desired, current) {{
      if (typeof window.SelectFromHere !== 'function' || typeof window.SelectToHere !== 'function') throw new Error('When2meet selection functions are unavailable.');
      const changed = desired.flatMap((value, index) => {{
        if (value === current[index]) return [];
        const element = document.getElementById(`YouTime${{window.TimeOfSlot[index]}}`);
        if (!element) throw new Error('When2meet slot elements are unavailable.');
        const rect = element.getBoundingClientRect();
        return [{{ element, value, left: Math.round(rect.left), top: rect.top, bottom: rect.bottom }}];
      }});
      const columns = new Map();
      for (const slot of changed) {{
        const column = columns.get(slot.left) || [];
        column.push(slot); columns.set(slot.left, column);
      }}
      const ranges = [];
      for (const column of columns.values()) {{
        column.sort((first, second) => first.top - second.top);
        for (const slot of column) {{
          const range = ranges.at(-1);
          if (range && range.left === slot.left && range.value === slot.value && slot.top <= range.end.bottom + 2) {{
            range.end = slot;
          }} else {{
            ranges.push({{ left: slot.left, value: slot.value, start: slot, end: slot }});
          }}
        }}
      }}
      for (const range of ranges) {{
        window.SelectFromHere({{ target: range.start.element }});
        window.SelectToHere({{ target: range.end.element }});
        if (typeof window.SelectStop === 'function') window.SelectStop();
        await new Promise((resolve) => setTimeout(resolve, 100));
      }}
      return ranges.length;
    }}
  }};
  if (!adapter.validatePage()) {{ alert('fill4you: this does not look like a supported When2meet poll.'); return; }}
  if (!adapter.isLoggedIn()) {{ alert('fill4you: log into this When2meet poll first.'); return; }}
  fetch(`${{API_BASE}}/api/v1/availability/when2meet`, {{
    method: 'POST', headers: {{ 'Content-Type': 'application/json', Authorization: `Bearer ${{TOKEN}}` }},
    body: JSON.stringify({{ slots: adapter.getSlots(), slot_minutes: 15 }})
  }}).then(async (response) => {{
    if (!response.ok) throw new Error((await response.json()).detail || 'Availability request failed.');
    return response.json();
  }}).then(async (payload) => {{
    const current = adapter.getCurrentAvailability();
    const changed = payload.desired.filter((value, index) => value !== current[index]).length;
    if (!changed) {{ alert('fill4you: your poll already matches the generated availability.'); return; }}
    if (!confirm(`fill4you: update ${{changed}} changed slots? This replaces the current draft.`)) return;
    const ranges = await adapter.applyAvailability(payload.desired, current);
    alert(`fill4you: applied ${{ranges}} changed range(s). Please review the poll.`);
  }}).catch((error) => alert(`fill4you: ${{error.message}}`));
}})();"""
