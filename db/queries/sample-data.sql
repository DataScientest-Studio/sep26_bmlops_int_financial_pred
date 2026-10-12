-- Made-up prices for trying the example queries; db/queries/remove-sample-data.sql removes them.
-- The suffix .SAMPLE keeps them apart from real prices, which are stored as AAPL.US and SAP.XETRA.
-- Rows that already exist are skipped, so the file can be run again.

INSERT INTO prices (symbol, day, open, high, low, close, volume, fetched_at) VALUES
    ('AAPL.SAMPLE', '2026-10-08', 254.10, 256.80, 253.40, 256.20, 41000000, '2026-10-08 20:30+00'),
    ('AAPL.SAMPLE', '2026-10-09', 256.30, 257.90, 252.70, 253.50, 38500000, '2026-10-09 20:30+00'),
    ('SAP.SAMPLE',  '2026-10-08', 231.40, 233.10, 230.20, 232.60, 1900000,  '2026-10-08 16:00+00'),
    ('SAP.SAMPLE',  '2026-10-09', 232.50, 234.00, 231.80, 233.70, 1750000,  '2026-10-09 16:00+00')
ON CONFLICT DO NOTHING;
