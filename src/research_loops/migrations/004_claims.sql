CREATE TABLE claims (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    statement TEXT NOT NULL,
    tag TEXT NOT NULL CHECK(tag IN ('measured','simulated','cited','assumed','interpretation','hypothesis')),
    metric TEXT NOT NULL,
    supersedes TEXT REFERENCES claims(id)
);
CREATE TRIGGER claim_no_update BEFORE UPDATE ON claims BEGIN SELECT RAISE(ABORT,'append only claim'); END;
CREATE TRIGGER claim_no_delete BEFORE DELETE ON claims BEGIN SELECT RAISE(ABORT,'append only claim'); END;
CREATE TABLE challenges (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claims(id),
    evidence_run TEXT NOT NULL REFERENCES runs(id),
    grounds TEXT NOT NULL
);
CREATE TRIGGER challenge_no_update BEFORE UPDATE ON challenges BEGIN SELECT RAISE(ABORT,'append only challenge'); END;
CREATE TRIGGER challenge_no_delete BEFORE DELETE ON challenges BEGIN SELECT RAISE(ABORT,'append only challenge'); END;
