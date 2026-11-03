-- Creates the prices table where it is missing: in the project database at each
-- start of the services, in the replay database and each test database when created.
CREATE TABLE IF NOT EXISTS prices (
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
