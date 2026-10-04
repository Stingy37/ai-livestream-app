"""RAG team. Public interface: ``Retriever`` (see the Team Interface Contract).

Splitting, clustering, and query decomposition are internal — restructure them freely.
"""

from rag.retrieval import Retriever

__all__ = ["Retriever"]
