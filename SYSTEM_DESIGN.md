# System Design (≤800 words)

Seat Hold & TTL

Seats are held by creating a `SeatHold` record with `status = 'active'` and an `expires_at` timestamp. A PostgreSQL unique partial index on `(show_id, seat_id)` where `status = 'active'` prevents two simultaneous active holds for the same seat. The hold's TTL is enforced primarily via Redis: when a hold is created the system sets a Redis key `hold:{show_id}:{seat_id}` with `EX=ttl`. Redis expiry emits a notification (or a Celery beat sweep runs) that triggers releasing the DB hold and notifying clients via Socket.IO. As a failsafe, a Celery task `release_expired_holds` periodically sweeps the DB for holds past `expires_at` and marks them `released`.

Concurrency Prevention

Correctness is achieved at the database level. The application attempts to insert a `SeatHold` record inside a transaction. PostgreSQL enforces the partial unique index for active holds; concurrent attempts will leave only one insert succeeding while the others raise a constraint error. This makes the DB the source of truth. Redis is used only for timely TTL notifications and not relied upon for correctness: if Redis is unavailable, database uniqueness still prevents double-holds.

Waitlist Auto-assignment Flow

Waitlist entries are stored in `waitlist_entries` per `show_id` and `category`. On a cancellation, the system triggers `offer_waitlist_for_show_category(show_id, category)` which selects the oldest `status='waiting'` entry, marks it `offered`, sets `offered_at` and `offer_expires_at`, and generates a signed token for the customer. The token encodes `entry_id` and is time-limited using `itsdangerous.URLSafeTimedSerializer`. The offer is emailed to the customer with a link containing the token.

Time-limited Offer Handling

When a customer follows the offer link, the token is verified (max age = offer TTL). If valid, the backend creates a short-lived `SeatHold` for the offered seat(s) tied to the customer and returns a hold identifier so the customer can complete checkout. If the customer fails to accept before the TTL, a periodic Celery task `sweep_expired_offers` marks that entry `skipped` and automatically offers the seat to the next customer in queue. All transitions are recorded in the DB so the process is auditable and resilient to restarts.

Design trade-offs & robustness

- Redis key expiry provides low-latency signals to update clients in near-real-time; DB sweeps are a robust fallback.
- Using DB uniqueness for concurrency makes the system correct even during Redis outages.
- All asynchronous operations (email, offer distribution, sweeps) run in Celery tasks to keep HTTP requests fast and reliable.
- Booking references use UUIDs; QR codes encode booking references (not raw DB ids) to avoid guessability.
