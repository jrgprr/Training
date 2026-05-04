from sqlalchemy.orm import Session
from app.db.session import get_db


class BaseRepository:
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())