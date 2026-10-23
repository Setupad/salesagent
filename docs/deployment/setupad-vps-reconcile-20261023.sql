BEGIN;

LOCK TABLE alembic_version, push_notification_configs IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF (SELECT array_agg(version_num ORDER BY version_num) FROM alembic_version)
        IS DISTINCT FROM ARRAY['f7d2c3b4a901']::varchar[] THEN
        RAISE EXCEPTION 'Expected the deployed VPS revision f7d2c3b4a901 alone';
    END IF;

    IF EXISTS (SELECT 1 FROM push_notification_configs) THEN
        RAISE EXCEPTION 'Webhook registrations require a separate data reconciliation';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'push_notification_configs'
          AND column_name = 'protocol'
          AND data_type = 'character varying'
          AND character_maximum_length = 20
          AND is_nullable = 'YES'
          AND column_default IS NULL
          AND is_generated = 'NEVER'
    ) THEN
        RAISE EXCEPTION 'The protocol column does not match revision 6a52cf43ad75';
    END IF;
END
$$;

INSERT INTO alembic_version (version_num) VALUES ('6a52cf43ad75');

COMMIT;