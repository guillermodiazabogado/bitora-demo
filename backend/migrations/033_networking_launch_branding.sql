ALTER TABLE events ADD COLUMN networking_brand_title TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN networking_brand_welcome TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN networking_brand_mode TEXT NOT NULL DEFAULT 'POWERED_BY_BITORA';
ALTER TABLE events ADD COLUMN networking_public_base_url TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN networking_launch_state TEXT NOT NULL DEFAULT 'DRAFT';
ALTER TABLE events ADD COLUMN networking_launched_at TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN networking_launch_updated_at TEXT NOT NULL DEFAULT '';
