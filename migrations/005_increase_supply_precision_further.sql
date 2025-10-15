-- Migration 005: Further increase precision for supply columns
-- Handle extremely large token supplies (some tokens have supplies > 10^76)

BEGIN;

-- Update total_supply to handle even larger supplies
-- Using NUMERIC(100,8) to handle supplies up to ~10^92
ALTER TABLE crypto_projects 
ALTER COLUMN total_supply TYPE NUMERIC(100,8);

-- Update max_supply to handle even larger supplies  
-- Using NUMERIC(100,8) to handle supplies up to ~10^92
ALTER TABLE crypto_projects 
ALTER COLUMN max_supply TYPE NUMERIC(100,8);

-- Also update circulating_supply for consistency
ALTER TABLE crypto_projects 
ALTER COLUMN circulating_supply TYPE NUMERIC(100,8);

COMMIT;