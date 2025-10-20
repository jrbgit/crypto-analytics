-- Migration: Increase consensus_mechanism column length
-- Issue: StringDataRightTruncation error when inserting consensus mechanism descriptions longer than 100 characters
-- Solution: Increase VARCHAR limit from 100 to 500 characters

ALTER TABLE link_content_analysis 
ALTER COLUMN consensus_mechanism TYPE VARCHAR(500);

-- Add comment to document the change
COMMENT ON COLUMN link_content_analysis.consensus_mechanism IS 'Consensus mechanism description (increased from 100 to 500 chars in migration 009)';