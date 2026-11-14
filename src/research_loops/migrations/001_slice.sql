CREATE TABLE project (
    id INTEGER PRIMARY KEY CHECK (id=1),
    revision INTEGER NOT NULL DEFAULT 0
);
INSERT INTO project(id) VALUES(1);
CREATE TABLE registrations (
    hash TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    evaluator_hash TEXT NOT NULL,
    inputs TEXT NOT NULL,
    supersedes TEXT REFERENCES registrations(hash),
    reason TEXT,
    created TEXT NOT NULL
);
CREATE TRIGGER registration_no_update BEFORE UPDATE ON registrations BEGIN SELECT RAISE(ABORT,'immutable registration'); END;
CREATE TRIGGER registration_no_delete BEFORE DELETE ON registrations BEGIN SELECT RAISE(ABORT,'immutable registration'); END;
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    registration_hash TEXT NOT NULL REFERENCES registrations(hash),
    assignment TEXT NOT NULL,
    execution_status TEXT NOT NULL,
    scientific_outcome TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    report_hash TEXT,
    report TEXT,
    verdict TEXT,
    error TEXT,
    prediction TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    kind TEXT NOT NULL,
    hash TEXT NOT NULL,
    size INTEGER NOT NULL,
    UNIQUE(run_id,kind)
);
CREATE TABLE events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TRIGGER event_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER event_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
