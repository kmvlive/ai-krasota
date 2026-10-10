# @ai-krasota/api — Backend (FastAPI)

Python 3.11+, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload    # http://localhost:8000/docs
pytest                           # тесты
```
