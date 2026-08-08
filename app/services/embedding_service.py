# app/services/embedding_service.py
"""
Embedding service.

Wraps the Phase 2 fine-tuned sentence-transformers model. Responsible for:
  - loading the model once and reusing it (loading is slow — ~1-2s minimum,
    more on CPU — so this must NOT happen per-request)
  - converting course text into the exact input format used during training
  - producing embedding vectors for storage in the pgvector `embedding`
    column on Course

Used by:
  - scripts/backfill_course_embeddings.py (Phase 3, next step) — embeds all
    existing seeded courses
  - the course creation/update path on the main backend integration (Phase 4)
  - the content-based recommendation query builder (Phase 3, later step) —
    embeds a query string the same way before searching pgvector
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Loads the fine-tuned model from disk and caches it for the lifetime of
    the process. lru_cache(maxsize=1) with no arguments is a simple way to
    get "load once, reuse forever" without a separate global variable and
    manual None-check — the first call loads it, every call after returns
    the cached instance.

    Raises FileNotFoundError with a clear message if the model folder isn't
    where settings expects it, since a silent fallback to the un-fine-tuned
    base model would produce working-but-wrong embeddings that are hard to
    debug later.
    """
    settings = get_settings()
    model_path = settings.EMBEDDING_MODEL_PATH

    try:
        return SentenceTransformer(model_path)
    except (OSError, FileNotFoundError) as e:
        raise FileNotFoundError(
            f"Fine-tuned embedding model not found at '{model_path}'. "
            f"Download fine_tuned_course_embedder.zip from the Colab notebook, "
            f"unzip it to that path, and confirm EMBEDDING_MODEL_PATH in your "
            f".env points to it."
        ) from e


def build_course_text(title: str, description: str) -> str:
    """
    Builds the exact text format the model was trained on. Must stay in
    sync with `course_text()` in the Colab notebook (Cell 6) — if this
    format ever changes, the model needs to be re-fine-tuned to match, or
    embeddings generated before/after the change won't be comparable.
    """
    return f"{title}. {description}"


def embed_text(text: str) -> list[float]:
    """
    Embeds a single string. Used both for course text and, later, for
    embedding a free-text search/recommendation query the same way courses
    were embedded — comparing embeddings only makes sense if both sides
    went through the identical model and input format.
    """
    model = get_embedding_model()
    # .tolist() converts the numpy array output to a plain Python list,
    # which is what pgvector's SQLAlchemy Vector type expects for storage.
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Batch version — encodes many strings in one forward pass, which is
    significantly faster than calling embed_text() in a loop when embedding
    many courses at once (e.g. the Phase 3 backfill script, or bulk
    re-embedding jobs later).
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()