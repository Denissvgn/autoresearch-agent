# Autoresearch Agent Workspace

You are running inside the autoresearch-agent Docker container.
Your job is to autonomously tune ML models by following the SKILL.md instructions.

## Rules

- All paths are relative to `/app/workspace/`
- Python: always use `/app/workspace/.venv/bin/python` (never system python)
- ML services are reachable via Docker network:
  - MLflow Tracking: http://mlflow:5000
  - Data Ingest: http://data-ingest:8000
  - Ensemble Trainer: http://ensemble-trainer:8000
  - RL Trainer: http://rl-trainer:8000
  - Feature Service: http://feature-service:8000
- NEVER write outside `/app/workspace/` except during config promotion
- Use `scripts/autotuner/setup.py` to initialize workspaces
- Use `scripts/autotuner/{model}/prepare.py` to run experiments
- Use `scripts/autotuner/promote.py` to promote winning configs

## Iteration Output Protocol

After **each** experiment iteration, output a JSON line in exactly this format:

```
ITERATION_RESULT: {"iteration": N, "primary_metric": X.XXXX, "metric_name": "...", "all_gates_passed": true|false, "decision": "keep|discard|crash", "description": "brief change description", "training_time_s": NNN.N}
```

The orchestrator monitors your output for these `ITERATION_RESULT:` markers
to track progress and broadcast updates to the web UI.

## Experiment Loop

1. Run `setup.py` to create the workspace (if not already done)
2. Read the model's README.md for strategy guidance
3. Establish a baseline by running the current config as-is
4. For each iteration:
   - Read `train.yaml` and `results.tsv`
   - Form a hypothesis (change ONE parameter at a time)
   - Edit `train.yaml`
   - Run `prepare.py --config <path>/train.yaml`
   - Parse the output metrics
   - If improved AND gates passed: keep → copy to `best_train.yaml`
   - Otherwise: revert `train.yaml` from `best_train.yaml`
   - Output the `ITERATION_RESULT:` marker
5. Stop when improvements plateau (3 consecutive < 0.5% improvement)

## Environment

- S3 endpoint: http://minio:9000 (via AWS_ACCESS_KEY_ID/SECRET)
- MLflow artifacts: s3://mlflow-artifacts
- Shared feature library: v2.1.0 (93 features)
