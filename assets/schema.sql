CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS chats (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY,
    chat_id TEXT NOT NULL,
    message_id BIGINT NOT NULL,
    posted_at TIMESTAMPTZ NOT NULL,
    raw_text TEXT NOT NULL,
    route_from TEXT,
    route_to TEXT,
    vehicle_type TEXT,
    tonnage_tons DOUBLE PRECISION,
    price_amount DOUBLE PRECISION,
    price_currency TEXT,
    contact TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    extra_metadata JSONB DEFAULT '{}'::jsonb,
    hash_digest TEXT UNIQUE NOT NULL,
    duplicate_of_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_messages_chat_posted ON messages (chat_id, posted_at DESC);
CREATE INDEX IF NOT EXISTS ix_messages_vehicle ON messages (vehicle_type);
CREATE INDEX IF NOT EXISTS ix_messages_route ON messages (route_from, route_to);
CREATE INDEX IF NOT EXISTS ix_messages_raw_text_trgm ON messages USING gin (raw_text gin_trgm_ops);

