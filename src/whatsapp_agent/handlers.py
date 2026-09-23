from neonize.client import NewClient
from neonize.events import MessageEv
from .client import client
from .db import conn, db_lock


@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv) -> None:
    from neonize import extract_text

    text = extract_text(message.Message)
    chat = message.Info.MessageSource.Chat
    chat_str = str(chat)
    print(message)
    with db_lock, conn:
        conn.execute(
            """
        INSERT INTO messages (chat_jid, msg_id, sender, text, timestamp)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chat_jid, msg_id)
        DO NOTHING;
        """,
            (
                chat_str,
                str(message.Info.ID),
                str(message.Info.MessageSource.Sender),
                text,
                message.Info.Timestamp,
            ),
        )
        print("Row logged with text content: ", text)

    if not message.Info.MessageSource.IsFromMe:
        return

    if text == "ping":
        client.reply_message("pong", message)
        rows = conn.execute(
            """
        SELECT text FROM messages
        WHERE chat_jid = ?
        ORDER BY timestamp DESC
        LIMIT 10;
        """,
            (chat_str,),
        )
        message_str = ""
        for row in rows:
            print(row)
            message_str += row[0] + "\n"
        print(message_str)
        client.reply_message(message_str, message)

    elif text == "info":
        if not message.Info.MessageSource.IsGroup:
            print("Not a group broski")
            return
        print(client.get_group_info(chat))
