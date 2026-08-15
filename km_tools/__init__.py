from .store import store_fuente_externa, batch_store_fuentes_externas
from .search import search_fuentes_externas, get_sector_corpus, get_paper_full_text, get_ficha_full_text

__all__ = [
    "store_fuente_externa",
    "batch_store_fuentes_externas",
    "search_fuentes_externas",
    "get_sector_corpus",
    "get_paper_full_text",
    "get_ficha_full_text",
]
