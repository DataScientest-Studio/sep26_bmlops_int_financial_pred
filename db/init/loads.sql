-- Creates the loads table where it is missing: in the project database at each
-- start of the services, in the replay database and each test database when created.
-- One row per security: the time its latest load fetched it, replaced by each load.
CREATE TABLE IF NOT EXISTS loads (
    symbol      text        NOT NULL,
    fetched_at  timestamptz NOT NULL,
    PRIMARY KEY (symbol)
);
