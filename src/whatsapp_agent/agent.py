from langchain_core.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from neonize.proto.Neonize_pb2 import Global___JID
from datetime import datetime, timedelta
from .db import db_lock, conn


@tool
def get_recent_messages(
    chat_jid: Global___JID, timedelta_hours: int = 0, timedelta_minutes: int = 30
):
    """Get recent messages from the current chat where the agent was invoked. Use timedelta_  hours and timedelta_minutes based on the user message. Eg: What did i miss in the last 2 and a half hours would require 2 and 30 as the values for the 2 paramenters"""
    current_time = datetime.now()
    catchup_time = current_time - timedelta(
        hours=timedelta_hours, minutes=timedelta_minutes
    )
    catchup_timestamp = catchup_time.timestamp()
    with db_lock, conn:
        rows = conn.execute(
            """
        SELECT text FROM messages
        WHERE chat_jid = ?
        AND timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT 500;
        """,
            (chat_jid, catchup_timestamp),
        )
