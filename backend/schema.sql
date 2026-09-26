PRAGMA foreign_keys = ON;

CREATE TABLE email_threads (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE emails (
    id INTEGER PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES email_threads(id),
    message_id TEXT NOT NULL UNIQUE,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at DATETIME NOT NULL,
    received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_emails_thread_id ON emails(thread_id);

CREATE TABLE attachments (
    id INTEGER PRIMARY KEY,
    email_id INTEGER NOT NULL REFERENCES emails(id),
    filename TEXT NOT NULL,
    content BLOB NOT NULL,
    received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_attachments_email_id ON attachments(email_id);

CREATE TABLE purchase_orders (
    id INTEGER PRIMARY KEY,
    thread_id INTEGER NOT NULL UNIQUE REFERENCES email_threads(id),
    supplier_order_number VARCHAR(128) NOT NULL UNIQUE,
    current_version_id INTEGER REFERENCES order_versions(id),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_purchase_orders_supplier_order_number ON purchase_orders(supplier_order_number);

CREATE TABLE order_versions (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    version_number INTEGER NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    created_by_type VARCHAR(16) NOT NULL CHECK (created_by_type IN ('agent', 'human')),
    source_email_id INTEGER UNIQUE REFERENCES emails(id),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_order_version_number UNIQUE (order_id, version_number)
);
CREATE INDEX ix_order_versions_order_id ON order_versions(order_id);

CREATE TABLE supplier_snapshots (
    id INTEGER PRIMARY KEY,
    order_version_id INTEGER NOT NULL UNIQUE REFERENCES order_versions(id),
    name TEXT NOT NULL,
    address TEXT,
    contact_information TEXT,
    salesperson TEXT
);

CREATE TABLE order_detail_snapshots (
    id INTEGER PRIMARY KEY,
    order_version_id INTEGER NOT NULL UNIQUE REFERENCES order_versions(id),
    buyer_po_reference VARCHAR(128),
    document_date DATE,
    order_received_date DATE,
    buyer_details TEXT,
    billing_address TEXT
);

CREATE TABLE shipping_snapshots (
    id INTEGER PRIMARY KEY,
    order_version_id INTEGER NOT NULL UNIQUE REFERENCES order_versions(id),
    delivery_address TEXT,
    shipping_method TEXT
);
CREATE TABLE order_financial_summaries (
    id INTEGER PRIMARY KEY,
    order_version_id INTEGER NOT NULL UNIQUE REFERENCES order_versions(id),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    plant_cost NUMERIC(14, 2) CHECK (plant_cost >= 0),
    variety_license_fee_total NUMERIC(14, 2) CHECK (variety_license_fee_total >= 0),
    container_cost NUMERIC(14, 2) CHECK (container_cost >= 0),
    label_cost NUMERIC(14, 2) CHECK (label_cost >= 0),
    freight NUMERIC(14, 2) CHECK (freight >= 0),
    grand_total NUMERIC(14, 2) CHECK (grand_total >= 0)
);

CREATE TABLE line_item_snapshots (
    id INTEGER PRIMARY KEY,
    order_version_id INTEGER NOT NULL REFERENCES order_versions(id),
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    description TEXT NOT NULL,
    size TEXT,
    ordered_quantity NUMERIC(14, 3) CHECK (ordered_quantity >= 0),
    confirmed_quantity NUMERIC(14, 3) CHECK (confirmed_quantity >= 0),
    catalog_price NUMERIC(14, 2) CHECK (catalog_price >= 0),
    customer_price NUMERIC(14, 2) CHECK (customer_price >= 0),
    variety_license_fee NUMERIC(14, 2) CHECK (variety_license_fee >= 0),
    extended_line_amount NUMERIC(14, 2) CHECK (extended_line_amount >= 0),
    item_notes TEXT,
    scheduled_shipping_date_or_week VARCHAR(128),
    CONSTRAINT uq_line_item_number UNIQUE (order_version_id, line_number)
);
CREATE INDEX ix_line_item_snapshots_order_version_id ON line_item_snapshots(order_version_id);

CREATE TABLE processing_runs (
    id INTEGER PRIMARY KEY,
    email_id INTEGER NOT NULL REFERENCES emails(id),
    attachment_id INTEGER REFERENCES attachments(id),
    temporal_workflow_id VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    stage VARCHAR(64),
    error_summary TEXT,
    completed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_processing_runs_email_id ON processing_runs(email_id);

CREATE TABLE chat_conversations (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_chat_conversations_order_id ON chat_conversations(order_id);

CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES chat_conversations(id),
    reply_to_message_id INTEGER REFERENCES chat_messages(id),
    sender_type VARCHAR(16) NOT NULL CHECK (sender_type IN ('human', 'agent', 'system')),
    message_type VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    intent VARCHAR(32),
    temporal_workflow_id VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_chat_messages_conversation_id ON chat_messages(conversation_id);

CREATE TABLE agent_change_drafts (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    chat_message_id INTEGER NOT NULL REFERENCES chat_messages(id),
    base_version_id INTEGER NOT NULL REFERENCES order_versions(id),
    proposed_snapshot_json TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'discarded')),
    resolved_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_agent_change_drafts_order_id ON agent_change_drafts(order_id);

CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    order_version_id INTEGER REFERENCES order_versions(id),
    chat_message_id INTEGER REFERENCES chat_messages(id),
    agent_change_draft_id INTEGER REFERENCES agent_change_drafts(id),
    actor_type VARCHAR(16) NOT NULL CHECK (actor_type IN ('agent', 'human', 'system')),
    action VARCHAR(64) NOT NULL,
    change_summary_json TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_audit_events_order_id ON audit_events(order_id);