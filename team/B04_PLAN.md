# B04 preparation and main compatibility — 25/11/2026

## Frozen-model residual/action/phase diagnostic — 26/11/2026

Authorized next task while Kaggle scores independently. Source base main b041343;
new branch codex/b04-diagnostics-20261126. Read the same five FINAL v2.1 PDFs.

- Hypothesis: Ridge's MAE/RMSE tradeoff can be localized to explicit sensor-delta,
  temperature-band and zone slices; observed action coverage may limit transfer.
  This is descriptive diagnosis, not a new model/control-gain hypothesis.
- Inputs fixed: six verified B03 episodes, original B04 ridge.npz/report hashes.
  Train1/2/4, validation5/7, generated0500 already-seen development evidence.
  No refit/tuning/scaler changes, new rollouts or frozen holdout access.
- Reproduce per-building persistence/Ridge metrics to1e-10 before interpreting.
  Report all rows; primary metrics MAE/bias and per-zone deltas, secondary RMSE,
  p90/p99 error and fraction of squared/absolute error from |delta|>1K and>5K.
- Fixed slices: current sensor below/inside/above band; |delta|<=0.1,0.1–1,>1K;
  first12steps vs rest. Do not drop tails or relabel observed sensor as latent state.
- Action bins fixed[-1,-0.5,0,0.5,1], unique values rounded4decimals, switch
  tolerance1e-6, low-switch<1% and constant std<=1e-12; report range-edge occupancy. Native VAV
  readback at obs[t+1] vs command[t-lag], lag0/1/2; report unmodified values and
  ventilation-floor explanation from source. No selecting a lag for new features.
- Command/target Pearson at past lags0/1/2/3: null for constant/short inputs,
  sample counts explicit, no cross-episode concatenation, no p-value/causal claim.
- Train-only feature min/max support bounds used diagnostically; |z|>3 from
  original train-only scaler. These are support flags, not validated OOD detector.
- Decision: if reproduced metrics mismatch, STOP. If generated MAE worsens or
  action/support limitations persist, keep Ridge offline/B05 off. Identify next
  validation-led change; no hyperparameter sweep or model choice using generated.
- Budget600s process wall, one numerical thread, episode-at-a-time memory.
  Unique output, hashes before/after, measured wall/CPU, immutable raw receipts;
  export only small portable checks/report and plots, update one existing notebook.
- Verification: hand-calculated metric/lag/coverage negative tests, integration
  on fixed artifacts, full suite, fresh-source tests, independent technical review.
- Follow-up after first diagnostic: source-default damper floor0.1 is checked as
  an explicit fixed hypothesis against readback (not fitted or used to change
  features/actions). Preserve first run; revised diagnostic uses a new output ID.

## Authorized continuation / delivery — 26/11/2026

User now explicitly authorizes publishing and merging verified, appropriate B work.
This supersedes prior no-push/PR/merge session notes. It does not approve a final
Base, Kaggle submission, holdout opening or enabling B05.

- Canonical delivery workspace is now the native Work checkout on
  `feature/B-delivery-20261126`, initially based on main `3dd6b3a`.
- Preserve both prior checkouts and every historical run. Bring B files into Work;
  no moves/deletions in the old directories. Reuse environment and corpus locally.
- Complete the nine missing DEV-SMALL full jobs: Singapore, Atlanta, Denver ×
  pid/pid_water/member_a. Reuse six already successful matched-source cases.
  One simulator worker/thread; total new wall budget 5400s. Per-job timeout uses
  measured B03 runtime with 50% headroom plus 60s, minimum 600s. Stop on failure;
  incomplete runs never yield a suite score. Keep HEAD pinned during these jobs.
- Add strict source/config/steps/duplicate validation to assemble a suite from
  independent successful receipts; TDD on invalid and incomplete inputs.
- Export only portable small evidence and code/docs/tests. Keep simulator outputs,
  datasets, model binaries, internal machine paths and holdout assets outside Git.
- Fresh full tests + independent whole-branch technical review, inspect staged
  diff, then commit/push/PR/merge using expected head SHA if checks permit. Do not
  bypass a protected branch or fabricate human G1 signoff.

## Historical scope and experiment design — 25/11/2026

The no-push/no-merge restriction in this historical scope was superseded by the
26/11 authorization above. Original experiment budgets and receipts remain unchanged.

Approved scope at that time: preserve B01–B03, validate against main 3dd6b3a, then prepare
persistence and Ridge delta-temperature forecasting. No B05 controller, push,
merge, Kaggle submission or holdout access.

1. Copy B sources into an isolated checkout of new main; reuse the existing
Python environment and read the original immutable B03 corpus by absolute path.
2. Run existing tests, B01 audit and full offline corpus validation. Record source
identity: simulator unchanged between 78d8b62 and 3dd6b3a; A adds only team files.
3. Write negative tests for future-feature leakage and train-only preprocessing.
Fit a fixed alpha=1 Ridge after persistence, using metadata-mapped zone features.
Keep train / validation / generated-dev buildings separate; no tuning on generated-dev.
4. Save offline coefficients/scaler in NPZ, feature contract, hashes, predictions,
MAE/RMSE per building/zone and plots. Use every valid row; report masks explicitly.
No claim that forecast accuracy proves a control improvement.
5. Compare pid / pid_water / member_a sequentially through existing run_batch.
288-step smoke first, then full 8640-step cold and hot cases; total benchmark wall
budget 2400 seconds, per job maximum 600 seconds, one worker and one BLAS thread.
This deliberately small diagnostic does not select a final base or yield a suite score.
Advance to five-climate DEV-SMALL and generated-dev before a base recommendation.

Hypotheses: Ridge reduces unseen-building sensor-delta MAE relative to zero-delta
persistence; A's paired full-episode loss improves on pid_water across both selected
climates. Freeze features and alpha before running. If validation MAE fails to improve,
retain persistence and study phase/large tails before adding model complexity.

Rulings: retain existing B folder layout documented in team/README.md; no mass move.
Native workspace creation did not return promptly, so use a separate local clone
inside the authorized project directory. Existing original checkout is preserved.
Dataset/environment junctions only reuse existing materials; outputs stay in this clone.
