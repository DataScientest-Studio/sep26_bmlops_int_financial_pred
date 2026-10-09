-- Runs once, when the container starts with an empty data volume.
CREATE TABLE prices (
    symbol text    NOT NULL,
    day    date    NOT NULL,
    open   numeric NOT NULL,
    high   numeric NOT NULL,
    low    numeric NOT NULL,
    close  numeric NOT NULL,
    volume bigint  NOT NULL,
    PRIMARY KEY (symbol, day)
);
