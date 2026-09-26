# Procurement assistant take-home

## What to build

Build an application that manages purchase orders received through supplier emails and PDF acknowledgements:

- **Parse purchase orders.** The agent reads the full PDF, extracts the order information, and stores and displays it in a structured form.
- **Correct parsed information.** The user can edit what the agent extracted.
- **Handle change orders.** When a revised acknowledgement arrives, the agent identifies what changed and updates the existing purchase order accordingly.
- **Chat in the application.** The user can ask questions about the order and request changes through chat in the UI.

### What to track and save

The application should track and save:

- **Supplier details:** name, address, contact information and salesperson.
- **Order details:** supplier order number, buyer PO reference, document date, order received date, buyer details and billing address.
- **Shipping:** delivery address, shipping method and **scheduled shipping date/week for each line item**.
- **Every line item:** full description, size, ordered quantity, confirmed quantity, catalog price, special/customer price ("Your Price"), variety license fee, extended line amount and item notes.

`schema.sql` is a starter schema; you can modify and extend it as much as you need.

## Setup

The starter uses **Python 3.12** and only the standard library.

From the repository root:

```sh
python3.12 init_db.py
```

This creates `data/app.sqlite3` from `schema.sql`, with no seeded rows. It refuses to overwrite an existing database.

## How email simulation works

The simulator stores the incoming email and any supplied PDF attachments, commits the records, and directly calls:

```python
handler.handle_event(event_type, record_id, db_path)
```

`db_path` is an absolute `pathlib.Path` to the database. The records are available before the handler runs. The call is synchronous, so the command waits for the handler to finish.

| Command | Records stored | Event | `record_id` |
| --- | --- | --- | --- |
| `new-thread` | Thread, first email and supplied PDFs | `email.received` | Email ID |
| `email` | Email in an existing thread and supplied PDFs | `email.received` | Email ID |

PDFs arrive as email attachments. Each email produces one handler call after the email and all its attachments are stored. Chat happens in the application's UI.

The supplied handler is an unimplemented stub. It raises `NotImplementedError` after the simulator stores the input.

### New thread with its first email and PDF

```sh
python3.12 simulate.py new-thread \
  --email fixtures/initial/email.json \
  --pdf fixtures/initial/acknowledgement.pdf
```

On a fresh database, this creates thread `1` and email `1`, then calls `handle_event("email.received", 1, db_path)`. Only the initial email and PDF are delivered at this point.

### Later email in the same thread

```sh
python3.12 simulate.py email --thread 1 \
  --email fixtures/update/email.json \
  --pdf fixtures/update/acknowledgement.pdf
```

This creates email `2` in the same thread and calls `handle_event("email.received", 2, db_path)`.

## Submission

Submit your work on a branch named `<your_name>/submission`.
