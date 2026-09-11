"""Path setup for HealthCom 2026 experiments."""
import sys
from pathlib import Path

# Add jsonld-ex library to path
_lib = Path(__file__).resolve().parents[3] / "jsonld-ex" / "packages" / "python" / "src"
if str(_lib) not in sys.path:
    sys.path.insert(0, str(_lib))

# Add experiments root to path
_exp = Path(__file__).resolve().parents[1]
if str(_exp) not in sys.path:
    sys.path.insert(0, str(_exp))
