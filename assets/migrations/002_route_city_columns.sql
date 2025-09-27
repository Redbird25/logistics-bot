-- Migration: add canonical city fields to messages
-- Apply after deploying parser city normalization

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS route_from_city_id TEXT,
    ADD COLUMN IF NOT EXISTS route_from_city_name TEXT,
    ADD COLUMN IF NOT EXISTS route_from_country TEXT,
    ADD COLUMN IF NOT EXISTS route_from_region TEXT,
    ADD COLUMN IF NOT EXISTS route_to_city_id TEXT,
    ADD COLUMN IF NOT EXISTS route_to_city_name TEXT,
    ADD COLUMN IF NOT EXISTS route_to_country TEXT,
    ADD COLUMN IF NOT EXISTS route_to_region TEXT;

CREATE INDEX IF NOT EXISTS ix_messages_route_city
    ON messages (route_from_city_id, route_to_city_id);
