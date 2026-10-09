# Team setup — proposal

To be agreed by the team. Roadmap and phase goals: `plan.md`, "Roadmap — proposal".

## Members
[team member A], [team member B], [team member C]; mentor: the course coach.

## Areas
Each member owns one area from phase 1 to the defense and presents it at the defense.

| Area | Owner | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|---|
| Data | [team member A, B, or C] | database, one-time load | daily ingestion, replay, trading calendar, DVC, ingestion DAG | prediction log tables, outcome collection |
| Model | [team member A, B, or C] | training and prediction functions, baselines | MLflow tracking and registry, promotion rule, training DAG | Evidently drift DAGs, triggered retraining |
| Service | [team member A, B, or C] | FastAPI, tests | Compose stack, API access (users and roles), CI (optional) | Prometheus and Grafana, alerts, Streamlit |

Shared by all: README and docs, the presentation, the interfaces between areas (agreed together, see `plan.md`).

Alternatives:
- By area (proposed): clear ownership and little collision in the same files; everyone has their own part to present. An area that runs late holds up the others.
- By phase: everyone works on the current phase together. Less waiting at the start, but members collide in the same files and nobody owns a part at the defense.
- In pairs with rotation: good for learning, but slower, and with three members one always works alone.

## Meetings
- Coach: Mon Oct 12 12:00, then around each phase deadline (Oct 22, Nov 16) and the mock defense call (Nov 12). A time that does not suit → tell the coach in Slack.
- Team: one of the two options below, at a fixed time. Each member says what they did, what comes next, and what blocks them; anything longer goes to a separate call with only the people it concerns.
  - Daily stand-up, 15 minutes: blockers surface within a day; costs a fixed slot every day.
  - Twice a week, 30 minutes: fewer interruptions next to the course modules; a blocker can wait up to three days unless raised in Slack.
- Everything else goes through Slack.

## Communication
| Slack channel | Members | Use |
|---|---|---|
| `sep26_bmlops_int_financial_pred` | team and mentor | questions to the coach, meeting links, progress for the coach |
| `mlops-project-financial-prediction - Team chat` | team | day-to-day coordination, review requests, blockers |

A decision made in a call or in Slack is written into `plan.md` or `decisions/` the same day; the Slack thread alone is not the record.

## Work tracking
GitHub Issues on a project board in the team repo: one issue per task, assigned to one member, one milestone per coach meeting (Oct 12, Oct 22, Nov 12, Nov 16).

Alternatives:
- GitHub Issues and project board (proposed): tasks sit next to the code and link to their pull requests; the jury sees the process in the repo.
- External board (Trello, Notion): familiar to many; tasks and code live apart, links kept by hand.
- Task list in Slack or a shared document: no setup; no assignment, history or link to the code.

## Code review
Every change goes through a pull request (rules in `plan.md`, "Decision proposals"). The reviewer is the next member in the ring: Data → Model → Service → Data. So every member also knows a second area.
