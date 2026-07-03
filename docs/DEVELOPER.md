# RIYORA WELLNESS — Developer Manual

## Local Dev
- Backend runs on `:8001` via supervisord; frontend on `:3000`.
- Hot reload is enabled; only restart supervisord on `.env` change or dependency install.
- MongoDB URL comes from `MONGO_URL` in `/app/backend/.env`.

## Directory Layout
```
/app/
├── backend/
│   ├── app/
│   │   ├── core/       # config, deps, security, middleware
│   │   ├── db/         # mongo client, indexes, seeds
│   │   ├── models/     # pydantic models per phase
│   │   ├── routes/     # FastAPI routers, one per feature area
│   │   ├── services/   # business logic (payment, commission, brv, analytics, exports)
│   │   ├── utils/      # helpers (otp, audit, sanitize, file_validator, serializers, membership)
│   │   └── repositories/
│   ├── tests/          # pytest — one file per phase
│   ├── invoices/       # generated PDFs
│   ├── uploads/        # admin file uploads
│   └── server.py       # FastAPI entry
├── frontend/
│   ├── public/         # index.html, sw.js, manifest.json, robots.txt, sitemap.xml
│   └── src/
│       ├── components/ # shared: AdminShell, MobileShell, ErrorBoundary, ProtectedRoute…
│       ├── context/    # AuthContext
│       ├── lib/        # api client, formatters
│       ├── pages/      # one per screen (user + admin)
│       └── services/   # per-domain API wrappers
├── scripts/            # backup_mongo.sh, restore_mongo.sh
└── docs/               # DEPLOYMENT, SECURITY, ADMIN_MANUAL, BACKUP_RESTORE, DEVELOPER
```

## Conventions
- Use `search_replace` on existing files; do not rewrite unless substantial.
- All routes prefixed `/api/` (Kubernetes ingress requirement).
- ISO 8601 strings (UTC) for dates. `datetime.now(timezone.utc)`.
- Soft-delete via `deleted_at: str | None` on every collection.
- Every admin write action goes through `utils/audit.log_action(...)`.

## Adding a new admin page
1. Create the route file under `/app/backend/app/routes/`.
2. Include it in `server.py` (`from app.routes import ... as ..._routes` + `api_router.include_router(...)`).
3. Add a Pydantic model under `/app/backend/app/models/`.
4. Create the frontend page at `/app/frontend/src/pages/AdminXxx.jsx`.
5. Wire it in `/app/frontend/src/App.js` inside the AdminShell block.
6. Add a nav entry in `/app/frontend/src/components/AdminShell.jsx`.
7. Add a matching pytest module under `/app/backend/tests/`.

## Tests
```bash
cd /app/backend && pytest -v
```

## API Docs
Swagger: `{REACT_APP_BACKEND_URL}/docs`

## Business Rule Validation
Run any time from the admin panel (`/admin/qa`) or the API:
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     $BACKEND/api/admin/qa/brv | jq .
```
