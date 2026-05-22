from .semantic_scholar import search_literature
from .pubmed import search_pubmed          # mantenido como fallback / referencia
from .uniprot import get_protein_sequence
from .esmfold import predict_structure
from .stability import analyze_stability
from .variants import design_variants
from .compare import compare_variants

__all__ = [
    "search_literature",
    "search_pubmed",
    "get_protein_sequence",
    "predict_structure",
    "analyze_stability",
    "design_variants",
    "compare_variants",
]
