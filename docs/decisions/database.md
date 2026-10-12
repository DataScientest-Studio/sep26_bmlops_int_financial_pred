# Database choice — PostgreSQL or NoSQL

Decision: PostgreSQL, confirmed by the coach (as presented: sep26_bmlops_int_financial_pred @ Mon Oct 12, 2026 12pm - 12:30pm (CEST); listed in [`plan.md`, "Decisions"](../plan.md#decisions)). The course allows either ("a SQL or NoSQL DB", `references/architecture.md`); its reference pipeline chart shows PostgreSQL.

## What the database has to hold
- **Prices:** per security and trading day: open, high, low, close, volume. Fixed columns, one row per (security, day). Size: 30 securities × 25 years × ~252 trading days ≈ 190,000 rows — small.
- **Predictions:** every forecast with its input features, the model version and the time it was made (required in phase 3, read by the drift check).
- **Actual outcomes:** the next day's real price change, to measure how good the forecasts were in production (level 3).

## What the services will ask of it
- Price history of one security for a date range (training, app chart).
- Latest trading day per security (daily ingestion: what is missing?).
- Load a day again without creating duplicates (historical replay, re-runs).
- Predictions next to the actual outcome of the same security and day (production performance).
- Recent predictions vs. a reference period (drift check with Evidently).

## PostgreSQL
Pros:
- The data is a table by nature: fixed columns, one row per security and day.
- A primary key on (security, day) rules out duplicates; re-loading a day is a single "insert or update".
- Predictions vs. actual outcomes is a join on security and day, done by the database.
- Date-range queries and "latest day per security" are short, standard SQL.
- MLflow (runs, model registry) and Airflow (its own bookkeeping) both need an SQL database anyway. One PostgreSQL server can hold all three as separate databases — one engine to run, back up and learn.
- Built for many clients at once: API, ingestion, Airflow, MLflow and the app all connect to the same server and write at the same time.
- Strict data types (`date`, `numeric`, `timestamp`): bad data is rejected on insert instead of being stored silently.
- pandas reads query results directly into a DataFrame (`read_sql`), which is what training and Evidently consume.
- Ad-hoc questions about the product later ("which securities had the largest errors last month?") need no new code.

Cons:
- The schema is fixed: adding a column needs a change to the table. Mitigation: store the prediction features in one JSON column (PostgreSQL `jsonb`), so a new feature needs no table change.
- The team has to write SQL or use a library for it (SQLAlchemy).
- Runs as a server: one more Compose service, with a data volume and a user and password from the environment.

## NoSQL (e.g. MongoDB)
Pros:
- No fixed schema: a prediction document can carry whatever features the current model uses.
- Raw API responses (yfinance, Stooq) could be stored as they arrive.
- Scales across machines — irrelevant at this data size.

Cons:
- Predictions vs. actual outcomes has to be joined in Python or with an aggregation pipeline.
- Duplicate protection and data types have to be set up explicitly (unique index, validation) instead of coming with the table.
- A second database engine in the stack, next to the PostgreSQL server MLflow and Airflow still need.
- The flexibility it offers is little use here: the price data has fixed columns, and the variable part (features) is covered by a JSON column in PostgreSQL.

## Note on SQLite
SQLite is probably not a good option: it is a single file without a server, while we want one server to serve several databases (project data, MLflow, Airflow) to several services at once. Concurrent writers to one SQLite file wait on each other's lock, and Airflow does not support SQLite outside development.

## Decision
PostgreSQL, one container, with separate databases for the project data, MLflow and Airflow. Prices as a table keyed by (security, day); predictions as a table with the features in a `jsonb` column; actual outcomes joined by security and day.
