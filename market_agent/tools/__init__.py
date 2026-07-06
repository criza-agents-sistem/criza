import sys
from pathlib import Path

# criza/ (padre de market_agent/) tiene que estar en sys.path para 'utils.corpus' —
# no asumir que quien importa este paquete ya lo insertó (market_agent.py lo hace,
# pero un test que importe tools/ directamente no).
_CRIZA_DIR = Path(__file__).parent.parent.parent
if str(_CRIZA_DIR) not in sys.path:
    sys.path.insert(0, str(_CRIZA_DIR))

from .datosgobar import search_official_stats, search_series, get_series_values
from .web_fetch import fetch_page_text
from .email_draft import draft_outreach_email
from utils.corpus import buscar_corpus_cientifico

__all__ = [
    "search_official_stats",
    "search_series",
    "get_series_values",
    "fetch_page_text",
    "draft_outreach_email",
    "buscar_corpus_cientifico",
]
