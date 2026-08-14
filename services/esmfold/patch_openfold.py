"""
Parche de compatibilidad para openfold.

La imagen nvcr.io/nvidia/pytorch:23.06-py3 tiene APIs incompatibles y
no tiene los módulos CUDA compilados de openfold.

Parches aplicados a todos los archivos .py de openfold:
1. fa_is_installed = False (flash_attn API incompatible)
2. attn_core_inplace_cuda = None (CUDA ext no compilado)
"""

import sys
import subprocess
from pathlib import Path

BASE = Path("/usr/local/lib/python3.10/dist-packages/openfold")

if not BASE.exists():
    print(f"ERROR: {BASE} no existe.")
    sys.exit(1)

# ── Patches a aplicar en todos los .py ──────────────────────────────────────
PATCHES = [
    # Patch 1: deshabilitar flash_attn (API incompatible con imagen base, solo en latest main)
    (
        'fa_is_installed = importlib.util.find_spec("flash_attn") is not None',
        'fa_is_installed = False  # deshabilitado: API incompatible con imagen base'
    ),
    # Patch 2: hacer attn_core_inplace_cuda opcional (CUDA ext no compilado, solo en latest main)
    (
        'attn_core_inplace_cuda = importlib.import_module("attn_core_inplace_cuda")',
        (
            'try:\n'
            '    attn_core_inplace_cuda = importlib.import_module("attn_core_inplace_cuda")\n'
            'except ModuleNotFoundError:\n'
            '    attn_core_inplace_cuda = None  # CUDA ext no compilado — fallback a PyTorch'
        )
    ),
    # Patch 3: hacer pytorch_lightning opcional en callbacks.py (solo inferencia, no training)
    (
        'from pytorch_lightning.utilities import rank_zero_info',
        (
            'try:\n'
            '    from pytorch_lightning.utilities import rank_zero_info\n'
            'except (ImportError, ModuleNotFoundError):\n'
            '    def rank_zero_info(*args, **kwargs): pass  # training only'
        )
    ),
    (
        'import pytorch_lightning as pl',
        (
            'try:\n'
            '    import pytorch_lightning as pl\n'
            'except (ImportError, ModuleNotFoundError):\n'
            '    pl = None  # training only'
        )
    ),
    # Patch 4: hacer dllogger opcional (no está en PyPI, solo needed para training logging)
    (
        'import dllogger as logger',
        (
            'try:\n'
            '    import dllogger as logger\n'
            'except (ImportError, ModuleNotFoundError):\n'
            '    class _FakeDLLogger:\n'
            '        def __getattr__(self, name): return lambda *a, **kw: None\n'
            '    logger = _FakeDLLogger()  # dllogger no disponible — solo inferencia'
        )
    ),
    (
        'from dllogger import JSONStreamBackend, StdOutBackend, Verbosity',
        (
            'try:\n'
            '    from dllogger import JSONStreamBackend, StdOutBackend, Verbosity\n'
            'except (ImportError, ModuleNotFoundError):\n'
            '    class _Stub:\n'
            '        def __init__(self, *a, **kw): pass\n'
            '    JSONStreamBackend = StdOutBackend = _Stub\n'
            '    class Verbosity:\n'
            '        DEFAULT = WARNING = VERBOSE = 0\n'
            '    # dllogger no disponible — solo inferencia'
        )
    ),
]

patched_files = []
errors = []

for py_file in BASE.rglob("*.py"):
    content = py_file.read_text(encoding="utf-8", errors="replace")
    original = content
    for old, new in PATCHES:
        if old in content:
            content = content.replace(old, new)
    if content != original:
        py_file.write_text(content, encoding="utf-8")
        patched_files.append(py_file.name)

if patched_files:
    print(f"OK: parcheados {len(patched_files)} archivos: {patched_files}")
else:
    print("AVISO: ningún patrón encontrado — posiblemente ya parchado o estructura distinta")

# Limpiar .pyc
subprocess.run(
    ["find", str(BASE), "-name", "*.pyc", "-delete"],
    capture_output=True
)

print("Patch completado.")
