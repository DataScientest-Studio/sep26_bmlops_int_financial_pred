-- Creates the dividends table in each new database: the project database on the
-- container's first start, the replay database and each test database when created.
CREATE TABLE dividends (
    symbol      text    NOT NULL,
    day         date    NOT NULL,
    amount      numeric NOT NULL,
    currency    text    NOT NULL,
    PRIMARY KEY (symbol, day)
);
