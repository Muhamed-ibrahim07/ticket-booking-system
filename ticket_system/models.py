import uuid
from datetime import datetime, timedelta
from sqlalchemy import UniqueConstraint
from .extensions import db
from sqlalchemy.exc import IntegrityError


from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    role = db.Column(db.String(50), default='customer')
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, pw: str):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)


class Venue(db.Model):
    __tablename__ = 'venues'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    rows = db.Column(db.Integer, default=0)
    cols = db.Column(db.Integer, default=0)


class Show(db.Model):
    __tablename__ = 'shows'
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(255), nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey('venues.id'), nullable=False)
    start_at = db.Column(db.DateTime, nullable=False)


class Seat(db.Model):
    __tablename__ = 'seats'
    id = db.Column(db.Integer, primary_key=True)
    show_id = db.Column(db.Integer, db.ForeignKey('shows.id'), nullable=False)
    row = db.Column(db.String(8))
    number = db.Column(db.Integer)
    category = db.Column(db.String(64))
    price = db.Column(db.Float, default=0.0)


class SeatHold(db.Model):
    __tablename__ = 'seat_holds'
    id = db.Column(db.Integer, primary_key=True)
    show_id = db.Column(db.Integer, nullable=False)
    seat_id = db.Column(db.Integer, nullable=False)
    customer_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(32), default='active')  # active, released, booked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    booking_ref = db.Column(db.String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    show_id = db.Column(db.Integer, nullable=False)
    seat_id = db.Column(db.Integer, nullable=False)
    customer_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('show_id', 'seat_id', name='uq_booking_seat'),
    )


class WaitlistEntry(db.Model):
    __tablename__ = 'waitlist_entries'
    id = db.Column(db.Integer, primary_key=True)
    show_id = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(64), nullable=False)
    customer_id = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), default='waiting')  # waiting, offered, skipped
    offered_at = db.Column(db.DateTime, nullable=True)
    offer_expires_at = db.Column(db.DateTime, nullable=True)


def create_partial_indexes(engine):
    # Create PostgreSQL partial unique index to prevent two active holds for same seat
    if engine.dialect.name == 'postgresql':
        try:
            engine.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_active_seathold ON seat_holds (show_id, seat_id)
            WHERE status = 'active'
            """)
        except Exception:
            pass
