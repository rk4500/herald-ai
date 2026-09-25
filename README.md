# WhatsApp Agent (Herald)

A WhatsApp bot built on [neonize](https://github.com/krypton-byte/neonize) that logs every message and reaction to a local SQLite database, resolves sender identities across WhatsApp's PN/LID contact scheme, and exposes a Groq-backed AI assistant ("Herald") that can summarize what you missed in a chat.

## How it works

`whatsapp_agent/__init__.py` is the entry point. On startup it initializes the database schema, runs a one time contact import from neonize's own session store, then connects the WhatsApp client and blocks on the event loop.

Two neonize event handlers drive everything:

- `ConnectedEv` (`client.py`) just logs that the session is live.
- `MessageEv` (`handlers.py`) fires on every incoming message or reaction. It resolves the sender's saved name, writes a row to `messages` or `reactions`, and if the message is from the account owner and starts with `ping`, `/ai`, or `/herald`, triggers a reply.

All database access goes through a single shared `sqlite3.Connection` (`db.py`) in WAL mode, guarded by one `threading.Lock` since neonize event callbacks can run off the main thread.

## Current features

- [x] Persistent message logging to SQLite (`messages` table), deduplicated on `(chat_jid, msg_id)` so overlapping backfills don't create duplicate rows.
- [x] Reaction logging to a separate `reactions` table, with `INSERT ... ON CONFLICT DO UPDATE` so an updated or removed reaction overwrites the old row instead of duplicating it.
- [x] Sender identity resolution across WhatsApp's dual PN (phone number) / LID (linked ID) addressing. `chat_info.resolve_or_save_name` checks the local `contacts` table first, falls back to the message's push name, and backfills the contact map as new senders are seen.
- [x] One time contact import on startup that attaches neonize's own `session.db` and copies known contacts (`whatsmeow_contacts` joined with `whatsmeow_lid_map`) into the local `contacts` table, so names are available immediately instead of only after someone messages.
- [x] `ping` command: replies `pong` and echoes the last 10 messages in that chat.
- [x] `/ai` and `/herald` commands: hands the message text to Herald, a Groq powered assistant.
- [x] Herald can call a `get_recent_messages` tool to pull messages from the current chat within a caller specified time window and summarize them in bullet points, formatted for WhatsApp's plain text rendering (single asterisk bold, no markdown tables).
- [x] Herald is scoped to stay on topic. Off topic questions get a canned refusal instead of burning tokens on an unrelated answer.
- [x] Commands only work when sent by the account owner (`IsFromMe`), so the bot doesn't respond to arbitrary contacts.

## Fixed issues

- [x] `on_message` used to call `start_conversation` while still holding `db_lock`, and `get_recent_messages` tried to acquire the same non-reentrant lock again on the same thread. Any `/ai` or `/herald` message deadlocked the process and locked the database until it was killed. The AI dispatch now runs outside the `with db_lock, conn:` block.
- [x] `message.Info.Timestamp` from neonize is in milliseconds, while `get_recent_messages` used to build its cutoff from `datetime.now().timestamp()`, which is in seconds. Units are now consistent, so the "recent window" filter actually filters.

## Planned features

- [ ] Reply context: capture what message a person is replying to (not just what they said), so logged messages and summaries reflect actual reply chains instead of a flat timeline.
- [ ] Smarter "what did I miss" summaries: instead of a fixed time window, look back to the user's own last message or reaction in the chat and summarize everything since then.
- [ ] Relative time support in Herald (e.g. "since this morning") once the bot has a reliable notion of current time to reason with.
- [ ] Summaries across multiple chats in one request, not just the chat Herald was invoked from.
- [ ] Reaction context surfaced in summaries (e.g. "3 people reacted with 👍 to X").
