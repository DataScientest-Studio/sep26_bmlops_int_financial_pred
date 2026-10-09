# Schedule (sep26 cohort)

Authoritative: the coach (forum post and introduction video). Coach: a deadline is a progress meeting, not a submission — he checks progress, answers questions and gives the next step; dates are flexible if needed; meetings are recorded, and links are posted in Slack. A phase may start early once the previous one is done.

| Phase | Deadline 2026 | Content (detail: `course-checklist.md`) |
|---|---|---|
| 0 Kick-off | before Oct 9 | watch kick-off recording; questions in Slack; team agrees on organisation, target application and a roadmap before building |
| 1 Foundations | Oct 12, coach meeting 12:00 | objectives + metrics, reproducible env, DB + one-time load script, baseline model (`training.py`, `predict.py`), API (`training/`, `predict/`) |
| 2 Microservices, tracking, versioning | Oct 22 | MLflow tracking + registry + best-model tagging, docker-compose microservices, scheduled retraining, DVC (no Git) hashes in MLflow; optional tests, CI/CD, auth, Kubernetes |
| 3 Monitoring & maintenance | Nov 16 | Evidently drift in Airflow, prediction logging, Prometheus/Grafana + alerts + webhook retrain, Streamlit, docs |
| Defense | Nov 17–18 (coach); sheet: Mon or Tue (Nov 16–17) | 15 min presentation + 5 min demo + 10 min Q&A (sheet: 20 min presentation with live demo + 10 min Q&A) |

## Communication
- Slack channel is the primary channel; coach replies within ~24 h. Older messages: Slack "Pins".
- A meeting time that does not suit → tell the coach in Slack; he moves it.
- Unable to attend a meeting → send questions beforehand.
- Mentoring calls (kick-off deck): ≤1 h on Zoom/Teams, regular. Each member in turn presents: tasks done, successes/blockers, remaining backlog. Coach may set group or individual goals. Whole team owns the backlog.

## Cohort calendar (SEP26 sprint sheet)
Generic course calendar; where it differs from the coach's dates above, the coach's dates apply.
- Mentoring calls: framing Oct 1; phase calls Oct 5, 9, 16, 23, 30, Nov 5; **mock defense Nov 12**.
- Masterclasses: Oct 1 MLOps overview; Oct 9 API security and regulation; Oct 23 monitoring and observability; Nov 5 cloud MLOps. Q&A sessions Oct 7 and Oct 20, 12:00–13:00.
- Sprints and mandatory modules: 1 (from Sep 21) Linux & Bash, Docker; 2 (from Oct 2) MLflow, DVC & DagsHub, Nginx; 3 (from Oct 12) Airflow, BentoML (optional: SQL, MongoDB); 4 (from Oct 26) drift monitoring, Prometheus & Grafana; 5 (from Nov 6) Kubernetes. ≥8 of 10 mandatory modules required to pass the training.
- End of training Thu Nov 19; jury sessions Nov 24 and Dec 1.

## Mismatched phase models (do not mix up)
- Coach: 3 phases + kick-off (above).
- SEP26 sheet: 4 phases (Phase 1 Oct 2–5, Phase 2 Oct 6–19, Phase 3 Oct 20–Nov 2, Phase 4 Nov 3–19).
- Kick-off deck: 4 phases (1 Foundations, 2 Microservices/tracking/versioning, 3 Orchestration & deployment, 4 Monitoring & scalability); bootcamp 40 days = 10 days each. Coach phase 2 ≈ deck 2+3; coach phase 3 ≈ deck 4.
