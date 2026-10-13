# Financial forecasting — project plan

Reference material: `references/` (index in `references/README.md`).

## Decisions
Settled. Basis: coach feedback, agreed, or built and in use. Longer explanations follow the table.

| Topic | Decision | Basis | Date | Details |
|---|---|---|---|---|
| Database | PostgreSQL; each member's database is private and filled only from EODHD with their own key | Coach feedback (PostgreSQL), agreed (private databases) | Oct 12, 2026 1) | [Database](#database), [`decisions/database.md`](decisions/database.md) |
| Environment | uv; `make setup` installs the locked packages | Coach feedback | Oct 12, 2026 1) | README, "Setup" |
| Team repo | the course repo `DataScientest-Studio/sep26_bmlops_int_financial_pred`, with this project's full history and its own structure | Coach feedback | Oct 12, 2026 1) | — |
| API access | optional, phase 2: HTTP basic authentication against a `users` table, passwords as bcrypt hashes, roles `user` and `admin` | Agreed | Oct 12, 2026 1) | [API access](#api-access), [`decisions/password-hashing.md`](decisions/password-hashing.md) |
| Trading calendar | the `exchange_calendars` package, wrapped in one module of the project | Built | Oct 12, 2026 1) | [`decisions/trading-calendar.md`](decisions/trading-calendar.md) |
| Test strategy | acceptance tests per requirement first, unit tests with the code; pytest with pytest-xdist | Built | Oct 12, 2026 1) | [Test strategy](#test-strategy) |
| Requirements | StrictDoc, top level only (~15–25); source `docs/requirements.sdoc`, `make requirements` regenerates `docs/requirements.md` after every change | Built | Oct 12, 2026 1) | — |
| Continuous integration | every push runs `make lint` and `make test` on GitHub | Built | Oct 12, 2026 1) | [Continuous integration](#continuous-integration) |
| Data source | EODHD, free tier (20 calls per day, 1 year of history); each member uses their own free key; `make load` fills a new database, `make update` adds the new trading days | Agreed | Oct 12, 2026 1) | [Data source](#data-source) |
| Close prices | prices stored as they printed; splits and dividends in tables of their own | Agreed | Oct 12, 2026 1) | [Close prices](#close-prices) |
| Package and login | Python package `forecasting`; development login `admin`/`admin` in `.env.example`, for local use only | Built | Oct 12, 2026 1) | — |

1\) As presented: sep26_bmlops_int_financial_pred @ Mon Oct 12, 2026 12pm - 12:30pm (CEST).

### Database
PostgreSQL, details in `decisions/database.md`. Each member runs their own private database, filled only from EODHD with their own key: `make load` once, `make update` every trading day. Price data never leaves a member's database and is never committed.

### API access
HTTP basic authentication against a `users` table in the project database (passwords stored as bcrypt hashes, see `decisions/password-hashing.md`; role `user` or `admin`). Users call `predict/`; admins also call `training/`, the model metrics and a few user-management endpoints (add, list, remove). The demo app logs in as a user. Builds on the course's API security exercise.

### Test strategy
requirements first. Each requirement names how it is checked: Test, Demonstration or Inspection (`requirements.md`, "How requirements are checked"). For every requirement checked by Test, black-box acceptance tests are written before the code (TDD); the share of passing acceptance tests is the progress indicator (`make acceptance`). Below them: unit tests for the pure functions (features, target, no look-ahead, baselines, metrics, trading calendar), API tests with swapped-in parts, and integration tests against a throwaway database with a small fixed price set. Each pytest-xdist worker gets its own test database; tests never use a cloud service or real e-mail, and never the network, with one exception: the contract tests of the data source (`make contract`) call EODHD with the member's own key from `.env`, to notice when EODHD changes how it delivers data. They are not part of `make test` or CI, and each check the key's history, remaining calls or plan cannot support is skipped with its reason. No model-quality thresholds: tests check that the comparison with the baselines is computed, not that the model wins. Acceptance tests of phase 1 are in `tests/acceptance/`; those of phases 2 and 3 are written when each phase starts.

