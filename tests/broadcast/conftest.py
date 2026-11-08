"""Make ``src/`` importable, the same way ``python src/main.py`` does."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
