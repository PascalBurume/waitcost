import os
import sys

# Make the repo root importable so `import model...`, `import agent...` resolve
# whether pytest is run from the repo root or elsewhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The engine is what we verify here, so pin the planner to the deterministic
# rule-based path by default. (Production default is `auto` = Gemma-first.) Tests
# that exercise the Gemma path set WAITCOST_PLANNER / monkeypatch Ollama explicitly.
os.environ.setdefault("WAITCOST_PLANNER", "rule")
