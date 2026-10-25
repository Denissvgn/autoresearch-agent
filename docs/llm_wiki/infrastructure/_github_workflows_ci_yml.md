# GitHub Actions: CI

**Path:** `.github/workflows/ci.yml`
**Type:** `github_actions`

## Triggers

- `push`
- `pull_request`
- `workflow_dispatch`

## Jobs

| Job | Display Name | Runs On | Needs | Steps |
|---|---|---|---|---:|
| `test` | `Lint and Test` | `ubuntu-latest` | — | 17 |
| `smoke` | `Docker Smoke` | `ubuntu-latest` | — | 2 |
| `distributed` | `Distributed (Postgres)` | `ubuntu-latest` | — | 6 |
| `ui` | `UI Build` | `ubuntu-latest` | — | 7 |
| `qualification-gates` | `Qualification Gates` | `ubuntu-latest` | — | 7 |
| `live-qualification` | `Live Qualification (opt-in)` | `ubuntu-latest` | — | 7 |

### test

- `Checkout repository` - uses `actions/checkout@v7`
- `Set up Python` - uses `actions/setup-python@v7`
- `Install sandbox prerequisites (bubblewrap + userns)` - runs `sudo apt-get update sudo apt-get install -y --no-install-recommends bubblewrap sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 \|\| true`
- `Install Poetry` - runs `python -m pip install --upgrade pip pip install poetry`
- `Install dependencies` - runs `poetry config virtualenvs.in-project true poetry install --no-interaction --no-ansi --no-root`
- `Poetry metadata check` - runs `poetry check`
- `Lockfile check` - runs `poetry check --lock`
- `Build release archives` - runs `# Poison local-only directories so archive checks catch broad includes. trap 'rm -rf skills/_drafts/ci-sentinel skills/ci-unbundled' EXIT mkdir -p skills/_drafts/ci-sentinel skills/ci-unbundled printf 'not a release asset\n' > skills/_drafts/ci-sentinel/SKILL.yaml printf 'not a release asset\n' > skills/ci-unbundled/SKILL.yaml poetry build --output "$RUNNER_TEMP/release-dist"`
- `Check release archive contents` - runs `poetry run pytest tests/test_packaging.py -q`
- `Smoke test installed wheel outside checkout` - runs `python -m venv "$RUNNER_TEMP/wheel-smoke-venv" "$RUNNER_TEMP/wheel-smoke-venv/bin/python" -m pip install "$RUNNER_TEMP"/release-dist/*.whl mkdir -p "$RUNNER_TEMP/wheel-smoke-cwd" cd "$RUNNER_TEMP/wheel-smoke-cwd" "$RUNNER_TEMP/wheel-smoke-venv/bin/python" -I - <<'PY' import sysconfig from pathlib import Path from src.core.skill_registry import DEFAULT_SKILLS_ROOT, SkillRegistry site_packages = Path(sysconfig.get_path("purelib")).resolve() assert DEFAULT_SKILLS_ROOT == site_packages / "skills", DEFAULT_SKILLS_ROOT registry = SkillRegistry() expected = {"code-refactor", "db-config-tuning", "prompt-engineering"} assert set(registry.discover()) == expected for skill_id in expected: assert registry.get(skill_id).id == skill_id for asset in ("SKILL.yaml", "SKILL.md", "bootstrap.py", "eval/run.py"): assert (DEFAULT_SKILLS_ROOT / skill_id / asset).is_file() print("Installed wheel discovers and loads all bundled skills") PY`
- `Domain-coupling guard` - runs `python scripts/check_domain_coupling.py`
- `Referenced-doc integrity guard` - runs `python scripts/check_doc_references.py`
- `Legacy-vocabulary branching guard` - runs `python scripts/check_legacy_vocab_branching.py`
- `Ruff` - runs `poetry run ruff check --config pyproject.toml src tests --output-format=github`
- `Mypy` - runs `poetry run mypy src --no-error-summary`
- `Non-ML session e2e` - runs `poetry run pytest tests/test_non_ml_session_e2e.py -q`
- `Pytest` - runs `poetry run pytest tests -q`

### smoke

- `Checkout repository` - uses `actions/checkout@v7`
- `Smoke test the built image` - runs `scripts/smoke_docker.sh`

### distributed

- `Checkout repository` - uses `actions/checkout@v7`
- `Set up Python` - uses `actions/setup-python@v7`
- `Install sandbox prerequisites (bubblewrap + userns)` - runs `sudo apt-get update sudo apt-get install -y --no-install-recommends bubblewrap sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 \|\| true`
- `Install Poetry` - runs `python -m pip install --upgrade pip pip install poetry`
- `Install dependencies` - runs `poetry config virtualenvs.in-project true poetry install --no-interaction --no-ansi --no-root`
- `Pytest (postgres + distributed markers)` - runs `poetry run pytest -m "postgres or distributed" -vv`

### ui

- `Checkout repository` - uses `actions/checkout@v7`
- `Set up Node` - uses `actions/setup-node@v7`
- `Install dependencies` - runs `npm ci --ignore-scripts`
- `Typecheck` - runs `npx --no-install tsc --noEmit --types vitest/globals,@testing-library/jest-dom`
- `Vitest` - runs `npm run test:unit -- --pool=forks --maxWorkers=1 --minWorkers=1 --no-file-parallelism`
- `Build` - runs `npx vite build`
- `Production ops tests` - runs `node scripts/run-production-ops-tests.mjs`

### qualification-gates

- `Checkout repository` - uses `actions/checkout@v7`
- `Set up Python` - uses `actions/setup-python@v7`
- `Install sandbox prerequisites (bubblewrap + userns)` - runs `sudo apt-get update sudo apt-get install -y --no-install-recommends bubblewrap sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 \|\| true`
- `Install Poetry` - runs `python -m pip install --upgrade pip pip install poetry`
- `Install dependencies` - runs `poetry config virtualenvs.in-project true poetry install --no-interaction --no-ansi --no-root`
- `Run qualification gates` - runs `poetry run python scripts/ci_qualification_gates.py`
- `Archive sanitized gate evidence` - uses `actions/upload-artifact@v7`

### live-qualification

- `Checkout repository` - uses `actions/checkout@v7`
- `Set up Python` - uses `actions/setup-python@v7`
- `Install sandbox prerequisites (bubblewrap + userns)` - runs `sudo apt-get update sudo apt-get install -y --no-install-recommends bubblewrap sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 \|\| true`
- `Install Poetry` - runs `python -m pip install --upgrade pip pip install poetry`
- `Install dependencies` - runs `poetry config virtualenvs.in-project true poetry install --no-interaction --no-ansi --no-root`
- `Run live qualification gates` - runs `poetry run python scripts/ci_qualification_gates.py --live --gate live-external`
- `Archive sanitized live evidence` - uses `actions/upload-artifact@v7`

## Notes

_Add reviewed operational context here; generated sections are replaced from source observations._
