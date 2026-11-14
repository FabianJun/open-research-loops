ALTER TABLE runs ADD COLUMN execution_metadata TEXT NOT NULL DEFAULT '{"backend":"fake","provider":"offline","model":"deterministic-v1","sdk_version":null,"cost_micro_usd":0,"sandbox_image":null}';