### Continuous integration
every push runs the style and type checks and the unit tests on GitHub (`.github/workflows/ci.yaml`, the same `make lint` and `make test` as on our machines); a failed run emails the person who pushed. `main` in the course repo refuses deletion and force pushes; once code review starts, changes reach it only through a pull request with green checks (see "Code review" in Open). Nightly runs: later, if needed.

### Data source
EODHD, free tier: 20 calls per day and 1 year of history; each request costs one call per security. Prices, splits and dividends all come from EODHD; daily prices cover exchanges worldwide, market indices included. Each member signs up for their own free key and keeps it in their own `.env` (`EODHD_API_KEY`). `make load` loads each security without stored prices from a configured first day (`HISTORY_START`), as far back as the plan allows; `make update` fetches for each security only the days from its latest stored one on, so each run moves little data. Each request costs one call however many days it covers. How the daily calls are spent: "Daily call budget" in Open.

EODHD's daily prices include the current day while its session is still running (delayed by about 15 minutes), in the same form as a finished day. How such a row is handled: "Provisional closes" in "Decision proposals".

### Close prices
the database stores prices as they printed — open, high, low, close and volume as traded that day. Splits (ratio) and dividends (amount actually paid, currency) are stored as events in tables of their own; the model's inputs correct prices and volumes for them when the inputs are built. EODHD delivers volume already corrected for each split it has applied; a split it lists for a day after the last delivered day is not yet applied. The load reverses the correction with the split ratios it fetches in the same run (each day's volume divided by the ratios of all later splits up to the last delivered day). When on a split's own day EODHD applies it is unchecked (see "Split on the day of a load" in Open). EODHD keeps closes as printed and multiplies the volume before a split by its ratio; the splits API delivers each ratio as text, for example `4.000000/1.000000`.

## Decision proposals
To be decided by the team.
- Scope: level 1 complete (full chain, persistence + mean-change baselines, historical replay, trading calendar), with several securities held in the SQL database from the start, plus the level 3 parts the course requires (prediction logging, drift checks, triggered retraining, keep-the-better-model rule). Level 2 items only after the chain runs end to end; cheapest first: simple sliding-window backtest.
  Alternatives:
  - Level 1 + course-required level 3 parts, level 2 later (proposed): covers every course checklist item with the least model work; the evaluation stays simple until the chain runs.
  - Level 1 only: least work, but misses parts the phase 3 checklist requires (prediction logging, drift checks, triggered retraining) — not viable for the course.
  - Level 1 + full level 2 from the start (several dozen securities, one global model vs. one per security, sliding-window backtest, prediction intervals): stronger evaluation, but it is model work, which is not graded, and it delays the end-to-end chain.
  - Full level 3 (telling volatile markets apart from model degradation, monitoring per security or sector): goes beyond what the course asks; only if time is left.
- First model: at most 1–2 days of model work (coach), then on to the MLOps parts. Proposal: Ridge regression (scikit-learn) predicting the next-day change, always scored next to the two required baselines (persistence: predicted change 0; historical mean change). Features from the price history only: changes of the last 1–5 days, 5- and 20-day volatility, volume change. Metrics: MAE, skill against persistence, directional accuracy, on days after the training period. Candidates with pros and cons: `decisions/regressors.md`. Owner: Scheima, who decides.
- Build budget: ~2 weeks of focused work; chain first (one rough version of every stage end to end), polish after.
  Alternatives:
  - Chain first, polish after (proposed): a working end-to-end system exists early, so integration problems show up early and there is always something to demo; early versions are rough.
  - Stage by stage, each finished before the next starts: every part is polished when done, but the chain is complete only at the end, integration problems appear late, and a delay leaves an incomplete system at the defense.
  - Follow the course phase deadlines only, without an own budget: matches the coach's checkpoints, but phase 3 (monitoring, retraining, app, docs) gets the least time before the defense.
