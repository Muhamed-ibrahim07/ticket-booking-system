from itsdangerous import URLSafeTimedSerializer
from flask import current_app


def generate_offer_token(entry_id: int) -> str:
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps({'entry_id': entry_id})


def verify_offer_token(token: str, max_age: int = None):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.loads(token, max_age=max_age) if max_age else s.loads(token)
