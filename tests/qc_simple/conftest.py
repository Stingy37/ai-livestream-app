import sys
from pathlib import Path

# Put src/ on the path so tests can write "from qc.simple.ner import ..."
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
