-- Example queries on the prices table; they only read.

-- Latest day and number of days stored per security.
SELECT symbol, max(day) AS latest_day, count(*) AS days
FROM prices
GROUP BY symbol
ORDER BY symbol;

-- The five most recent days of one security (on real prices: 'AAPL.US').
SELECT day, open, high, low, close, volume
FROM prices
WHERE symbol = 'AAPL.SAMPLE'
ORDER BY day DESC
LIMIT 5;

-- Change of the close from the previous stored day, per security.
SELECT symbol, day, close,
       close - lag(close) OVER (PARTITION BY symbol ORDER BY day) AS change
FROM prices
ORDER BY symbol, day;