- Secured entry point (phase 3, after the required phase 3 items; the kick-off deck lists "Secured APIs" and "light scalability" for phase 3, the coach lists API security as optional): Nginx in front of the API and the demo app as the only published entry point, with HTTPS (self-signed certificate, since the system runs locally), rate limits on `predict/` and `training/`, and requests spread over several API instances.
  Alternatives:
  - Nginx in front (proposed): encrypts the basic-auth password on the way, stops request floods and shows simple scaling, all with one component; one more service and a certificate to manage.
  - HTTPS in the API server itself (uvicorn): encryption only; no rate limits or scaling, and each service needs its own certificate.
  - Access control only (REQ-SVC-004), no encryption: no extra work; enough while everything runs on one machine (REQ-CON-002), but the password travels readable over any network.
- Demo app: the app the jury sees at the defense; it calls the model API, and the presentation can run inside it. Any technology is accepted.
  Alternatives:
  - Streamlit (proposed): pure Python, as in the course material and past group projects; quick to build, with charts included.
  - Small web app (an HTML page served by FastAPI): no extra framework; layout and charts are written by hand.
  - Gradio: as quick as Streamlit, but aimed at a single model demo; weaker for pages with price history and model metrics.
- Reference securities: six stocks that behave differently, plus two market indices as reference series (`config/securities.toml`). The indices are loaded like the stocks but are never a forecast target; whether the model uses their recent changes as inputs is part of "First model". Each request covers one symbol and one kind of data (EODHD's requests for a whole exchange cost 100 calls). A load costs three calls per stock (prices, splits, dividends) and one per index (no splits or dividends): 20 calls, the free tier's daily limit. A daily update costs the same when events are checked every day, 8 when only prices are fetched; a fetch during a running session does not fit beside a full daily update (see "Daily call budget" in Open).

  | Security | Exchange | Why |
  |---|---|---|
  | Apple (AAPL) | XNAS | very large technology company, medium volatility |
  | Tesla (TSLA) | XNAS | high volatility: does the model beat "no change" on noisy prices? |
  | JPMorgan Chase (JPM) | XNYS | bank, reacts to interest rates |
  | Exxon Mobil (XOM) | XNYS | energy, follows oil prices rather than technology |
  | Coca-Cola (KO) | XNYS | defensive, low volatility |
  | SAP (SAP) | XETR | second exchange with its own holidays, prices in euro |
  | S&P 500 index | XNYS | market trend of the US stocks |
  | DAX index | XETR | market trend of the German stock |

  Alternatives:
  - Six stocks and two indices (proposed): covers different volatility levels, sectors and two exchange calendars; the market trend is available to the model; the first load uses the whole daily limit.
  - Four stocks and two indices: 14 calls per full load or update, leaving 6 for a fetch during the session; fewer kinds of behaviour.
  - Six stocks, no indices: no market trend for the model; two calls fewer per day.
  - Exchange-traded funds instead of indices (SPY for the S&P 500, EXS1 for the DAX): traded like stocks, but they pay dividends, so each costs three calls on the first load.
- Provisional closes: during a running session the latest price stands in for the close. Each stored row carries the time it was fetched; a row is final once it was fetched a set delay after its exchange's close (trading calendar, early closes included; the delay covers EODHD's 15 minutes and the closing auction, for example 20 minutes, and is a setting). A later fetch replaces a provisional row and never a final one. Training uses final rows only; a forecast may start from a provisional close and then says so: the response gives the close it starts from and when that price was fetched. `make update` runs once a day at any time; a run during a session stores that day as provisional, and the next day's run replaces it with the final close.
  Alternatives:
  - Provisional rows with fetch time, replaced until final (proposed): a forecast is available during the session and the stored close is corrected by the next run; one more column and an update rule instead of insert-only.
  - Store only finished sessions (rows of a running session are dropped): simplest, insert-only; forecasts only after the close.
  - Store EODHD's rows as delivered: a price from mid-session stays in the database as the close, because a stored day is never replaced.

## Roadmap — proposal
To be agreed by the team. Team setup and areas: `docs/team.md`.

