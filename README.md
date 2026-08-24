# Ticket Booking System

**Live:** [Muhamed-ibrahim07/ticket-booking-system]([https://github.com/Muhamed-ibrahim07/ticket-booking-system](https://ticket-booking-system-fxrx.onrender.com/) **RENDER**

TicketFlow is a Flask ticket-booking API with a small React seat-map client. It demonstrates authentication, event and venue management, temporary seat holds, booking conversion, cancellation, waitlists, signed offers, and database-level protection against double booking.

## What This Project Demonstrates

- JWT registration, login, identity lookup, and role-based authorization.
- Admin venue creation and organiser show creation with generated seats.
- Customer seat holds with a configurable time-to-live (TTL).
- Conversion of an active hold into a booking with a UUID booking reference.
- Booking cancellation and waitlist offer handling.
- Seat availability queries and Socket.IO `seat_update` notifications.
- A database uniqueness constraint for bookings and a PostgreSQL partial unique index for active holds.
- SQLite for a quick local demonstration and PostgreSQL through Docker Compose.

## Technology

- Python 3.11, Flask, Flask-SQLAlchemy, Flask-JWT-Extended, Flask-SocketIO
- PostgreSQL for the containerized deployment; SQLite is the local default
- React 18 and Socket.IO client in `frontend/`
- Gunicorn with Eventlet for the production-like server command

## Repository Map

| Path | Purpose |
| --- | --- |
| `ticket_system/app.py` | Flask application factory and API routes |
| `ticket_system/models.py` | Users, venues, shows, seats, holds, bookings, and waitlists |
| `ticket_system/tasks.py` | Expired-hold and waitlist maintenance helpers |
| `seed.py` | Creates sample users, venue, show, and 50 seats |
| `run.py` | Eventlet-compatible development entrypoint |
| `frontend/src/App.js` | React seat-map demonstration client |
| `tests/test_concurrency.py` | Concurrent hold integration test |
| `API_DOCS.md` | Compact endpoint reference |
| `SYSTEM_DESIGN.md` | Design decisions and concurrency explanation |

## Run Locally on Windows

From the repository root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python seed.py
python run.py
```

Open [http://localhost:5000/](http://localhost:5000/). The default database is `sqlite:///dev.db`, so PostgreSQL is not required for the basic demonstration.

If PowerShell blocks script activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal and activate the environment again.

## Run with Docker

Docker provides PostgreSQL and the web service together:

```powershell
docker compose up --build
docker compose exec web python seed.py
```

Open [http://localhost:5000/](http://localhost:5000/). Stop the services with `Ctrl+C`, or run `docker compose down`.

## Environment Configuration

The application has useful development defaults. For a custom setup, define:

```text
DATABASE_URL=postgresql://user:password@localhost:5432/ticketdb
SECRET_KEY=replace-me
JWT_SECRET_KEY=replace-jwt
SEAT_HOLD_DEFAULT_TTL=600
WAITLIST_OFFER_TTL=900
```

Copy `.env.example` as a starting point. Never use development secrets in a public deployment.

## Seed Accounts

Running `python seed.py` creates these demonstration accounts:

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@example.com` | `adminpass` |
| Organiser | `organiser@example.com` | `organiserpass` |
| Customer | `customer@example.com` | `custpass` |

These credentials are for local grading only.

## Assessment Walkthrough

1. Start the server and run `python seed.py`.
2. Call `GET /api/events` and record the seeded `show_id`.
3. Register or log in as a customer and save the returned `access_token`.
4. Call `GET /api/seats/<show_id>` and confirm the seeded seats are available.
5. Hold one seat with the JWT. Confirm the response contains `hold_id` and `expires_at`.
6. Call `POST /api/book` with that `hold_id`. Confirm a unique `booking_ref` is returned.
7. Call `GET /api/bookings` with the same JWT and confirm the booking is listed.
8. Attempt to hold or book the same seat with another customer. The system must reject the conflicting operation.
9. Cancel the booking and query the seat map again. The seat must become available.
10. Use two customers to verify waitlist join, cancellation-triggered offer, and signed offer acceptance.
11. Use the organiser account to create a show and the admin account to create a venue. Confirm role restrictions with the wrong account.

## API Smoke Test

PowerShell example:

```powershell
$login = Invoke-RestMethod http://localhost:5000/api/login -Method Post -ContentType 'application/json' -Body '{"email":"customer@example.com","password":"custpass"}'
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }

Invoke-RestMethod http://localhost:5000/api/me -Headers $headers
Invoke-RestMethod http://localhost:5000/api/events
Invoke-RestMethod http://localhost:5000/api/seats/1

$hold = Invoke-RestMethod http://localhost:5000/api/hold_seat -Method Post -Headers $headers -ContentType 'application/json' -Body '{"show_id":1,"seat_id":1,"ttl":120}'
$hold

Invoke-RestMethod http://localhost:5000/api/book -Method Post -Headers $headers -ContentType 'application/json' -Body (ConvertTo-Json @{ hold_id = $hold.hold_id })
Invoke-RestMethod http://localhost:5000/api/bookings -Headers $headers
```

For the complete route list and payload shapes, see [API_DOCS.md](API_DOCS.md).

## Tests and Quality Checks

Run these from the repository root:

```powershell
python -m py_compile run.py seed.py ticket_system\app.py ticket_system\models.py
python -m pytest -q
```

The concurrency test expects the server to be running at `http://localhost:5000` and checks that at most one of 20 simultaneous requests can hold the same seat:

```powershell
python -m pytest -q tests/test_concurrency.py
```

The test is intentionally integration-oriented. PostgreSQL is the recommended database when demonstrating concurrent requests because its partial unique index is the strongest representation of the production constraint.

## Frontend Check

The React client in `frontend/` is a minimal seat-map demonstration. To build it:

```powershell
cd frontend
npm install
npm run build
```

The build confirms that the React client compiles. The Flask application remains the primary runnable demonstration and API under test.

## Design Notes

Seat ownership is protected by the database, not by a client-side check. An active hold expires according to `expires_at`; maintenance helpers release expired holds and advance expired waitlist offers. Booking references are UUIDs, and JWT claims carry the authenticated user and role. The rationale and trade-offs are documented in [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md).

## Limitations and Scope

- The frontend is a demonstration client rather than a complete checkout interface.
- Payment processing is outside the scope of this project.
- Email delivery is represented by helper logic and requires a provider configuration for real messages.
- Development seed passwords and secret defaults must be replaced before deployment.
