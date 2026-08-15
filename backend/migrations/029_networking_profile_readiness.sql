ALTER TABLE events ADD COLUMN networking_readiness_required TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN networking_readiness_recommended TEXT NOT NULL DEFAULT '';

ALTER TABLE networking_intents ADD COLUMN completed_title TEXT NOT NULL DEFAULT '';
ALTER TABLE networking_intents ADD COLUMN completed_function TEXT NOT NULL DEFAULT '';
ALTER TABLE networking_intents ADD COLUMN completed_seniority TEXT NOT NULL DEFAULT '';
ALTER TABLE networking_intents ADD COLUMN completed_organization_activity TEXT NOT NULL DEFAULT '';
ALTER TABLE networking_intents ADD COLUMN completed_organization_specialty TEXT NOT NULL DEFAULT '';
ALTER TABLE networking_intents ADD COLUMN completed_organization_description TEXT NOT NULL DEFAULT '';
