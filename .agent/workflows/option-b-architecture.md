---
description: Option B Architecture - Django API + React UI with Clean As You Go approach
---

# Option B Architecture Mode

> **AUTOMATIC**: This architecture is applied to ALL features and bugfixes without needing to be asked.
> Every time I touch a surface, I tidy it to be Option B compliant.

## Core Principles
- **Django** = API-only backend (JSON responses) + minimal HTML shells
- **React** = Primary UI, calls `/api/...` endpoints
- **PostgreSQL** via Django ORM

---

## When Touching API Endpoints (`/api/...`)

1. **JSON-only contract**
   - Success → JSON response
   - Error → `{ "error": "Short message", "details": "Optional context" }`
   - Never return HTML or templates from API views

2. **No template helpers** in API views
   - Don't use `render()` or `json_script`
   - Use DRF `APIView`/`Response` or Django `JsonResponse`

3. **CSRF for APIs**
   - CSRF failures must return JSON, not HTML CSRF page
   - Use/create JSON CSRF failure handler for API routes

4. **Error handling**
   - Wrap risky code in try/except
   - On error → JSON response + server-side log
   - Never let Django fall back to HTML debug templates

---

## When Touching UI Routes (`/receipts/`, `/ai-companion/`, etc.)

1. **Make Django view a thin shell**
   - Return simple HTML with `<div id="root"></div>`
   - Load React bundle via `{% static %}`
   - Remove complex Django template logic

2. **Push data to React via APIs**
   - React calls `/api/...` for data
   - Handle loading/error states in React
   - No large JSON blobs via `json_script`

3. **Error UX in React**
   - Check `res.ok` before parsing
   - Handle `{ error: ... }` with friendly banners
   - Handle non-JSON responses gracefully

---

## "Clean As You Go" Checklist

For each change:

- [ ] Identify which API endpoints you're touching
- [ ] Identify which UI routes you're touching
- [ ] For those endpoints/pages:
  - [ ] API returns JSON-only (success & error)
  - [ ] No template logic in API views
  - [ ] Django template is just a React mount shell
  - [ ] React fetch/parse is robust
- [ ] Delete unused legacy templates when migrating to React

---

## Safety Rules

- Don't remove working features unless migrating them
- Don't introduce new template logic where React could work
- Keep backward compatibility when changing URLs/contracts
- Only clean what you touch - no big bang rewrites
