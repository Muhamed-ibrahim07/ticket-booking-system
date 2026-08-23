# API Documentation (minimal)

POST /api/register
- Input: { email, password, name, role }
- Output: { ok, user_id }

POST /api/login
- Input: { email, password }
- Output: { ok, access_token }

POST /api/hold_seat
- Input: { show_id, seat_id, customer_id, ttl }
- Output: { ok, hold_id, expires_at }

POST /api/book
- Input: { hold_id, customer_id }
- Output: { ok, booking_ref }

POST /api/join_waitlist
- Auth required
- Input: { show_id, category }
- Output: { ok, waitlist_id }

POST /api/cancel_booking
- Auth required
- Input: { booking_id }
- Output: { ok }

POST /api/accept_offer
- Input: { token, user_id }
- Output: { ok, hold_id, expires_at }

Maintenance functions (synchronous):
- `release_expired_holds()` — sweeps expired active holds and releases them.
- `offer_waitlist_for_show_category(show_id, category)` — marks next waitlist entry as offered and generates token.
- `sweep_expired_offers()` — marks expired offers skipped and advances queue.
