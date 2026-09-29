import sqlite3
import threading
from .config import DB_PATH

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA foreign_keys=ON")

db_lock = threading.RLock()


def init_db():
    with db_lock, conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
        chat_jid TEXT,
        msg_id TEXT,
        sender TEXT,
        sender_name TEXT,
        text TEXT,
        timestamp INTEGER,
        quoted_text TEXT,
        mentioned_jids TEXT,
        PRIMARY KEY (chat_jid, msg_id)   -- dedupes overlapping backfills
        );""")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS reactions (
        chat_jid TEXT,
        msg_id TEXT, -- This is the ID of the message being reacted to, so if you change reactions the same row will be updated, this table only holds current state, not history of reactions on a single message
        sender TEXT,
        sender_name TEXT,
        text TEXT,
        timestamp INTEGER,
        PRIMARY KEY (chat_jid, msg_id, sender)   -- dedupes overlapping backfills
        );""")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
        pn TEXT,
        lid, TEXT,
        full_name TEXT,
        PRIMARY KEY (pn)
        );""")

        messages_schema = conn.execute(
            "SELECT sql FROM sqlite_schema WHERE name = 'messages';"
        ).fetchone()[0]
        if "quoted_text" not in messages_schema:
            conn.execute("""ALTER TABLE messages ADD COLUMN quoted_text TEXT;""")
        if "mentioned_jids" not in messages_schema:
            conn.execute("""ALTER TABLE messages ADD COLUMN mentioned_jids TEXT;""")
