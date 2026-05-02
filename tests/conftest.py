from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
