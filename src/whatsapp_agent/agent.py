import json
from groq.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from neonize.events import MessageEv
from neonize.proto.Neonize_pb2 import JID
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from groq import Groq

from .client import client as neonize_client
from whatsapp_agent.chat_info import resolve_name_jid
from .config import GROQ_MODEL
from .db import db_lock, conn

groq_client = Groq()
MODEL = GROQ_MODEL


def get_current_time() -> str:
    india_time = datetime.now((ZoneInfo("Asia/Kolkata")))
    return india_time.strftime("%Y-%m-%d %H:%M")


def get_last_activity_time() -> float:
    with db_lock, conn:
        activity_time: int = conn.execute("""
        SELECT MAX(ts) from (
            SELECT timestamp as ts from messages
            UNION ALL
            SELECT timestamp as ts from reactions
        )
        """).fetchone()[0]
        if activity_time:
            return activity_time
    return 0


def get_messages(chat_jid: JID, catchup_timestamp: float, tail: int = 0) -> str:
    """Get recent messages from the current chat where the agent was invoked. Returns a block of messages from oldest(within timedelta) to newset. Use timedelta_  hours and timedelta_minutes based on the user message. Eg: What did i miss in the last 2 and a half hours would require 2 and 30 as the values for the 2 paramenters"""
    additional_prompt = """Use this list of messages in the form sender: text, in order from oldest to newest, to create a summary of discussions in the chat. The sender "[Me]" represents the user. Use this to say "You said..." instead of treating the user as a general chat member."""

    with db_lock, conn:
        rows = conn.execute(
            f"""
        SELECT text, sender_name, mentioned_jids, quoted_text FROM messages
        WHERE chat_jid = ?
        {"AND timestamp > ?" if tail == 0 else ""}
        ORDER BY timestamp ASC
        {"LIMIT 500" if tail == 0 else "LIMIT " + str(tail)};
        """,
            (str(chat_jid), catchup_timestamp),
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
                quoted_text if len(quoted_text) <= 80 else f"{quoted_text[:80]}..."
            )
            message_str += f'{first_name} replying to "{quoted_text}": {text}'
        else:
            message_str += f"{first_name}: {text}\n"
    if message_str:
        return additional_prompt + "\n" + message_str
    return ""


def get_recent_messages(
    chat_jid: JID, timedelta_hours: int = 1, timedelta_minutes: int = 0, tail: int = 0
) -> str:
    current_time = datetime.now()
    catchup_time = current_time - timedelta(
        hours=timedelta_hours, minutes=timedelta_minutes
    )
    catchup_timestamp = catchup_time.timestamp() * 1000
    print("Get recent messages tool call started", catchup_time, catchup_timestamp)
    return get_messages(chat_jid, catchup_timestamp, tail=tail)


def get_messages_since_active(chat_jid: JID) -> str:
    messages = get_messages(chat_jid, get_last_activity_time())
    if messages:
        return messages
    return "No new messages since last active. Tell the user they didn't miss anything in one short sentance."


tools: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_messages",
            "description": "Get recent messages from the current chat where the agent was invoked. Use timedelta_hours and timedelta_minutes based on the user message. Eg: What did i miss in the last 2 and a half hours would require 2 and 30 as the values for the 2 paramenters. If blank, 1 hour is set",
            "parameters": {
                "type": "object",
                "properties": {
                    "timedelta_minutes": {
                        "type": "number",
                        "description": "The number of minutes to look back in the chat history",
                    },
                    "timedelta_hours": {
                        "type": "number",
                        "description": "The number of hours to look back in the chat history",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_messages_since_active",
            "description": "Get messages since the user was last active (last time they sent a message or reacted to something) from the current chat where the agent was invoked.",
        },
    },
]


def start_conversation(messageEv: MessageEv, user_prompt: str) -> str | None:
    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": f"""
                You are Herald, an AI assistant that helps the user, {neonize_client.get_me().PushName}, keep up with their WhatsApp chats. 
                Use the get_recent_messages tool if the user asks you to catch them up / tell them what they missed over the last X amount of time.
                Use the get_messages_since_active tool if the user simply asks what they missed to to be caught up without any mention of time, this returns all messages since last time the user was active in the chat.
                Only talk about capabilites you currently have, based off the tools availalbe to you and their descriptions, but don't expose toolnames publicly, just convert to what you can achieve with the tools. Never Overstate.
                Right now you can only summarise from the chat you are invoked. Current time is {get_current_time()}. Use this to translate any relative times provided into absolute timedeltas. If vague time provided, like since morning, or a few hours, choose yourself, don't ask the user to clarify. Only if there's no real time provided should you reiterate the requirements. 
                Don't expalin all this to the user though.
                When summarizing do NOT try to make a table of messages actual verbatim messages. ONLY return a summary, in points. With the number of hours if less than 24, or x number of days (no range) being summarized in the title.
                All formatting outside of embolding with SINGLE asterisks should be text, not markdown since whatsapp doesn't render markdown.
                Do not waste tokens answering off topic questions like what a linked list is, only questions related to the chats, the user and yourself. Just say 'Sorry that's out of my scope at the moment.' In case of off topic questions.
                Lastly, do NOT tell the user that you won't do the things you're instructed to avoid like not providing verbatim chats, just don't do them.""",
        },
        {"role": "user", "content": user_prompt},
    ]
    print(f"Inital message: {messages}")

    response = groq_client.chat.completions.create(
        model=MODEL, messages=messages, tools=tools, tool_choice="auto"
    )
    print(f"Inital response: {response}")
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls:
        available_functions = {
            "get_recent_messages": get_recent_messages,
            "get_messages_since_active": get_messages_since_active,
        }

        messages.append(response_message)

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)
            print("calling tool get recent messages")
            function_response = function_to_call(
                chat_jid=messageEv.Info.MessageSource.Chat, **function_args
            )

            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                }
            )

        second_response = groq_client.chat.completions.create(
            model=MODEL, messages=messages
        )
        return second_response.choices[0].message.content
    return response_message.content
