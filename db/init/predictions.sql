-- Creates the predictions table where it is missing: in the project database at each
-- start of the services, in the replay database and each test database when created.
-- One row per forecast.
CREATE TABLE IF NOT EXISTS predictions (
    id                bigint           GENERATED ALWAYS AS IDENTITY,
    symbol            text             NOT NULL,
    day               date             NOT NULL,
    change            double precision NOT NULL,
    model_version     text             NOT NULL,
    start_close       numeric          NOT NULL,
    start_fetched_at  timestamptz      NOT NULL,
    change_1          double precision NOT NULL,
    change_2          double precision NOT NULL,
    change_3          double precision NOT NULL,
    change_4          double precision NOT NULL,
    change_5          double precision NOT NULL,
    requested_at      timestamptz      NOT NULL,
    PRIMARY KEY (id)
);
