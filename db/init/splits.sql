-- Runs once, when the container starts with an empty data volume.
CREATE TABLE splits (
    symbol  text    NOT NULL,
    day     date    NOT NULL,
    ratio   numeric NOT NULL,
    PRIMARY KEY (symbol, day)
);
