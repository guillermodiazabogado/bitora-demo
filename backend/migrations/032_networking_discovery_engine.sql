ALTER TABLE events ADD COLUMN networking_discovery_enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE events ADD COLUMN networking_discovery_exploration_frequency INTEGER NOT NULL DEFAULT 4;
ALTER TABLE events ADD COLUMN networking_discovery_batch_size INTEGER NOT NULL DEFAULT 3;

CREATE INDEX IF NOT EXISTS idx_networking_interactions_actor_type
ON networking_interaction_events(event_id, actor_participation_id, event_type, target_participation_id);