Target application, as the jury sees it at the defense: a demo app that calls the model API (see "Demo app" in "Decision proposals").
- Pick a security; see its next-day forecast with the model version, next to both baselines; the "not investment advice" notice always visible.
- A history chart of past forecasts against the actual outcomes.
- A status panel: latest stored quote, latest training run, current production model, latest drift check.

Live demo: replay advances the simulated calendar by a few trading days and the chain runs on its own — new quotes are loaded, predictions logged, drift checked, the model retrained and promoted if it is better — visible in the app, MLflow and Grafana.

| Period | Milestone | Content |
|---|---|---|
| until Mon Oct 12 (coach meeting 12:00) | Foundations: a clone plus `make` gives a database with history, a trained baseline and an API answering `predict/` | "Phase 1 plan" below; roadmap and team setup agreed |
| Oct 13–22 (coach meeting) | Chain runs end to end: one replayed day goes from new quotes through training and promotion to the API serving the new model | MLflow tracking and registry, "better model" rule, Docker Compose services (database, API, MLflow, Airflow), Airflow DAGs for ingestion and training, replay and trading calendar, DVC snapshots with hashes in MLflow |
| Oct 23–Nov 6 | Closed loop and monitoring | prediction log and outcome collection, Evidently drift DAGs (training and prediction side), Prometheus and Grafana with alerts and the retraining webhook, first demo app version |
| Nov 7–11 | Feature freeze Nov 11 | tests, README and API docs, check from a fresh clone, demo script |
| Thu Nov 12 | Mock defense call | full demo as at the defense |
| Nov 13–16 | Polish and rehearse | fixes from the mock defense, presentation (slides or in the demo app), 1–2 rehearsals with equal speaking time |

Level 2 items (more securities, backtesting) start only if the chain is complete by Nov 6.

## Phase 1 plan — foundations by Mon Oct 12
Proposal for the team. Coach meeting Mon Oct 12, 12:00 (invite sent; a time that does not suit is moved on request in Slack).

Goal: a teammate runs `git clone` and a handful of `make` commands and gets a running database with price history, a trained baseline model, and an API answering `predict/`.

