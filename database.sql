BEGIN TRANSACTION;
CREATE TABLE operation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,  -- 'import', 'send', 'export'
            total_records INTEGER,
            success_count INTEGER,
            failed_count INTEGER,
            details TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP
        );
INSERT INTO "operation_log" VALUES(1,'send_messages',10,10,0,'Elapsed: 10.86s','2026-08-14 20:45:40.620181','2026-08-14 20:45:51.598028');
INSERT INTO "operation_log" VALUES(2,'send_messages',10,0,0,'Elapsed: 9.22s','2026-08-14 20:45:42.873055','2026-08-14 20:45:52.118179');
CREATE TABLE sent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_phone TEXT NOT NULL,
            formatted_phone TEXT NOT NULL,
            contact_name TEXT,
            passport_number TEXT,
            message_type TEXT NOT NULL,  -- 'sms' or 'whatsapp'
            message_content TEXT NOT NULL,
            status TEXT NOT NULL,        -- 'success', 'failed', 'pending'
            message_id TEXT,             -- معرف الرسالة من المزود
            provider TEXT,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(contact_phone, message_type)  -- منع التكرار
        );
CREATE INDEX idx_phone_type
            ON sent_messages(contact_phone, message_type);
CREATE INDEX idx_status
            ON sent_messages(status);
CREATE INDEX idx_sent_at
            ON sent_messages(sent_at);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('operation_log',2);
COMMIT;
