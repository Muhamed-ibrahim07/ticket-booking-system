import os
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from .config import Config
from .extensions import db, jwt, socketio
from .models import Seat, SeatHold, Booking, create_partial_indexes, User, WaitlistEntry
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from itsdangerous import URLSafeTimedSerializer
from datetime import timezone
from sqlalchemy import func



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)

    # No Redis client in simplified stack

    @app.before_first_request
    def init_db():
        db.create_all()
        # create partial index if postgres
        create_partial_indexes(db.engine)
        # ensure Seat.price column exists (if schema evolved)
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('seats')]
            if 'price' not in cols:
                dialect = db.engine.dialect.name
                if dialect == 'postgresql':
                    db.engine.execute('ALTER TABLE seats ADD COLUMN price double precision DEFAULT 0')
                elif dialect == 'sqlite':
                    db.engine.execute('ALTER TABLE seats ADD COLUMN price REAL DEFAULT 0')
                else:
                    db.engine.execute('ALTER TABLE seats ADD COLUMN price FLOAT DEFAULT 0')
        except Exception:
            app.logger.warning('Could not ensure seats.price column exists')


    @app.route('/api/hold_seat', methods=['POST'])
    @jwt_required()
    def hold_seat():
        data = request.get_json() or {}
        show_id = data.get('show_id')
        seat_id = data.get('seat_id')
        ttl = int(data.get('ttl') or app.config.get('SEAT_HOLD_DEFAULT_TTL', 600))
        customer_id = get_jwt_identity()

        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        # Try to create a SeatHold; rely on DB unique index to enforce concurrency
        hold = SeatHold(show_id=show_id, seat_id=seat_id, customer_id=customer_id, expires_at=expires_at)
        try:
            db.session.add(hold)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({'ok': False, 'reason': 'seat_unavailable'}), 409

        # No Redis TTL key in simplified setup

        socketio.emit('seat_update', {'show_id': show_id, 'seat_id': seat_id, 'status': 'held'})
        return jsonify({'ok': True, 'hold_id': hold.id, 'expires_at': expires_at.isoformat()})


    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        role = data.get('role', 'customer')
        if not email or not password:
            return jsonify({'ok': False, 'reason': 'missing_credentials'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'ok': False, 'reason': 'exists'}), 400
        u = User(email=email, name=name, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return jsonify({'ok': True, 'user_id': u.id})


    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({'ok': False, 'reason': 'invalid'}), 401
        additional_claims = {'role': user.role}
        access = create_access_token(identity=user.id, additional_claims=additional_claims)
        return jsonify({'ok': True, 'access_token': access})


    def role_required(role):
        def wrapper(fn):
            from functools import wraps

            @wraps(fn)
            @jwt_required()
            def inner(*args, **kwargs):
                claims = get_jwt()
                if claims.get('role') != role and claims.get('role') != 'admin':
                    return jsonify({'ok': False, 'reason': 'forbidden'}), 403
                return fn(*args, **kwargs)

            return inner

        return wrapper


    @app.route('/api/join_waitlist', methods=['POST'])
    @jwt_required()
    def join_waitlist():
        data = request.get_json() or {}
        show_id = data.get('show_id')
        category = data.get('category')
        user_id = get_jwt_identity()
        if not show_id or not category:
            return jsonify({'ok': False, 'reason': 'missing'}), 400
        # position: max(position)+1 in show+category
        max_pos = db.session.query(func.max(WaitlistEntry.position)).filter_by(show_id=show_id, category=category).scalar() or 0
        entry = WaitlistEntry(show_id=show_id, category=category, customer_id=user_id, position=(max_pos or 0) + 1)
        db.session.add(entry)
        db.session.commit()
        return jsonify({'ok': True, 'waitlist_id': entry.id})


    @app.route('/api/venues', methods=['POST'])
    @role_required('admin')
    def create_venue():
        data = request.get_json() or {}
        name = data.get('name')
        rows = int(data.get('rows') or 0)
        cols = int(data.get('cols') or 0)
        if not name:
            return jsonify({'ok': False, 'reason': 'missing_name'}), 400
        v = None
        try:
            from .models import Venue
            v = Venue(name=name, rows=rows, cols=cols)
            db.session.add(v)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'ok': False, 'reason': 'db_error'}), 500
        return jsonify({'ok': True, 'venue_id': v.id})


    @app.route('/api/shows', methods=['POST'])
    @role_required('organiser')
    def create_show():
        data = request.get_json() or {}
        event_name = data.get('event_name')
        venue_id = data.get('venue_id')
        start_at = data.get('start_at')
        category_prices = data.get('category_prices') or {}
        if not event_name or not venue_id or not start_at:
            return jsonify({'ok': False, 'reason': 'missing'}), 400
        try:
            from .models import Show, Venue, Seat
            # parse start_at (ISO format expected)
            dt = datetime.fromisoformat(start_at)
            show = Show(event_name=event_name, venue_id=venue_id, start_at=dt)
            db.session.add(show)
            db.session.flush()

            # generate seats from venue layout
            venue = Venue.query.get(venue_id)
            if not venue:
                db.session.rollback()
                return jsonify({'ok': False, 'reason': 'venue_not_found'}), 404

            rows = venue.rows or 0
            cols = venue.cols or 0
            # Simple category allocation: if 'Premium' present, assign top ~1/3 rows to Premium
            premium_rows = 0
            if 'Premium' in category_prices:
                premium_rows = max(1, rows // 3)

            for r in range(1, rows + 1):
                for n in range(1, cols + 1):
                    if r <= premium_rows:
                        category = 'Premium'
                    else:
                        # fallback to 'Standard' if present, else first key
                        category = 'Standard' if 'Standard' in category_prices else (list(category_prices.keys())[0] if category_prices else 'Standard')
                    price = float(category_prices.get(category, 0))
                    seat = Seat(show_id=show.id, row=str(r), number=n, category=category, price=price)
                    db.session.add(seat)

            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('Failed to create show')
            return jsonify({'ok': False, 'reason': 'db_error'}), 500

        return jsonify({'ok': True, 'show_id': show.id})


    @app.route('/api/events', methods=['GET'])
    def list_events():
        args = request.args
        date = args.get('date')
        venue_id = args.get('venue_id')
        from .models import Show, Venue
        q = Show.query
        if date:
            try:
                d = datetime.fromisoformat(date).date()
                q = q.filter(db.func.date(Show.start_at) == d)
            except Exception:
                pass
        if venue_id:
            q = q.filter(Show.venue_id == int(venue_id))
        shows = q.all()
        out = []
        for s in shows:
            v = Venue.query.get(s.venue_id)
            out.append({'show_id': s.id, 'event_name': s.event_name, 'venue': v.name if v else None, 'start_at': s.start_at.isoformat()})
        return jsonify({'ok': True, 'events': out})


    @app.route('/api/bookings', methods=['GET'])
    @jwt_required()
    def my_bookings():
        user_id = get_jwt_identity()
        from .models import Booking, Seat, Show
        bookings = Booking.query.filter_by(customer_id=user_id).all()
        out = []
        for b in bookings:
            seat = Seat.query.get(b.seat_id)
            show = Show.query.get(b.show_id)
            out.append({'booking_id': b.id, 'booking_ref': b.booking_ref, 'show_id': b.show_id, 'event_name': show.event_name if show else None, 'seat_id': b.seat_id, 'row': seat.row if seat else None, 'number': seat.number if seat else None, 'category': seat.category if seat else None, 'price': seat.price if seat else None, 'created_at': b.created_at.isoformat()})
        return jsonify({'ok': True, 'bookings': out})


    @app.route('/api/organiser/summary/<int:show_id>', methods=['GET'])
    @role_required('organiser')
    def organiser_summary(show_id):
        from .models import Booking, Seat
        from sqlalchemy import func
        total_bookings = db.session.query(func.count(Booking.id)).filter(Booking.show_id == show_id).scalar() or 0
        total_revenue = db.session.query(func.coalesce(func.sum(Seat.price), 0)).join(Seat, Booking.seat_id == Seat.id).filter(Booking.show_id == show_id).scalar() or 0.0
        return jsonify({'ok': True, 'show_id': show_id, 'total_bookings': int(total_bookings), 'total_revenue': float(total_revenue)})


    @app.route('/api/cancel_booking', methods=['POST'])
    @jwt_required()
    def cancel_booking():
        data = request.get_json() or {}
        booking_id = data.get('booking_id')
        user_id = get_jwt_identity()
        booking = Booking.query.get(booking_id)
        if not booking or booking.customer_id != user_id:
            return jsonify({'ok': False, 'reason': 'not_found'}), 404
        show_id = booking.show_id
        # get seat category by seat id
        seat = Seat.query.get(booking.seat_id)
        category = seat.category if seat else None
        # delete booking
        db.session.delete(booking)
        db.session.commit()

        # offer to waitlist immediately (synchronous)
        try:
            from .tasks import offer_waitlist_for_show_category
            if category:
                offer_waitlist_for_show_category(show_id, category)
        except Exception:
            app.logger.exception('Failed to offer waitlist')

        socketio.emit('seat_update', {'show_id': show_id, 'seat_id': booking.seat_id, 'status': 'vacant'})
        return jsonify({'ok': True})


    @app.route('/api/accept_offer', methods=['POST'])
    @jwt_required()
    def accept_offer():
        data = request.get_json() or {}
        token = data.get('token')
        user_id = get_jwt_identity()
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try:
            payload = s.loads(token, max_age=app.config.get('WAITLIST_OFFER_TTL', 900))
        except Exception:
            return jsonify({'ok': False, 'reason': 'token_invalid'}), 400
        entry_id = payload.get('entry_id')
        hold_id = payload.get('hold_id')
        entry = WaitlistEntry.query.get(entry_id)
        from .models import SeatHold as SH
        hold = SH.query.get(hold_id)
        if not entry or not hold:
            return jsonify({'ok': False, 'reason': 'invalid_offer'}), 400
        if entry.customer_id != user_id or hold.customer_id != user_id or entry.status != 'offered' or hold.status != 'active':
            return jsonify({'ok': False, 'reason': 'invalid_offer'}), 400
        # mark entry accepted
        entry.status = 'accepted'
        db.session.add(entry)
        db.session.commit()
        return jsonify({'ok': True, 'hold_id': hold.id, 'expires_at': hold.expires_at.isoformat()})


    @app.route('/api/seats/<int:show_id>', methods=['GET'])
    def seats_for_show(show_id):
        # return seat list with status: available / held / booked
        from .models import Seat, Booking, SeatHold
        seats = Seat.query.filter_by(show_id=show_id).all()
        result = []
        for s in seats:
            status = 'available'
            booked = Booking.query.filter_by(show_id=show_id, seat_id=s.id).first()
            if booked:
                status = 'booked'
            else:
                hold = SeatHold.query.filter(SeatHold.show_id == show_id, SeatHold.seat_id == s.id, SeatHold.status == 'active').first()
                if hold:
                    status = 'held'
            result.append({'seat_id': s.id, 'row': s.row, 'number': s.number, 'category': s.category, 'status': status})
        return jsonify({'ok': True, 'seats': result})


    @app.route('/api/book', methods=['POST'])
    @jwt_required()
    def book():
        data = request.get_json() or {}
        hold_id = data.get('hold_id')
        user_id = get_jwt_identity()

        hold = SeatHold.query.get(hold_id)
        if not hold or hold.status != 'active' or hold.expires_at < datetime.utcnow():
            return jsonify({'ok': False, 'reason': 'hold_invalid'}), 400
        if hold.customer_id != user_id:
            return jsonify({'ok': False, 'reason': 'forbidden'}), 403

        # create booking
        booking = Booking(show_id=hold.show_id, seat_id=hold.seat_id, customer_id=user_id)
        try:
            db.session.add(booking)
            hold.status = 'booked'
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({'ok': False, 'reason': 'seat_already_booked'}), 409

        # emit socket update
        socketio.emit('seat_update', {'show_id': hold.show_id, 'seat_id': hold.seat_id, 'status': 'booked'})

        # send booking email synchronously
        try:
            from .tasks import send_booking_email
            send_booking_email(booking.id)
        except Exception:
            app.logger.exception('Failed to send booking email')

        return jsonify({'ok': True, 'booking_ref': booking.booking_ref})


    @app.route('/api/admin/sweep', methods=['POST'])
    def admin_sweep():
        # Protected by a static secret header (useful for cron); check X-Sweep-Secret or query param
        secret = app.config.get('SWEEP_SECRET') or os.getenv('SWEEP_SECRET')
        provided = request.headers.get('X-Sweep-Secret') or request.args.get('sweep_secret')
        if not secret or provided != secret:
            return jsonify({'ok': False, 'reason': 'forbidden'}), 403
        try:
            from .tasks import release_expired_holds, sweep_expired_offers
            released = release_expired_holds()
            skipped = sweep_expired_offers()
            return jsonify({'ok': True, 'released_holds': int(released), 'expired_offers_skipped': int(skipped)})
        except Exception:
            app.logger.exception('Sweep failed')
            return jsonify({'ok': False, 'reason': 'sweep_failed'}), 500

    return app
