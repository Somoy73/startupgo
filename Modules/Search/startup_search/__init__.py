"""StartupGo search: LightRAG over the startup database and agent entries, with NVIDIA-hosted models.

    StartupSearch    query -> matched startups; startup or thesis -> N-hop subgraph (what the Backend calls)
    ProcessStorage   database -> LightRAG vector + graph storage (run: process-storage)
"""

from .config import SearchSettings
from .documents import Document, load_documents
from .errors import SearchError, SearchUnavailable
from .graph import GraphEdge, GraphNode, Subgraph
from .process_storage import ProcessReport, ProcessStorage
from .search import StartupMatch, StartupSearch

__all__ = [
    "Document",
    "GraphEdge",
    "GraphNode",
    "ProcessReport",
    "ProcessStorage",
    "SearchError",
    "SearchSettings",
    "SearchUnavailable",
    "StartupMatch",
    "StartupSearch",
    "Subgraph",
    "load_documents",
]
