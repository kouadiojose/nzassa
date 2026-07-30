# N'Zassa Business — Backend

API FastAPI asynchrone, PostgreSQL multi-tenant, Redis, Dramatiq.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn nzassa.main:app --reload
```

Docs API : http://localhost:8000/docs
