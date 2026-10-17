"""StartupGo search: LightRAG over the startup database and agent entries, with NVIDIA-hosted models.

    StartupSearch    query -> matched startups (what the Backend calls)
    ProcessStorage   database -> LightRAG vector + graph storage (run: process-storage)
"""

from .config import SearchSettings
from .documents import Document, load_documents
from .errors import SearchError, SearchUnavailable
from .process_storage import ProcessReport, ProcessStorage
from .search import StartupMatch, StartupSearch

__all__ = [
    "Document",
    "ProcessReport",
    "ProcessStorage",
    "SearchError",
    "SearchSettings",
    "SearchUnavailable",
    "StartupMatch",
    "StartupSearch",
    "load_documents",
]
