# Smart Buildings 2026 - Team Workflow

## Foundation
Official starter-kit baseline commit: 1fb7560.
Keep the official LICENSE and NOTICE.

## Git workflow
- main: stable integrated code.
- chore/*: project setup and maintenance.
- feature/a-zone: zone/VAV control.
- feature/b-data-ml: benchmark, data, ML, predictive control.
- feature/c-plant: AHU/HWS continuous optimization.
- Use Pull Requests to merge changes into main.

## Module ownership
- A: VAV continuous actions.
- B: AHU/HWS discrete actions.
- C: AHU/HWS continuous actions.
- Modules must preserve actions owned by other members.

## Evaluation
- Record commit SHA, scenario, configuration, and score.
- Compare changes against the same base and scenarios.
- Keep generated datasets and model artifacts outside Git.

## Safety
- Do not push secrets or competition holdout data.
- Do not directly modify upstream starter-kit code without review.
- Keep main runnable.
