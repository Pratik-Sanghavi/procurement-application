"""Store a simulated email with its PDF attachments, then call the candidate's handler."""

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

try:
    import handler
    from init_db import DEFAULT_DB
except ModuleNotFoundError:
    import backend.handler as handler
    from backend.init_db import DEFAULT_DB


def read_email(path: Path) -> dict:
    email = json.loads(path.read_text(encoding="utf-8"))
    fields = {"message_id", "sender", "recipient", "subject", "body", "sent_at"}
    if not isinstance(email, dict) or set(email) != fields:
        raise ValueError(f"Email JSON must contain exactly: {', '.join(sorted(fields))}")
    if any(not isinstance(value, str) for value in email.values()):
        raise ValueError("Email fields must be strings.")
    if not email["message_id"].strip():
        raise ValueError("message_id must not be empty.")
    return email


def read_pdf(path: Path) -> tuple[str, bytes]:
    content = path.read_bytes()
    if not content.startswith(b"%PDF-"):
        raise ValueError(f"{path} does not have a PDF header.")
    return path.name, content


def store_input(args: argparse.Namespace, db_path: Path) -> tuple[str, int]:
    # Read inputs before making any database changes.
    email = read_email(args.email)
    pdfs = [read_pdf(path) for path in args.pdf]

    # mode=rw requires an existing database: simulation never creates one silently.
    with closing(sqlite3.connect(db_path.as_uri() + "?mode=rw", uri=True)) as db:
        db.execute("PRAGMA foreign_keys = ON")
        with db:
            if args.command == "new-thread":
                thread_id = db.execute(
                    "INSERT INTO email_threads (subject) VALUES (?)", (email["subject"],)
                ).lastrowid
            else:
                thread_id = args.thread
            record_id = db.execute(
                """INSERT INTO emails
                   (thread_id, message_id, sender, recipient, subject, body, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (thread_id, email["message_id"], email["sender"], email["recipient"],
                 email["subject"], email["body"], email["sent_at"]),
            ).lastrowid
            db.executemany(
                "INSERT INTO attachments (email_id, filename, content) VALUES (?, ?, ?)",
                [(record_id, name, content) for name, content in pdfs],
            )
    # The transaction has committed and the connection is closed at this point.
    print(f"Stored thread_id={thread_id}, email_id={record_id}, PDFs={len(pdfs)}.", flush=True)
    return "email.received", record_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to an initialized SQLite DB")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("new-thread", "Create a thread with its first email and optional PDFs"),
        ("email", "Add an email and optional PDFs to an existing thread"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--email", type=Path, required=True, help="Email JSON file")
        command.add_argument("--pdf", type=Path, action="append", default=[], help="PDF to attach; repeatable")
        if name == "email":
            command.add_argument("--thread", type=int, required=True)
    args = parser.parse_args(argv)
    db_path = args.db.resolve()

    try:
        event_type, record_id = store_input(args, db_path)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"Input was not stored: {error}", file=sys.stderr)
        return 1

    print(f"Calling handler.handle_event({event_type!r}, {record_id}, {str(db_path)!r}).", flush=True)
    try:
        handler.handle_event(event_type, record_id, db_path)
    except Exception:
        print("Input remains stored. Handler failed; see the exception below.", file=sys.stderr)
        raise
    print("Handler finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