| # | Item | Done when | Depends on |
|---|---|---|---|
| 0 | Team meeting (before Oct 12) | roadmap draft and organisational setup agreed (see Open); database, data source and securities decided; objectives and key metrics (draft in `docs/requirements.sdoc`) confirmed | — |
| 1 | Repo ready and shared | team has write access; own repo structure (coach feedback, see [Decisions](#decisions), note 1); template README replaced; `.gitignore` and `.env.example` in place; CI passes (see "Continuous integration") | 0 |
| 2 | Reproducible environment | `pyproject.toml`, `uv.lock`, `.python-version`; Makefile targets `setup`, `db`, `load`, `update`, `train`, `predict`, `api`, `test`; works from a fresh clone | 1 |
| 3 | PostgreSQL | Compose file with only the database (exact image tag, data volume, credentials from `.env`); table `prices` keyed by (security, day) | 2 |
| 4 | One-time load script | loads the history of the agreed securities; a re-run creates no duplicates; API key read from `.env` | 3, data source |
| 5 | Baseline training pipeline | a training function reads prices from the database, builds the target (next-day change), trains, compares with the persistence and mean-change baselines, saves the model to a gitignored folder; a prediction function returns the next-day forecast for one security; one file or two (see Open) | 3 (4 for real data) |
| 6 | Initial API endpoints | FastAPI with `training/` (runs training) and `predict/` (security in; forecast and model version out) | 5 |
| 7 | Minimum tests and docs | unit tests (pytest, run in parallel with pytest-xdist) for feature building and both endpoints; README section "Setup from a fresh clone" | 2–6 |

Repo sharing (item 1): every member works with their own GitHub account; access is granted to the accounts, never shared. Each member brings their GitHub username to the meeting.
- Team repo: the course repo `DataScientest-Studio/sep26_bmlops_int_financial_pred`, holding this project's full history. Members get write access by invitation from an admin of the repo.
- "Changes only through reviewed pull requests" is enforced by a ruleset on `main`; GitHub enforces it because the course repo is public.

Interfaces to agree at the meeting, so items 3–6 can be built in parallel:
- Table: `prices(symbol, day, open, high, low, close, volume, fetched_at)`, primary key (symbol, day); `fetched_at` is the time the row was fetched (UTC), see "Provisional closes".
- Tables: `splits(symbol, day, ratio)` and `dividends(symbol, day, amount, currency)`, primary key (symbol, day) each.
- Functions: `train() -> model_version`, `predict(symbol) -> forecast`.
- API: request and response of `training/` and `predict/`.

Split: by area (data, model, service), see `docs/team.md`.

In Phase 1 the model is saved as a plain file; MLflow follows in Phase 2 (see "Roadmap — proposal").

## Open
- Roadmap: proposal in "Roadmap — proposal", to be agreed by the team before building (coach). Input still to review: the coach's previous group repos (`references/README.md`, past learner projects).
- Organisational setup: proposal in `docs/team.md` (areas and owners, meetings, communication, work tracking, reviews), to be agreed by the team.
- Local operation or a live cloud database (REQ-CON-002): decided by the team once the foundation runs (load, training, prediction, API). Every member's pipeline needs an up-to-date database during development. Options: each member runs their own database and loads from the data source; a shared development database on a team member's NAS, reached over Tailscale; a live database on a small rented cloud server (for example, AWS). REQ-CON-002 (no cloud service) changes if the team chooses a cloud database.
- Daily call budget (phase 2, daily ingestion): one setting per member and key, the calls per day the EODHD plan allows (`calls_per_day`, 20 on the free plan). Proposal: each day the prices come first, one call per security; the calls left check splits and dividends, the securities checked longest ago first, so the rhythm follows the number of securities (6 securities on the free plan: daily; 16: about every 8 days). Market indices take one price call each and have no events; every fetch during a running session (see "Provisional closes") costs one more price call per security and index. Calls used are counted in the database across runs and reset at 00:00 UTC, when EODHD's day turns; a spent budget stops requests until then, and the run reports what it left out; more securities than calls per day is refused at start. Alternative: a fixed "check events every N days" setting beside the budget — simpler, but re-tuned by hand whenever the securities change, and nothing stops a combination that exceeds the budget. Either way, a split noticed late leaves the newest model input wrong until it is fetched.
- Split on the day of a load: when on the split's own day EODHD corrects the earlier volumes (before the session opens, during it, or only after the close) is unchecked. The load undoes a split once that day is delivered; if EODHD corrects at another time, a load on that day stores the earlier volumes multiplied or divided by the split's ratio, and they stay so. Check: on a split day, fetch the security before the open, during the session and after the close, and compare the previous day's volume with the one fetched the evening before.
- Data to trade on: which securities and how much history the model learns from (`HISTORY_START`, default 1980-01-02, the earliest day the trading calendar covers). German prices from before Xetra (1997) follow the old Frankfurt floor's holidays, which the Xetra calendar describes slightly differently: a few days a year are counted as missing or rejected. To be decided by the team.
- Objectives and key metrics: draft in `docs/requirements.sdoc`, to be confirmed by the team; main metric and the "better model" rule still to be defined.
- Training and prediction code: one file or two (the coach accepts either). Proposal: separate modules for training, prediction and evaluation (`src/forecasting/`), as in the course scaffold and the past group projects.
- Code review: GitHub pull requests, once the foundation is built; until then changes go straight to `main`. How strict (one approval required, or the author merges after green checks) and the reviewer ring (`docs/team.md`) are decided then.
- Defense date: the coach says Nov 17 or 18, the SEP26 sheet says Monday or Tuesday (Nov 16 or 17); the sheet also lists a mock defense call on Nov 12. (Ask the coach.)
- `requirements.txt`: the course scaffold ships one (the classic pip package list) and its stub CI may install from it. The project environment is managed by uv (`pyproject.toml`, `uv.lock`). Drop `requirements.txt`, or keep it as a file generated from `uv.lock` (`uv export --format requirements-txt`) for anyone using plain pip? Generated, it must be regenerated after every package change.
