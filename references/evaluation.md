# Evaluation, deliverables, defense

## What is graded
- Only MLOps proficiency; model performance is not evaluated.
- No final report. The repo **README** is judged closely: visuals, clear structure, no spelling errors.
- Kick-off "control points": technical (code quality, docs, test coverage, performance); MLOps (automation, versioning, monitoring, maintenance); documentation (technical, process, API, maintenance guides).
- Kick-off "to succeed": functional ML pipeline, automated processes, monitored deployment, maintained system; clear tech docs, up-to-date processes, complete API docs, maintenance guides; MLOps understanding, best practices, collaboration, continuous improvement.
- Good practices (deck): version code/data/models, document decisions and features/parameters, test regularly, code review, validate data quality, track transformations and experiments, automate, monitor, plan maintenance. Collaboration: defined Git workflow, regular reviews, clear communication.

## Defense (Nov 17–18)
- Forum: 15 min presentation (project progress + chosen architecture) + 5 min live demo (app works) + 10 min Q&A with jury. **Every member speaks.**
- May be given entirely in Streamlit instead of slides.
- Generic guide (DS-oriented, 20 + 10 min, jury of 2–3, cohort may attend): subject/problem, data (volume, architecture), dataviz, preprocessing, models + results, best model analysis, conclusion tied to business issue, critique + outlook. Streamlit needs a PoC page relevant to the business.
- Tips: rehearse 1–2×; keep speaking time roughly equal; one person shares screen throughout; preload models (avoid long Streamlit loads); if something breaks, explain and move on; anyone may answer any question.

## ML Canvas (to frame objectives in phase 1)
Fields: prediction task (type, entity, outcomes, wait before observation) · decisions · value proposition (end-user, benefit, workflow) · data collection (initial set, continuous update, collection rate) · data sources · impact simulation (deployability, test data, cost of errors, fairness) · making predictions (real-time vs batch, latency) · building models (number of prod models, update cadence) · features (available at prediction time) · monitoring (value/impact metrics).
The forum's "MLOps model canvas" Google Doc link points to `course-material/template Machine Learning Canvas (v1.1).pdf`.

## Report methodology (generic, no report due)
Usable as a README/defense question list: context and objectives; data (sources, availability, volume, target, limits); preprocessing; problem type and main metric (why); models tried/selected; error analysis; difficulties (planning, data, skills, compute); results vs. benchmark; improvements; bibliography; appendices (Gantt, code-file description).
