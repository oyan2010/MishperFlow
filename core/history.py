import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

class HistoryManager:
    _db_path = None
    _conn = None

    @classmethod
    def init_db(cls, base_dir: str):
        cls._db_path = os.path.join(base_dir, "whisperflow.db")
        conn = sqlite3.connect(cls._db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT UNIQUE NOT NULL,
                transcript TEXT NOT NULL,
                duration_seconds REAL NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        cls._conn = sqlite3.connect(cls._db_path)
        logger.info(f"Database initialized at {cls._db_path}")

    def __init__(self):
        if self._conn is None:
            raise RuntimeError("HistoryManager not initialized. Call init_db first.")

    def add_record(self, file_path: str, transcript: str, duration: float):
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "INSERT INTO recordings (file_path, transcript, duration_seconds) VALUES (?, ?, ?)",
                (file_path, transcript, duration)
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            logger.warning(f"Duplicate file path: {file_path}, skipping")
        except Exception as e:
            logger.error(f"Failed to add record: {e}")
            raise

    def get_all(self):
        cursor = self._conn.cursor()
        cursor.execute("SELECT id, timestamp, file_path, transcript, duration_seconds FROM recordings ORDER BY timestamp DESC")
        return [dict(id=row[0], timestamp=row[1], file_path=row[2], transcript=row[3], duration=row[4]) for row in cursor.fetchall()]

    def close(self):
        if self._conn:
            self._conn.close()