import sys
from pathlib import Path

# Put src/ on the path so tests can write "from scraper.fetch import ..."
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
