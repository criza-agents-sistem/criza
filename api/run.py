"""
Runner de la API — CRIZA.

Uso:
  python run.py            # sirve en http://localhost:8000
"""

import sys
from pathlib import Path

_API_DIR = Path(__file__).parent
_CRIZA_DIR = _API_DIR.parent
sys.path.insert(0, str(_API_DIR))
if str(_CRIZA_DIR) not in sys.path:
    sys.path.insert(0, str(_CRIZA_DIR))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, app_dir=str(_API_DIR))
