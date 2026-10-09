# Project reference — index

Condensed from the course material. Read the topic file you need; go to the source only for detail not kept here. The course material itself is not in the repository (folder `course-material/`, gitignored); every learner has it from the course.

| File | Content |
|---|---|
| `subject.md` | Prediction task, difficulty levels, data sources, bibliography |
| `schedule.md` | Phases, deadlines, meetings, defense dates |
| `course-checklist.md` | What to build, per phase (checklist) |
| `architecture.md` | Reference pipelines, service components, tool options |
| `evaluation.md` | What is graded, README, defense format, review topics |
| `../docs/plan.md` | Plan: decisions taken, open points |

## Sources and precedence
Coach of the sep26 cohort: [coach]. "Coach" in these files refers to [coach] unless noted.

Precedence where sources conflict: coach (forum post, introduction video) > subject PDF > SEP26 sprint sheet > kick-off deck > generic DataScientest docs.

| Source | Path (local, gitignored) | Kind |
|---|---|---|
| Coach forum post (Slack) | pasted in chat; not on disk | cohort-specific, authoritative for dates and tasks |
| Coach introduction video (Oct 2) | `course-material/2026-10-02-project_introduction_[coach]_transcript.txt` | transcript; organisation, phase 1 scope, meeting dates, local-only constraint |
| Subject (project brief) | `course-material/mlops-project-financial-prediction_10_2026.pdf` | cohort-specific subject |
| Kick-off deck | `course-material/Kick-Off Projets MLOPS (EN).pdf` | generic MLOps project methodology (author: [template author], not our coach) |
| Pipeline charts | `course-material/training_pipeline.png`, `course-material/predict_pipeline.png` | **file names swapped**: `training_pipeline.png` shows prediction, `predict_pipeline.png` shows training |
| Sprint sheet | `course-material/SEP26 PP Bootcamp MLOps (EN).xlsx` | sep26 cohort calendar: sprints, modules, mentoring calls, masterclasses (summary in `schedule.md`) |
| Sprint workbook (outdated) | `course-material/JUL26 PP Bootcamp MLOps (EN).xlsx` | **JUL26 cohort**, superseded by the SEP26 sheet |
| Report methodology | `course-material/(EN) Projects_methodology_report.pdf` | generic DS report guide; no report required here |
| Defense methodology | `course-material/Projet_Soutenance_Méthodologie_DS_EN.pdf` | generic DS defense guide |
| ML Canvas | `course-material/template Machine Learning Canvas (v1.1).pdf` | blank template (Louis Dorard, ownml.co) |
| Course repo | `github.com/DataScientest-Studio/sep26_bmlops_int_financial_pred` | the team repo; cookiecutter scaffold (README copied from "movie_recommandation", which invites modifications; folders for data, notebooks, reports, `src/` per step; stub CI runs `pytest` with no tests → fails) |

## Online originals of the material
The Google links in the course point to the files under `course-material/`:
- Sprint planning (cohort sheet) → `course-material/SEP26 PP Bootcamp MLOps (EN).xlsx`
- Project guidelines (slides) → `course-material/Kick-Off Projets MLOPS (EN).pdf`
- MLOps model canvas (doc) → `course-material/template Machine Learning Canvas (v1.1).pdf`
- Report guidelines → `course-material/(EN) Projects_methodology_report.pdf`
- Defense guidelines → `course-material/Projet_Soutenance_Méthodologie_DS_EN.pdf`
- Archives of past reports and slides/Streamlit apps: Google Drive folders `1vJ89jQHGb5xNvXiomliUbVGiM77GZDQk` and `1q3fFLqENeoFD66BD6UP5eIJYcnJsag23`
- Kick-off Zoom recording: link + passcode in the Slack channel (not copied here).

## Example / template repos
- Templates by [template author] (kick-off deck author): `github.com/[template author username]/mlops_project_template`, `github.com/[template author username]/mlops-boiler-plate`
- Past learner projects (the coach's previous groups): `DataScientest-Studio/juin23_continu_mlops_pompiers`, `DataScientest-Studio/AVR24CMLOPS_Bird-Image-Recognition` (local clones in `course-material/reference-repos/`), `DataScientest-Studio/dec23_mlops_accidents`
- Streamlit gallery: `streamlit.io/gallery`; DataScientest Studio: `studio.datascientest.com`
