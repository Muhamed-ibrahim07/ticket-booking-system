import os
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

db = SQLAlchemy()
jwt = JWTManager()
# No Redis messaging queue: single web process/socketio instance
socketio = SocketIO(cors_allowed_origins="*")
