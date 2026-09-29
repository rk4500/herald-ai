from neonize.client import NewClient
from neonize.events import MessageEv, OfflineSyncCompletedEv
from neonize import extract_text
import typing
import json

from neonize.utils import Jid2String

from .agent import start_conversation
from .chat_info import import_chats, resolve_name_jid, resolve_or_save_name
from .client import client
from .db import conn, db_lock


@client.event(event=OfflineSyncCompletedEv)
def on_offline_sync(NewClient, OfflineSyncCompletedEv) -> None:
    print("OfflineSyncEv Importing/Syncing Chats")
    import_chats()


@client.event(MessageEv)
def on_message(client: NewClient, messageEv: MessageEv) -> None:
    message = messageEv.Message
    chat = messageEv.Info.MessageSource.Chat
    print(messageEv)

    # Extracting text, mentioned JIDs and quoted responses, if any.
    text = ""
    quotedText = ""
    json_jids: str | None = None
    if message.conversation:
        text = message.conversation
    else:
        for field_name in [
            "extendedTextMessage",
            "imageMessage",
            "videoMessage",
            "documentMessage",
        ]:
            if message.HasField(field_name):
                field: typing.Any = getattr(message, field_name, None)
                text = getattr(field, "text", "") or getattr(field, "caption", "")
                if field.contextInfo.HasField("quotedMessage"):
                    quotedText = extract_text(field.contextInfo.quotedMessage)
                    print(f"Quoted text: {quotedText}")
                jids: list[str] = []
                for jid in field.contextInfo.mentionedJID:
                    jids.append(jid.split("@")[0])
                json_jids = json.dumps(jids) if jids else None

    with db_lock, conn:
        sender_name = resolve_or_save_name(messageEv)
        if messageEv.Info.Type == "reaction":
            reaction = messageEv.Message.reactionMessage.text or "Removed"
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
                    str(messageEv.Message.reactionMessage.key.ID),
                    str(messageEv.Info.MessageSource.Sender),
                    sender_name,
                    reaction,
                    messageEv.Info.Timestamp,
                ),
            )
            print(
                f"Row logged with reaction content: {reaction}\nSent by: {sender_name}"
            )
            return

        if messageEv.Info.MessageSource.Chat.User == "status":
            print("Not an actual message (status update)")
            return

        if not text:
            if messageEv.Info.MediaType:
                text = messageEv.Info.MediaType
            else:
                text = "Other message type"

        # Saving the message with resolved sender name
        conn.execute(
            """
        INSERT INTO messages (chat_jid, msg_id, sender, sender_name, text, timestamp, quoted_text, mentioned_jids)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_jid, msg_id)
        DO NOTHING;
        """,
            (
                str(chat),
                str(messageEv.Info.ID),
                Jid2String(messageEv.Info.MessageSource.Sender),
                sender_name,
                text,
                messageEv.Info.Timestamp,
                quotedText or None,
                json_jids or None,
            ),
        )
        print(
            f"Row logged with text content: {text}\nSent by: {sender_name} with mentioned jids: {json_jids}\nQuoted text: {quotedText}"
        )

        # To disable listening for commands from others
        if not messageEv.Info.MessageSource.IsFromMe:
            return

        # Test response to see if messsage logging and building works properly
        if text == "ping":
            rows = conn.execute(
                """
                SELECT text, sender_name, mentioned_jids, quoted_text FROM messages
                WHERE chat_jid = ?
                ORDER BY timestamp DESC
                LIMIT 10;
                """,
                (str(chat),),
            ).fetchall()
            # Construct agent context with name and message content pairs
            message_str = ""
            for text, name, mentioned_jids, quoted_text in rows:
                name = name or "Unknown"
                first_name = name.split(" ")[0]
                if mentioned_jids:
                    jids = json.loads(mentioned_jids)
                    for jid in jids:
                        id = jid.split("@")[0]
                        server = jid.split("@")[1]
                        mentioned_name = resolve_name_jid(id, server)
                        text = text.replace(f"@{jid}", f"@{mentioned_name}")
                if quoted_text:
                    quoted_text = (
                        quoted_text
                        if len(quoted_text) <= 80
                        else f"{quoted_text[:80]}..."
                    )
                    message_str += f'{first_name} replying to "{quoted_text}": {text}'
                else:
                    message_str += f"{first_name}: {text}\n"

            client.reply_message(message_str, messageEv)

    if messageEv.Info.MessageSource.IsFromMe and (
        "/ai" in text[0:3] or "/herald" in text[0:7]
    ):
        response = start_conversation(messageEv, text) or "Groq Error"
        client.reply_message(response, messageEv)
