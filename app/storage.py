import sqlite3
import os
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from app.config import settings
from app.models import WebhookPayload

db_path = settings.DATABASE_URL.replace("sqlite:///", "")
if settings.DATABASE_URL.startswith("sqlite:////"):
    db_path = settings.DATABASE_URL[10:]
elif settings.DATABASE_URL.startswith("sqlite:///"):
    db_path = settings.DATABASE_URL[10:]

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    dir_name = os.path.dirname(db_path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                from_msisdn TEXT NOT NULL,
                to_msisdn TEXT NOT NULL,
                ts TEXT NOT NULL,
                text TEXT,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_msisdn);")
        conn.commit()

def store_message(payload: WebhookPayload) -> Tuple[bool, str]:
    """
    Store message. Returns (inserted: bool, error: str)
    """
    try:
        with get_db_connection() as conn:
            now = datetime.utcnow().isoformat() + "Z"
            conn.execute(
                """
                INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (payload.message_id, payload.from_msisdn, payload.to_msisdn, payload.ts, payload.text, now)
            )
            conn.commit()
            return True, ""
    except sqlite3.IntegrityError:
        return False, ""
    except Exception as e:
        return False, str(e)

def get_messages(limit: int, offset: int, from_msisdn: Optional[str], since: Optional[str], q: Optional[str]) -> Tuple[List[sqlite3.Row], int]:
    base_query = "FROM messages WHERE 1=1"
    params = []

    if from_msisdn:
        base_query += " AND from_msisdn = ?"
        params.append(from_msisdn)
    
    if since:
        base_query += " AND ts >= ?"
        params.append(since)
        
    if q:
        base_query += " AND text LIKE ?"
        params.append(f"%{q}%")

    count_query = f"SELECT COUNT(*) {base_query}"
    data_query = f"SELECT * {base_query} ORDER BY ts ASC, message_id ASC LIMIT ? OFFSET ?"
    
    with get_db_connection() as conn:
        total = conn.execute(count_query, params).fetchone()[0]
        
        params.append(limit)
        params.append(offset)
        
        rows = conn.execute(data_query, params).fetchall()
            
        return rows, total

def get_stats() -> Dict[str, Any]:
    with get_db_connection() as conn:
        total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        
        ts_stats = conn.execute("SELECT MIN(ts), MAX(ts) FROM messages").fetchone()
        
        senders_rows = conn.execute("""
            SELECT from_msisdn, COUNT(*) as count 
            FROM messages 
            GROUP BY from_msisdn 
            ORDER BY count DESC 
            LIMIT 10
        """).fetchall()
        
        unique_senders = conn.execute("SELECT COUNT(DISTINCT from_msisdn) FROM messages").fetchone()[0]
        
        messages_per_sender = [
            {"from": row["from_msisdn"], "count": row["count"]} for row in senders_rows
        ]
        
        return {
            "total_messages": total_messages,
            "senders_count": unique_senders,
            "messages_per_sender": messages_per_sender,
            "first_message_ts": ts_stats[0],
            "last_message_ts": ts_stats[1]
        }

def check_db_ready() -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except:
        return False
