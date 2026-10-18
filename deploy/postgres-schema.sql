-- AgentTerm distributed sync schema. Apply transactionally through the
-- selected migration runner; never use this schema against production without
-- independent review and backup verification.
CREATE TABLE IF NOT EXISTS agentterm_objects (
  project TEXT NOT NULL, object_id TEXT NOT NULL, sender_device TEXT NOT NULL,
  sequence BIGINT NOT NULL, envelope TEXT NOT NULL, digest TEXT NOT NULL,
  PRIMARY KEY (project, object_id, sender_device, sequence)
);
CREATE TABLE IF NOT EXISTS agentterm_sequences (
  device TEXT NOT NULL, project TEXT NOT NULL, sequence BIGINT NOT NULL,
  digest TEXT NOT NULL, PRIMARY KEY (device, project, sequence)
);
CREATE TABLE IF NOT EXISTS agentterm_cursors (
  device TEXT NOT NULL, project TEXT NOT NULL, sequence BIGINT NOT NULL,
  PRIMARY KEY (device, project)
);
