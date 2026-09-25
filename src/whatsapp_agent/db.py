import sqlite3
import threading
from .config import DB_PATH

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA foreign_keys=ON")

db_lock = threading.Lock()


def init_db():
    conn.execute("""
    CREATE TABLE IF NOT EXISTS messages (
    chat_jid TEXT,
    msg_id TEXT,
    sender TEXT,
    sender_name TEXT,
    text TEXT,
    timestamp INTEGER,
    PRIMARY KEY (chat_jid, msg_id)   -- dedupes overlapping backfills
    );""")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS reactions (
    chat_jid TEXT,
    msg_id TEXT,
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
