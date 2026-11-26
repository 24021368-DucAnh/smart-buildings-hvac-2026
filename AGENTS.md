# Project working knowledge

Read `team/README.md`, `team/PROJECT_KNOWLEDGE.md`, and the task-specific plan
before changes. This repo extends the official Smart Buildings starter kit.
Preserve LICENSE/NOTICE and official simulator/reward/evaluator code.

- Keep evidence statuses explicit: VERIFIED, FAILED, INTERRUPTED, NOT RUN.
  A passed unit test is not a Kaggle submission or human G1 approval.
- Record source URL, revision, license and whether code is inherited, adapted,
  newly AI-assisted, or human-authored. Do not infer other members' AI usage.
- Record wall time and measured CPU separately. Person-hours remain unknown
  unless the member supplies a real work log. Never infer hours from commits.
- Use metadata for variable building dimensions. No hidden IDs/future sensors or
  simulator internals in inference features. Preprocessing/model fit is train-only.
- A owns VAV continuous; B owns data/evaluation and AHU/pump discrete; C owns
  plant continuous/composition/submission. Respect write ownership and flag-off
  identity. Research models are not enabled controllers by default.
- Smoke is 288 steps for workflow. Control scores require all declared scenarios
  at 8640 steps, exact membership, finite rewards and verified provenance.
- Start with one worker/thread, measure runtime, set a budget, preserve failed
  runs, never overwrite run IDs. Frozen holdout stays closed without team decision.
- Public Git contains portable code/docs/tests/small evidence. Keep datasets,
  model binaries, raw logs/receipts, secrets and internal machine paths local.
- Before delivery: meaningful tests, fresh-clone check without generated data,
  source/AI/time disclosure, independent technical review and staged diff review.
  Respect repository protection; never bypass required reviewers/checks.
- On 26/11/2026 the user explicitly authorized merging verified B work in this
  delivery. That authorization supersedes earlier session no-push notes; it does
  not authorize Kaggle submission, holdout opening or signing G1 for A/C.
- Update the project knowledge and portable evidence when a result/decision
  changes; preserve immutable historical receipts and distinguish superseded runs.
