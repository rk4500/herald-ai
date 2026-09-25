from whatsapp_agent.chat_info import import_chats

from .client import client
from .db import init_db, conn

# Unused import to ensure decorators for event handlers are registered from handlers.py file
import whatsapp_agent.handlers


def main():
    init_db()
    import_chats()

    try:
        client.connect()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
