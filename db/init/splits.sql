-- Creates the splits table where it is missing: in the project database at each
-- start of the services, in the replay database and each test database when created.
CREATE TABLE IF NOT EXISTS splits (
    symbol  text    NOT NULL,
    day     date    NOT NULL,
    ratio   numeric NOT NULL,
    PRIMARY KEY (symbol, day)
);
