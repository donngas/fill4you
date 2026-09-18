# ruff: noqa: E501

import json
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.accounts.service import get_user
from app.bookmarklet import service
from app.core.config import Settings, get_settings
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
    label: str = Form("fill4you"),
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
def bookmarklet_script(request: Request, token: str, settings: Settings = Depends(get_settings)):
    # Cloudflare Tunnel reaches this service over its private HTTP network.
    # The request URL therefore cannot be used for browser-side requests.
    api_base = settings.public_base_url or str(request.base_url).rstrip("/")
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
  const INCLUDE_BUSY_TITLES = true;
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
    getChanges(desired, current) {{
      if (!Array.isArray(desired) || desired.length !== current.length) throw new Error('The availability response does not match this poll.');
      return desired.flatMap((value, index) => {{
        if (value === current[index]) return [];
        const element = document.getElementById(`YouTime${{window.TimeOfSlot[index]}}`);
        if (!element) throw new Error('When2meet slot elements are unavailable.');
        return [{{ element, desired: value }}];
      }});
    }},
    getPreviewSlots(desired, current) {{
      if (!Array.isArray(desired) || desired.length !== current.length) throw new Error('The availability response does not match this poll.');
      return desired.flatMap((value, index) => {{
        if (!value || value === current[index]) return [];
        const element = document.getElementById(`YouTime${{window.TimeOfSlot[index]}}`);
        if (!element) throw new Error('When2meet slot elements are unavailable.');
        return [{{ element, desired: value }}];
      }});
    }},
    showPreview(changes, busyBlocks) {{
      const styleId = 'fill4you-preview-style';
      let style = document.getElementById(styleId);
      if (!style) {{
        style = document.createElement('style');
        style.id = styleId;
        document.head.appendChild(style);
      }}
      style.textContent = `
          .fill4you-preview-add {{ box-shadow: inset 0 0 0 999px rgba(132, 201, 255, .7) !important; }}
          .fill4you-preview-busy {{ box-shadow: inset 0 0 0 999px rgba(225, 70, 70, .78) !important; }}
          #fill4you-preview-shield {{ position: fixed; inset: 0; z-index: 2147483647; background: rgba(15, 23, 42, .08); font-family: Arial, sans-serif; }}
          .fill4you-busy-label {{ position: fixed; z-index: 1; max-width: 120px; overflow: hidden; padding: 3px 6px; border: 1px solid rgba(255, 255, 255, .9); border-radius: 5px; background: rgba(112, 20, 25, .92); color: #fff; font: bold 11px/1.2 Arial, sans-serif; pointer-events: none; text-align: center; text-overflow: ellipsis; text-shadow: 0 1px 1px rgba(0, 0, 0, .45); white-space: nowrap; }}
          .fill4you-busy-overlay span {{ display: inline-block; max-width: 100%; padding: 2px 4px; overflow: hidden; background: rgba(255, 248, 239, .8); text-overflow: ellipsis; white-space: nowrap; }}
          #fill4you-preview-panel {{ position: fixed; z-index: 2; left: 50%; top: 50%; width: min(360px, calc(100vw - 32px)); padding: 20px; border-radius: 14px; background: #fff; box-shadow: 0 18px 50px rgba(15, 23, 42, .3); color: #172033; text-align: left; transform: translate(-50%, -50%); cursor: grab; touch-action: none; }}
          #fill4you-preview-panel h2 {{ margin: 0 0 8px; font-size: 20px; }}
          #fill4you-preview-panel p {{ margin: 8px 0; line-height: 1.45; }}
          #fill4you-preview-panel .fill4you-legend {{ font-size: 13px; color: #52617a; }}
          #fill4you-preview-panel .fill4you-actions {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }}
          #fill4you-preview-panel button {{ border: 0; border-radius: 8px; padding: 9px 13px; cursor: pointer; font: inherit; }}
          #fill4you-cancel {{ background: #e8edf5; color: #172033; }}
          #fill4you-apply {{ background: #2563eb; color: #fff; }}
      `;
      changes.forEach((change) => change.element.classList.add('fill4you-preview-add'));
      const shield = document.createElement('div');
      shield.id = 'fill4you-preview-shield';
      const additions = changes.filter((change) => change.desired).length;
      shield.innerHTML = `<section id="fill4you-preview-panel" role="dialog" aria-modal="true" aria-labelledby="fill4you-preview-title"><h2 id="fill4you-preview-title">fill4you 미리보기</h2><p>변경 예정 슬롯과 생성된 바쁨 시간을 표시합니다.</p><p class="fill4you-legend">파랑 ${{additions}}개: 가능으로 변경 · 빨강 ${{busyBlocks.length}}개: 바쁨</p><div class="fill4you-actions"><button id="fill4you-cancel" type="button">취소</button><button id="fill4you-apply" type="button">적용</button></div></section>`;
      document.body.appendChild(shield);
      const busyElements = new Set();
      const busyLabels = [];
      busyBlocks.forEach((busyBlock) => {{
        const slots = busyBlock.slot_indexes.flatMap((index) => {{
          const element = document.getElementById(`YouTime${{window.TimeOfSlot[index]}}`);
          if (!element) return [];
          const rect = element.getBoundingClientRect();
          busyElements.add(element);
          return [{{ element, left: Math.round(rect.left), top: rect.top, bottom: rect.bottom, width: rect.width }}];
        }});
        const columns = new Map();
        slots.forEach((slot) => {{ const column = columns.get(slot.left) || []; column.push(slot); columns.set(slot.left, column); }});
        columns.forEach((column) => {{
          column.sort((first, second) => first.top - second.top);
          const ranges = [];
          column.forEach((slot) => {{
            const range = ranges.at(-1);
            if (range && slot.top <= range.end.bottom + 2) range.end = slot;
            else ranges.push({{ start: slot, end: slot }});
          }});
          ranges.forEach((range) => {{
            if (busyBlock.title) {{
              const label = document.createElement('span');
              label.className = 'fill4you-busy-label';
              label.textContent = busyBlock.title;
              shield.appendChild(label);
              busyLabels.push({{ label, startElement: range.start.element, endElement: range.end.element }});
            }}
          }});
        }});
      }});
      busyElements.forEach((element) => element.classList.add('fill4you-preview-busy'));
      const positionBusyLabels = () => {{
        busyLabels.forEach((entry) => {{
          const start = entry.startElement.getBoundingClientRect();
          const end = entry.endElement.getBoundingClientRect();
          entry.label.style.left = `${{start.left + start.width / 2}}px`;
          entry.label.style.top = `${{(start.top + end.bottom) / 2}}px`;
          entry.label.style.transform = 'translate(-50%, -50%)';
        }});
      }};
      let positionFrame = null;
      const scheduleLabelPosition = () => {{
        if (positionFrame) return;
        positionFrame = requestAnimationFrame(() => {{ positionFrame = null; positionBusyLabels(); }});
      }};
      positionBusyLabels();
      window.addEventListener('scroll', scheduleLabelPosition, true);
      window.addEventListener('resize', scheduleLabelPosition);
      return new Promise((resolve) => {{
        const panel = shield.querySelector('#fill4you-preview-panel');
        const clear = () => {{
          changes.forEach((change) => {{
            change.element.classList.remove('fill4you-preview-add');
          }});
          busyElements.forEach((element) => element.classList.remove('fill4you-preview-busy'));
          window.removeEventListener('scroll', scheduleLabelPosition, true);
          window.removeEventListener('resize', scheduleLabelPosition);
          if (positionFrame) cancelAnimationFrame(positionFrame);
          shield.remove();
          document.removeEventListener('keydown', onKeyDown);
        }};
        const finish = (accepted) => {{ clear(); resolve(accepted); }};
        const onKeyDown = (event) => {{
          if (event.key === 'Escape') finish(false);
          if (event.key === 'Enter') finish(true);
        }};
        shield.querySelector('#fill4you-cancel').addEventListener('click', () => finish(false));
        shield.querySelector('#fill4you-apply').addEventListener('click', () => finish(true));
        shield.addEventListener('click', (event) => {{ if (event.target === shield) finish(false); }});
        let drag = null;
        panel.addEventListener('pointerdown', (event) => {{
          if (event.target.closest('button')) return;
          const rect = panel.getBoundingClientRect();
          panel.style.left = `${{rect.left}}px`;
          panel.style.top = `${{rect.top}}px`;
          panel.style.transform = 'none';
          panel.style.cursor = 'grabbing';
          drag = {{ pointerId: event.pointerId, offsetX: event.clientX - rect.left, offsetY: event.clientY - rect.top }};
          panel.setPointerCapture(event.pointerId);
        }});
        panel.addEventListener('pointermove', (event) => {{
          if (!drag || drag.pointerId !== event.pointerId) return;
          const rect = panel.getBoundingClientRect();
          const left = Math.max(0, Math.min(window.innerWidth - rect.width, event.clientX - drag.offsetX));
          const top = Math.max(0, Math.min(window.innerHeight - rect.height, event.clientY - drag.offsetY));
          panel.style.left = `${{left}}px`;
          panel.style.top = `${{top}}px`;
        }});
        panel.addEventListener('pointerup', (event) => {{
          if (!drag || drag.pointerId !== event.pointerId) return;
          panel.releasePointerCapture(event.pointerId);
          panel.style.cursor = 'grab';
          drag = null;
        }});
        document.addEventListener('keydown', onKeyDown);
        shield.querySelector('#fill4you-apply').focus();
      }});
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
  if (window.__fill4youRunning) {{ alert('fill4you: a preview is already open.'); return; }}
  if (!adapter.validatePage()) {{ alert('fill4you: this does not look like a supported When2meet poll.'); return; }}
  if (!adapter.isLoggedIn()) {{ alert('fill4you: log into this When2meet poll first.'); return; }}
  window.__fill4youRunning = true;
  fetch(`${{API_BASE}}/api/v1/availability/when2meet`, {{
    method: 'POST', headers: {{ 'Content-Type': 'application/json', Authorization: `Bearer ${{TOKEN}}` }},
    body: JSON.stringify({{ slots: adapter.getSlots(), slot_minutes: 15, include_busy_titles: INCLUDE_BUSY_TITLES }})
  }}).then(async (response) => {{
    if (!response.ok) throw new Error((await response.json()).detail || 'Availability request failed.');
    return response.json();
  }}).then(async (payload) => {{
    const current = adapter.getCurrentAvailability();
    const changes = adapter.getChanges(payload.desired, current);
    if (!changes.length) {{ alert('fill4you: your poll already matches the generated availability.'); return; }}
    const previewSlots = adapter.getPreviewSlots(payload.desired, current);
    if (!await adapter.showPreview(previewSlots, payload.busy_blocks || [])) return;
    const ranges = await adapter.applyAvailability(payload.desired, current);
    alert(`fill4you: applied ${{ranges}} changed range(s). Please review the poll.`);
  }}).catch((error) => alert(`fill4you: ${{error.message}}`)).finally(() => {{ window.__fill4youRunning = false; }});
}})();"""
