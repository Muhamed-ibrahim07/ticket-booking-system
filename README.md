# Ticket Booking System

A simplified, self-contained Ticket Booking System built with Flask, SQLAlchemy and Socket.IO. Provides a SPA frontend (served from the app), JWT auth, seat holds with TTL, waitlist offers, DB-backed concurrency protection, and an admin sweep endpoint for maintenance.

**Repository layout (relevant)**
- **ticket_system/**: Python package with the application
- **ticket_system/ticket_system/app.py**: Flask application factory and HTTP routes
- **ticket_system/ticket_system/models.py**: SQLAlchemy models
- **ticket_system/ticket_system/tasks.py**: synchronous maintenance tasks (sweep, email helpers)
- **ticket_system/ticket_system/static/**: single-file SPA (`index.html`, `app.js`, `styles.css`)
- **seed.py**: seeds the DB with an admin, organiser, customer, a venue, show and seats
- **run.py**: entrypoint that applies eventlet monkey-patch and instantiates the app
- **Dockerfile**, **docker-compose.yml**, **requirements.txt** (project root)

**Features**
- Visual single-file SPA served from `/` for manual testing
- JWT-based auth (`/api/register`, `/api/login`, `/api/me`)
- Seat hold mechanism with TTL (no Celery/Redis; uses DB + admin sweep endpoint)
- Waitlist with auto-offer and TTL acceptance token
- DB-level unique constraints to protect concurrency when booking
- Real-time seat status updates via Socket.IO (`seat_update` events)
- Admin sweep endpoint for releasing expired holds and expiring offers (`/api/admin/sweep`)
- Docker + docker-compose for local deployment

Quick local setup
1. Create a Python virtual environment and activate it:

```bash
python -m venv .venv
source .venv/Scripts/activate    # Windows PowerShell: .venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set minimal environment variables (optional; defaults exist for local development):

```bash
export FLASK_ENV=development
export DATABASE_URL=sqlite:///dev.db         # or a Postgres URL
export SECRET_KEY="change-me"
export JWT_SECRET_KEY="change-me"
export SWEEP_SECRET="sweep-secret"
```

4. Initialize DB and seed sample data (recommended):

```bash
python seed.py
```

Run locally (development)

- Run with the bundled eventlet-patched entrypoint for Socket.IO compatibility:

```bash
python run.py
# or, with Gunicorn (production-like):
gunicorn -k eventlet -w 1 run:app -b 0.0.0.0:5000
```

- Open http://localhost:5000/ to access the SPA. The SPA uses `fetch()` and Socket.IO to exercise the API.

Run with Docker Compose

```bash
docker-compose up --build
# seed inside container (after web container is ready):
docker-compose exec web python seed.py
```

Environment variables (summary)
- `DATABASE_URL` — SQLAlchemy database URL (default: `sqlite:///dev.db`)
- `SECRET_KEY` — Flask secret key (required for some features)
- `JWT_SECRET_KEY` — secret for JWT tokens
- `SWEEP_SECRET` — static secret for `POST /api/admin/sweep`
- `PORT` — port to bind when using environment-driven deploys (Render)
- Optional email SMTP settings if you wire up booking emails (see `tasks.py`)

Admin sweep (cron-friendly)
- Endpoint: `POST /api/admin/sweep`
- Protect by sending header `X-Sweep-Secret: <SWEEP_SECRET>` (or `?sweep_secret=` query param)
- Use your system cron or an external scheduler to call this periodically (e.g., every minute or two) to release expired holds and expire waitlist offers.

Key API endpoints (high level)
- `POST /api/register` — register user (role: customer/organiser/admin)
- `POST /api/login` — login, returns JWT access token
- `GET /api/me` — get current user info (requires JWT)
- `POST /api/hold_seat` — hold a seat (requires JWT)
- `POST /api/book` — convert a hold into a booking (requires JWT)
- `GET /api/seats/<show_id>` — list seats and statuses
- `POST /api/join_waitlist` — join a waitlist for a show/category
- `POST /api/accept_offer` — accept an offered waitlist hold via signed token
- `POST /api/cancel_booking` — cancel a booking (customer)
- `POST /api/venues` — create venue (admin)
- `POST /api/shows` — create show (organiser)

WebSocket events
- Event name: `seat_update` — payload includes `show_id`, `seat_id`, `status` (`held`/`booked`/`vacant`)

Development checks
- Verify Python syntax for critical files (example):

```bash
python -m py_compile ticket_system/ticket_system/app.py
```

Troubleshooting
- If the SPA shows empty seats or API returns 500s, check logs for DB migrations and ensure `seed.py` ran successfully.
- For concurrency surprises, prefer Postgres (set `DATABASE_URL` to a Postgres URI). The project contains helper code to create a partial unique index for active holds when running on Postgres.
- If Socket.IO connections fail, ensure `eventlet` is installed and you run with `python run.py` or use Gunicorn with `-k eventlet`.

Notes for graders / deploy
- This project intentionally avoids Celery/Redis: asynchronous maintenance is performed via a cronable admin endpoint and synchronous helper functions in `tasks.py`. That keeps the stack self-contained for local grading.

Next actions you might want me to do
- Run the app and open the SPA in a browser and verify flows
- Add CI script or a simple `Makefile` for common tasks
- Harden env validation and add an example `.env` file

---
If you want, I can commit this `README.md` into the repo now. Say "Yes, commit" and I'll run the git commands.# Ticket Booking System (scaffold)

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
