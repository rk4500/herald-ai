import signal
import sys
import atexit

from .client import client
from .db import conn

# Unused import to ensure decorators for event handlers are registered from handlers.py file
from . import handlers


def main():
    def handle_sigint(sig, frame):
        print("Shutting down...")
        try:
            client.stop()
        except Exception as e:
            print("Error disconnecting:", e)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    try:
        client.connect()
    finally:
        conn.close()
        print("DB Closed. Shutdown Completed")


if __name__ == "__main__":
    main()
