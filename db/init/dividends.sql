-- Runs once, when the container starts with an empty data volume.
CREATE TABLE dividends (
    symbol      text    NOT NULL,
    day         date    NOT NULL,
    amount      numeric NOT NULL,
    currency    text    NOT NULL,
    PRIMARY KEY (symbol, day)
);
