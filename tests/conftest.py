import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# isolated DB and no network for tests
os.environ["MEZON_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["MEZON_LLM_OFFLINE"] = "1"
