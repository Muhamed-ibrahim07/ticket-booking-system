from datetime import datetime, timedelta
import io
import qrcode

from .extensions import db, socketio
from .models import SeatHold, Booking, WaitlistEntry, User
from flask import current_app
from itsdangerous import URLSafeTimedSerializer


def send_booking_email(booking_id):
    # Minimal QR generation + placeholder email send (synchronous)
    with current_app.app_context():
        booking = Booking.query.get(booking_id)
        if not booking:
            return False

        qr = qrcode.make(booking.booking_ref)
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        buf.seek(0)

        # send email via SendGrid if available
        sg_key = current_app.config.get('SENDGRID_API_KEY') or current_app.config.get('MAIL_API_KEY')
        if sg_key:
            try:
                import base64
                import requests
                from_email = current_app.config.get('MAIL_FROM')
                # map booking.customer_id -> user's email
                user = User.query.get(booking.customer_id)
                to_email = user.email if user else from_email
                # send minimal SendGrid v3 mail with inline base64 attachment
                encoded = base64.b64encode(buf.getvalue()).decode('ascii')
                html = f"<p>Your booking {booking.booking_ref}</p><img src=\"data:image/png;base64,{encoded}\"/>"
                payload = {
                    'personalizations': [{'to': [{'email': to_email}]}],
                    'from': {'email': from_email},
                    'subject': f'Your booking {booking.booking_ref}',
                    'content': [{'type': 'text/html', 'value': html}],
                }
                r = requests.post('https://api.sendgrid.com/v3/mail/send', json=payload, headers={'Authorization': f'Bearer {sg_key}'}, timeout=10)
                current_app.logger.info('SendGrid send status: %s', r.status_code)
            except Exception:
                current_app.logger.exception('SendGrid send failed; falling back to log')
        else:
            current_app.logger.info(f"Would send email for booking {booking.booking_ref} with QR ({len(buf.getvalue())} bytes)")
        return True


def release_expired_holds():
    # Sweep DB for expired active holds and release them
    now = datetime.utcnow()
    expired = SeatHold.query.filter(SeatHold.status == 'active', SeatHold.expires_at < now).all()
    if not expired:
        return 0
    count = 0
    for h in expired:
        h.status = 'released'
        db.session.add(h)
        socketio.emit('seat_update', {'show_id': h.show_id, 'seat_id': h.seat_id, 'status': 'released'})
        count += 1
    db.session.commit()
    return count


def offer_waitlist_for_show_category(show_id, category):
    """Find next waiting entry for show+category, create an offered hold, send email with token."""
    with current_app.app_context():
        # find next waiting entry
        entry = (
            WaitlistEntry.query.filter_by(show_id=show_id, category=category, status='waiting')
            .order_by(WaitlistEntry.position.asc())
            .first()
        )
        if not entry:
            current_app.logger.info('No waitlist entries to offer')
            return None

        # find an available seat in this show/category (no booking, no active hold)
        from .models import Seat, Booking, SeatHold

        # seats for show & category
        seats = Seat.query.filter_by(show_id=show_id, category=category).all()
        available_seat = None
        for s in seats:
            booked = Booking.query.filter_by(show_id=show_id, seat_id=s.id).first()
            active_hold = SeatHold.query.filter(SeatHold.show_id == show_id, SeatHold.seat_id == s.id, SeatHold.status == 'active').first()
            if not booked and not active_hold:
                available_seat = s
                break

        if not available_seat:
            current_app.logger.info('No available seat to offer')
            return None

        # create a SeatHold for this seat
        now = datetime.utcnow()
        ttl = current_app.config.get('WAITLIST_OFFER_TTL', 900)
        hold = SeatHold(show_id=show_id, seat_id=available_seat.id, customer_id=entry.customer_id, expires_at=now + timedelta(seconds=ttl))
        db.session.add(hold)

        # mark entry offered and record offer times
        entry.status = 'offered'
        entry.offered_at = now
        entry.offer_expires_at = now + timedelta(seconds=ttl)
        db.session.add(entry)
        db.session.commit()

        # generate signed token containing hold id
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps({'entry_id': entry.id, 'hold_id': hold.id})

        # send email (placeholder)
        current_app.logger.info(f"Offering seat {available_seat.id} for waitlist entry {entry.id} to user {entry.customer_id}; token={token}")
        return {'entry_id': entry.id, 'token': token, 'hold_id': hold.id}


def sweep_expired_offers():
    """Find offered waitlist entries that expired and mark them skipped, then offer next."""
    with current_app.app_context():
        now = datetime.utcnow()
        expired = WaitlistEntry.query.filter(WaitlistEntry.status == 'offered', WaitlistEntry.offer_expires_at < now).all()
        for e in expired:
            e.status = 'skipped'
            db.session.add(e)
            # call next offer directly
            offer_waitlist_for_show_category(e.show_id, e.category)
        db.session.commit()
        return len(expired)
