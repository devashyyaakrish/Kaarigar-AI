import json
import psycopg2  # or use SQLAlchemy

def load_session(phone: str) -> dict:
    # Query user_sessions table by phone
    # Returns the 'context' JSONB column
    ...

def save_session(phone: str, state: str, context: dict):
    # Upsert into user_sessions
    ...