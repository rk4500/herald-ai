from neonize.client import NewClient
from neonize.events import MessageEv
from neonize import extract_text

from whatsapp_agent.chat_info import resolve_or_save_name
from .client import client
from .db import conn, db_lock


@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv) -> None:
    text = extract_text(message.Message)
    chat = message.Info.MessageSource.Chat
    print(message)
    with db_lock, conn:
        sender_name = resolve_or_save_name(message)
        if message.Info.Type == "reaction":
            reaction = message.Message.reactionMessage.text or "Removed"
            # Saving the reaction with resolved sender name
            conn.execute(
                """
            INSERT INTO reactions (chat_jid, msg_id, sender, sender_name, text, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_jid, msg_id, sender)
            DO UPDATE SET
            text = excluded.text,
            timestamp = excluded.timestamp;
            """,
                (
                    str(chat),
                    str(message.Message.reactionMessage.key.ID),
                    str(message.Info.MessageSource.Sender),
                    sender_name,
                    reaction,
                    message.Info.Timestamp,
                ),
            )
            print(
                f"Row logged with reaction content: {reaction}\nSent by: {sender_name}"
            )
            return

        if message.Info.MessageSource.Chat.User == "status":
            print("Not an actual message (status update)")
            return

        if not text:
            if message.Info.MediaType:
                text = message.Info.MediaType
            else:
                text = "Other message type"

        # Saving the message with resolved sender name
        conn.execute(
            """
        INSERT INTO messages (chat_jid, msg_id, sender, sender_name, text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_jid, msg_id)
        DO NOTHING;
        """,
            (
                str(chat),
                str(message.Info.ID),
                str(message.Info.MessageSource.Sender),
                sender_name,
                text,
                message.Info.Timestamp,
            ),
        )
        print(f"Row logged with text content: {text}\nSent by: {sender_name}")

        # To disable listening for commands from others
        if not message.Info.MessageSource.IsFromMe:
            return

        # Test response to see if messsage logging and building works properly
        if text == "ping":
            client.reply_message("pong", message)
            rows = conn.execute(
                """
            SELECT text, sender_name FROM messages
            WHERE chat_jid = ?
            ORDER BY timestamp DESC
            LIMIT 10;
            """,
                (str(chat),),
            ).fetchall()
            message_str = ""
            for text, name in rows:
                name = name or "Unknown"
                first_name = name.split(" ")[0]
                message_str += f"{first_name}: {text}\n"
            print(message_str)
            client.reply_message(message_str, message)

        elif text == "info":
            if not message.Info.MessageSource.IsGroup:
                print("Not a group broski")
                return
            print(client.get_group_info(chat))
