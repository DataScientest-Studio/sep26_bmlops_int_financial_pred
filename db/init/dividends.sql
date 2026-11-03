-- Creates the dividends table where it is missing: in the project database at each
-- start of the services, in the replay database and each test database when created.
CREATE TABLE IF NOT EXISTS dividends (
    symbol      text    NOT NULL,
    day         date    NOT NULL,
    amount      numeric NOT NULL,
    currency    text    NOT NULL,
    PRIMARY KEY (symbol, day)
);
