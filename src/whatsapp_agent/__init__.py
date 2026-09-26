from .db import init_db
from .chat_info import import_chats


def main():
    init_db()
    import_chats()


if __name__ == "__main__":
    main()
