PRAGMA foreign_keys = ON;

BEGIN;

UPDATE plan_prescription_blocks
SET duration_min = 30,
    duration_max = 35
WHERE block_role = 'support'
  AND discipline_family = 'strength_training'
  AND prescription_id IN (
      SELECT p.prescription_id
      FROM plan_session_prescriptions p
      JOIN plan_planned_sessions ps ON ps.planned_session_id = p.planned_session_id
      JOIN plan_micro_weeks mw ON mw.week_id = ps.week_id
      JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
      WHERE mb.block_code = 'B3'
  );

COMMIT;