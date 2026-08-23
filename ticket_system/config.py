import os
from datetime import timedelta

class Config:
    # Use DATABASE_URL as provided; don't rewrite the scheme (psycopg2 expected)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///dev.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret')
    # Redis/Celery not required in simplified single-process deployment
    REDIS_URL = os.getenv('REDIS_URL', '')
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', '')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', '')
    SEAT_HOLD_DEFAULT_TTL = int(os.getenv('SEAT_HOLD_DEFAULT_TTL', '600'))  # seconds
    WAITLIST_OFFER_TTL = int(os.getenv('WAITLIST_OFFER_TTL', '900'))
