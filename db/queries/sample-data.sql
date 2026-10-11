-- Made-up prices for trying the example queries; db/queries/remove-sample-data.sql removes them.
-- The suffix .SAMPLE keeps them apart from real prices, which are stored as AAPL and SAP.
-- Rows that already exist are skipped, so the file can be run again.

INSERT INTO prices (symbol, day, open, high, low, close, volume) VALUES
    ('AAPL.SAMPLE', '2026-10-08', 254.10, 256.80, 253.40, 256.20, 41000000),
    ('AAPL.SAMPLE', '2026-10-09', 256.30, 257.90, 252.70, 253.50, 38500000),
    ('SAP.SAMPLE',  '2026-10-08', 231.40, 233.10, 230.20, 232.60, 1900000),
    ('SAP.SAMPLE',  '2026-10-09', 232.50, 234.00, 231.80, 233.70, 1750000)
ON CONFLICT DO NOTHING;
