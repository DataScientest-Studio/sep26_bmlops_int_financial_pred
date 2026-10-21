-- Creates the prices table in each new database: the project database on the
-- container's first start, the replay database and each test database when created.
CREATE TABLE prices (
    symbol      text        NOT NULL,
    day         date        NOT NULL,
    open        numeric     NOT NULL,
    high        numeric     NOT NULL,
    low         numeric     NOT NULL,
    close       numeric     NOT NULL,
    volume      bigint      NOT NULL,
    fetched_at  timestamptz NOT NULL,
    PRIMARY KEY (symbol, day)
);
