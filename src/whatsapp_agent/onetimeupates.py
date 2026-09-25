import sqlite3
# from .config import DB_PATH


def alter_messages_table():
    conn = sqlite3.connect("database.db")

    with conn:
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN sender_name TEXT;")
        except sqlite3.Error as e:
            print("failed to alter table:", e)
        finally:
            rows = conn.execute("SELECT * FROM messages LIMIT 30").fetchall()
            for row in rows:
                print(row)


if __name__ == "__main__":
    alter_messages_table()
