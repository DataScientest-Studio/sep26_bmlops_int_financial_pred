-- Creates the splits table in each new database: the project database on the
-- container's first start, the replay database and each test database when created.
CREATE TABLE splits (
    symbol  text    NOT NULL,
    day     date    NOT NULL,
    ratio   numeric NOT NULL,
    PRIMARY KEY (symbol, day)
);
