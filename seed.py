"""Seed script to create initial data: users, venue, show, seats."""
import os
from datetime import datetime, timedelta

from ticket_system.ticket_system.app import create_app
from ticket_system.ticket_system.extensions import db
from ticket_system.ticket_system.models import User, Venue, Show, Seat


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(email='admin@example.com').first():
            u = User(email='admin@example.com', name='Admin', role='admin')
            u.set_password('adminpass')
            db.session.add(u)

        if not User.query.filter_by(email='organiser@example.com').first():
            o = User(email='organiser@example.com', name='Org', role='organiser')
            o.set_password('organiserpass')
            db.session.add(o)

        if not User.query.filter_by(email='customer@example.com').first():
            c = User(email='customer@example.com', name='Cust', role='customer')
            c.set_password('custpass')
            db.session.add(c)

        if not Venue.query.filter_by(name='Main Hall').first():
            v = Venue(name='Main Hall', rows=5, cols=10)
            db.session.add(v)
            db.session.flush()

            # create show
            show = Show(event_name='Sample Movie', venue_id=v.id, start_at=datetime.utcnow() + timedelta(days=1))
            db.session.add(show)
            db.session.flush()

            # create seats
            categories = ['Premium', 'Standard']
            for r in range(1, v.rows + 1):
                for n in range(1, v.cols + 1):
                    cat = 'Premium' if r <= 2 else 'Standard'
                    s = Seat(show_id=show.id, row=str(r), number=n, category=cat)
                    db.session.add(s)

        db.session.commit()
        print('Seed complete')


if __name__ == '__main__':
    seed()
