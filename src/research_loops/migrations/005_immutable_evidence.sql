CREATE TRIGGER run_prediction_immutable BEFORE UPDATE OF prediction,registration_hash,assignment,created ON runs
BEGIN SELECT RAISE(ABORT,'immutable assignment and prediction'); END;
CREATE TRIGGER run_report_immutable BEFORE UPDATE OF report,report_hash ON runs
WHEN OLD.report IS NOT NULL AND (OLD.report IS NOT NEW.report OR OLD.report_hash IS NOT NEW.report_hash)
BEGIN SELECT RAISE(ABORT,'immutable imported report'); END;
CREATE TRIGGER run_verdict_immutable BEFORE UPDATE OF verdict ON runs
WHEN OLD.verdict IS NOT NULL AND OLD.verdict IS NOT NEW.verdict
BEGIN SELECT RAISE(ABORT,'immutable verdict'); END;
CREATE TRIGGER artifact_no_update BEFORE UPDATE ON artifacts BEGIN SELECT RAISE(ABORT,'immutable artifact'); END;
CREATE TRIGGER artifact_no_delete BEFORE DELETE ON artifacts BEGIN SELECT RAISE(ABORT,'immutable artifact'); END;
