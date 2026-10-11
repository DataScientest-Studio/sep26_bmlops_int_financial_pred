-- Removes the made-up prices of db/queries/sample-data.sql; real prices are kept.

DELETE FROM prices WHERE symbol LIKE '%.SAMPLE';
