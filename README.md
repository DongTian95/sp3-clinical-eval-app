# Clinical Model Evaluation Interface (Sample)

A containerized web app for clinicians to evaluate *mock* multimodal model outputs (text + images), rate them with structured feedback, and store results persistently.

This was built as a **sample data-collection frontend** for preference optimization / RLHF-like workflows in clinical radiology settings.

## Quickstart

```bash
docker compose up --build
```

Then open: http://localhost:8000

- Login with any name (no password; demo only)
- Evaluate cases in the queue
- Optional: pairwise compare outputs (side-by-side)
- Optional: login as `admin` and open `/admin`

## Persistence

Feedback is stored in a SQLite database at `/data/app.db` inside the container.  
`docker compose` uses a named volume (`eval-data`) so data **survives container restarts**.

## Architecture

- **FastAPI** backend (server-side rendered HTML via Jinja2 templates)
- **SQLite** (SQLAlchemy ORM)
- Static images served from `/static/images`
- Auto-seeding: on first startup, the DB is initialized and sample cases/outputs are inserted

## Notes

- All case data is synthetic and contains **no patient information**.
- Model outputs are mocked and intentionally include minor errors to make evaluation meaningful.

