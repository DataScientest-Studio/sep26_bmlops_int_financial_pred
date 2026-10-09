# Requirements per phase (checklist)

Source: coach forum post (authoritative) + kick-off deck (adds tests/docs emphasis). `(opt)` = optional per coach.

## Phase 1 — Foundations (Oct 12)
- [ ] Project objectives and key metrics defined (ML Canvas, see `evaluation.md`)
- [ ] Reproducible dev environment (deck: think Docker from the start)
- [ ] Database (SQL or NoSQL); data stored by a one-time Python load script
- [ ] Baseline model built and evaluated: `training.py`, `predict.py`
- [ ] Inference API with endpoints `training/` and `predict/`
- Deck adds: Git code versioning, unit tests of main pipeline step functions, initial documentation.

## Phase 2 — Microservices, tracking, versioning (Oct 22)
- [ ] MLflow logging in the training script
- [ ] Data and model versioning via MLflow Model Registry
- [ ] Compare each new run with the previous model; tag the best (end of training script, or later in Airflow per training chart)
- [ ] Split into Docker microservices; orchestrate with docker-compose
- [ ] Scheduled training: cron, or Jenkins/Airflow (recommended, more complex)
- [ ] DVC **without Git** versions datasets; dataset hashes stored in MLflow
- [ ] (opt) Unit tests — a few cases, enough for CI
- [ ] (opt) GitHub Actions: `ci.yaml` (always: lint + tests + build images); `release.yaml` (master only: lint + tests + build & push images to Docker Hub)
- [ ] (opt) API security: Basic auth or OAuth2
- [ ] (opt) Kubernetes scalability
- Deck adds (its phase 3): rollback strategy, light scalability, API optimisation.

## Phase 3 — Monitoring & maintenance (Nov 16)
- [ ] Evidently drift detection **inside the Airflow pipeline**
  - Training side: reference = historical dataset, current = recent dataset; log report + metrics to MLflow; retrain if needed
  - Prediction side: store every prediction with its features in the DB; scheduled DAG checks drift; log report + metrics to MLflow; trigger training DAG if needed
- [ ] API performance monitoring with Prometheus + Grafana; alerts defined; Grafana built-in webhook triggers training
- [ ] Streamlit app to call the API and make predictions (may host the whole defense)
- [ ] Repo technical documentation finished (README graded, see `evaluation.md`)
- Deck adds: data-quality checks, system health checks, model/component update procedures.

## Subject-specific (from `subject.md`)
- [ ] Baselines (persistence, mean change) from the start; every model compared to them
- [ ] "Not investment advice" notice in the app
- [ ] Replay of historical data to simulate daily arrivals
- [ ] Trading-calendar handling
