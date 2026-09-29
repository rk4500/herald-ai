import sqlite3

from neonize.events import MessageEv
from .client import client

from .db import conn, db_lock
from .config import NEONIZE_PATH


def import_chats():
    with db_lock:
        try:
            with conn:
                conn.execute("ATTACH DATABASE ? AS neonize_store", (NEONIZE_PATH,))
                conn.execute("""
                INSERT INTO contacts(pn, lid, full_name)
                SELECT
                    REPLACE(c.their_jid, '@s.whatsapp.net', '') as pn,
                    l.lid as lid,
                    c.full_name as full_name
                FROM neonize_store.whatsmeow_contacts c
                LEFT JOIN neonize_store.whatsmeow_lid_map l
                    ON REPLACE(c.their_jid, '@s.whatsapp.net', '') = l.pn
                WHERE
                    c.their_jid LIKE '%@s.whatsapp.net'
                    AND c.full_name NOT LIKE ''
                ON CONFLICT (pn) DO UPDATE SET
                    lid = excluded.lid,
                    full_name = excluded.full_name
                """)
                print("Contact migration completed")

        except sqlite3.Error as e:
            print("Contact migration failed:", e)

        finally:
            try:
                conn.execute("DETACH DATABASE neonize_store")
            except sqlite3.Error as e:
                print("Detach neonize_store failed:", e)


def resolve_or_save_name(message: MessageEv) -> str:
    """Resolves name using JID (pn or lid) and saved contact map. Returns saved name if contact found, else saves and returns Push Name"""
    sender = message.Info.MessageSource.Sender
    user_id = sender.User
    name = resolve_name_jid(user_id, sender.Server)
    if name:
        return name

    push_name = message.Info.Pushname
    if not push_name:
        push_name = "Unknown"

    alt_sender = message.Info.MessageSource.SenderAlt
    alt_user_id = alt_sender.User
    if not alt_user_id:
        return push_name

    if alt_sender.Server == "lid":
        lid = alt_user_id
        pn = user_id
    else:
        lid = user_id
        pn = alt_user_id

    name = resolve_name_jid(alt_user_id, alt_sender.Server)

    if not name and push_name == "Unknown":
        return push_name  # No point saving a blank push name
    elif not name:
        name = push_name

    # Saving new contact or updating partial contact with LID
    conn.execute(
        """
    INSERT INTO contacts (pn, lid, full_name)
    VALUES (?, ?, ?)
    ON CONFLICT(pn) DO UPDATE SET
    lid = excluded.lid
    """,
        (pn, lid, name),
    )
    print("New contact saved")

    return name


def resolve_name_jid(jid: str, server: str) -> str | None:
    if jid == client.get_me().JID.User or jid == client.get_me().LID.User:
        return "[Me]"
    name = conn.execute(
        f"SELECT full_name FROM contacts WHERE {('lid' if server == 'lid' else 'pn')} = ? LIMIT 1",
        (jid,),
    ).fetchone()
    if name:
        return name[0]
    return None
