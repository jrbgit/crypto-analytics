-- Migration 004: Increase precision for supply columns
-- Handle extremely large token supplies (some tokens have supplies > 10^50)

BEGIN;

-- Update total_supply to handle very large supplies
-- Using NUMERIC(80,8) to handle supplies up to ~10^72
ALTER TABLE projects 
ALTER COLUMN total_supply TYPE NUMERIC(80,8);

-- Update max_supply to handle very large supplies  
-- Using NUMERIC(80,8) to handle supplies up to ~10^72
ALTER TABLE projects 
ALTER COLUMN max_supply TYPE NUMERIC(80,8);

-- Log the migration
INSERT INTO migration_log (migration_id, description, applied_at)
VALUES (4, 'Increased precision for total_supply and max_supply columns to NUMERIC(80,8)', NOW());

COMMIT;