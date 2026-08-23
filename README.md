# Ticket Booking System (scaffold)

This repo contains a Flask-based scaffold for a ticket booking system implementing seat holds with TTL, waitlist entries, bookings, QR ticket generation, Celery tasks and Redis integration.

Quick start

1. Copy `.env.example` to `.env` and set values (Postgres + Redis).
2. Create a Python venv and install:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Run the app locally:

```bash
set FLASK_APP=run.py
flask run
```

4. Start Celery worker:

```bash
celery -A ticket_system.celery_worker.celery worker -B --loglevel=info
```

5. (Optional) Start Redis keyspace listener to auto-release expired holds:

```bash
python -m ticket_system.ticket_system.redis_listener
```

Docker quickstart

1. Build and run the entire stack with Docker Compose:

```bash
docker-compose up --build
```

2. Open `http://localhost:5000/static/index.html` for a minimal seat map UI.

Create delivery zip

```bash
python make_zip.py
```

See the code for models and tasks. This scaffold focuses on the concurrency and TTL primitives; expand the frontend and auth as next steps.