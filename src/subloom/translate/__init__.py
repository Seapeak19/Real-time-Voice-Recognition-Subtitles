"""Translation backends."""

from .cloud import CloudTranslator
from .nllb import (
    NLLB_LICENSE,
    NLLB_SIZE_HINT,
    NLLBTranslator,
    download_local_model,
    local_model_available,
)
from .service import Readiness, TranslationService

__all__ = [
    "CloudTranslator",
    "NLLBTranslator",
    "NLLB_LICENSE",
    "NLLB_SIZE_HINT",
    "Readiness",
    "TranslationService",
    "download_local_model",
    "local_model_available",
]
