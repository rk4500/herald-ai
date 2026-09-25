import json
from groq.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from neonize.events import MessageEv
from neonize.proto.Neonize_pb2 import JID
from datetime import datetime, timedelta
from groq import Groq

from .config import GROQ_MODEL
from .db import db_lock, conn

client = Groq()
MODEL = GROQ_MODEL


def get_recent_messages(
    chat_jid: JID, timedelta_hours: int = 1, timedelta_minutes: int = 0
) -> str:
    """Get recent messages from the current chat where the agent was invoked. Returns a block of messages from oldest(within timedelta) to newset. Use timedelta_  hours and timedelta_minutes based on the user message. Eg: What did i miss in the last 2 and a half hours would require 2 and 30 as the values for the 2 paramenters"""
    current_time = datetime.now()
    catchup_time = current_time - timedelta(
        hours=timedelta_hours, minutes=timedelta_minutes
    )
    catchup_timestamp = catchup_time.timestamp() * 1000
    print("Get recent messages tool call started", catchup_time, catchup_timestamp)

    with db_lock, conn:
        rows = conn.execute(
            """
        SELECT text, sender_name FROM messages
        WHERE chat_jid = ?
        AND timestamp >= ?
        ORDER BY timestamp ASC
        LIMIT 500;
        """,
            (str(chat_jid), catchup_timestamp),
        ).fetchall()
    # Construct agent context with name and message content pairs
    message_str = ""
    for text, name in rows:
        name = name or "Unknown"
        first_name = name.split(" ")[0]
        message_str += f"{first_name}: {text}\n"
    print(message_str)
    return message_str


tools: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_messages",
            "description": "Get recent messages from the current chat where the agent was invoked. Use timedelta_hours and timedelta_minutes based on the user message. Eg: What did i miss in the last 2 and a half hours would require 2 and 30 as the values for the 2 paramenters. If left blank, a default of 1 hour and 0 minutes is set.",
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
]


def start_conversation(messageEv: MessageEv, user_prompt: str) -> str | None:
    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": """
                You are Herald, an AI assistant that helps the user keep up with their WhatsApp chats. 
                Use the get_recent_messages tool if the user asks you to catch them up or tell them what they missed
                Only talk about capabilites you currently have, based off the tools availalbe to you and their descriptions, but don't expose toolnames publicly, just convert to what you can achieve with the tools. Never Overstate.
                Right now you can only summarise from the chat you are invoked and can take a specific time only, no relative time like today morning (you don't know what time it is right now). Don't expalin all this to the user though.
                When summarizing do NOT try to make a table of messages actual verbatim messages. ONLY return a summary, in points.
                All formatting outside of embolding with SINGLE asterisks should be text, not markdown since whatsapp doesn't render markdown.
                Do not waste tokens answering off topic questions like what a linked list is, only questions related to the chats and yourself. Just say 'Sorry that's out of my scope at the moment.' In case of off topic questions.
                Lastly, do NOT tell the user that you won't do the things you're instructed to avoid like not providing verbatim chats, just don't do them.""",
        },
        {"role": "user", "content": user_prompt},
    ]
    print(f"Inital message: {messages}")

    response = client.chat.completions.create(
        model=MODEL, messages=messages, tools=tools, tool_choice="auto"
    )
    print(f"Inital response: {response}")
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls:
        available_functions = {
            "get_recent_messages": get_recent_messages,
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

        second_response = client.chat.completions.create(model=MODEL, messages=messages)
        return second_response.choices[0].message.content
    return response_message.content
