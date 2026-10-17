# StartupGo search

Natural-language startup search with [LightRAG](https://github.com/HKUDS/LightRAG) and NVIDIA's
free hosted models. Two parts:

| | File | Does |
|---|---|---|
| **ProcessStorage** | `startup_search/process_storage.py` | Reads the StartupGo database (and the agent's entries) and turns it into LightRAG's vector and graph storage. Run: `uv run process-storage` |
| **StartupSearch** | `startup_search/search.py` | What the Backend calls: a user query in, matched startups out |

## Interface for the Backend

```python
from startup_search import StartupSearch

search = StartupSearch()                                # settings from Search/config.toml
matches = await search.search("seaweed packaging startups")
await search.close()                                    # on shutdown
```

`matches` is a list of `StartupMatch`, best first:

| Field | |
|---|---|
| `slug` | StartupGo database slug (`None` if only an agent entry knows the startup) |
| `entry` | agent entry id, if there is one |
| `name`, `website` | |
| `info` | startup info saved by ProcessStorage: tagline, sector, country, city, stage (database); TRL, BRL, ocean impact readiness, investment score, confidence (agent entry) |
| `relevance` | 0–1, relative to the best match |
| `matched` | knowledge-graph entities that led to it, e.g. `("Seaweed", "Packaging")` |
| `documents` | the matched documents, e.g. `("startup:notpla", "entry:notpla-com")` |

The storage opens on the first search, so the Backend starts without a key or processed storage.
After `process-storage` writes new storage, the next search loads it; no restart is needed. Errors are
`SearchUnavailable` (no key, nothing processed yet; the Backend answers 503) and `SearchError`
(model or network failure; 502). `POST /api/startups/search` in the Backend adds each database
startup's full summary.

## ProcessStorage

```
database rows / agent entries -> one text document per startup        (documents.py)
  -> chunks -> entities + relations extracted by the chat model -> GraphDB (knowledge graph)
  -> embeddings of chunks, entities and relations              -> VectorDB
```

- **Documents.** For a database startup: name, tagline, description, sector, location, stage,
  founding year, KTH readiness levels, ocean-impact evidence and funding rounds. For an agent entry:
  every extracted fact and the agent's scores. Preview them without model calls:
  `uv run startup-search documents`.
- An agent entry whose website matches a database startup is found as that startup.
- Only new and changed documents are processed, since each costs a few chat-model calls. Startups that
  left the database are removed (`--keep-removed` keeps them). Run it again after the database or
  the agent's entries change.

Document ids are also LightRAG's `file_path`s (`startup:<slug>`, `entry:<agent id>`), so every
retrieved entity and chunk leads back to its startup.

## Search

Search uses LightRAG's retrieval (`aquery_data`) and doesn't generate an answer. In `mix` mode the
chat model picks keywords from the query, then entities, relations and text chunks are retrieved
from the graph and the vectors. A startup's score sums its best position in each of the three lists
(reciprocal-rank fusion), so long documents don't win just by having more entities. Repeated queries
are answered from memory.

## Storage

LightRAG's four storages are local files in `rag_storage/` for now; no database server is needed:

| Storage | Class | Holds |
|---|---|---|
| kv | `JsonKVStorage` | documents, chunks, entity/relation records, model-answer cache |
| vector | `NanoVectorDBStorage` | embeddings of chunks, entities and relations (`vdb_*.json`) |
| graph | `NetworkXStorage` | the knowledge graph (`graph_chunk_entity_relation.graphml`) |
| doc_status | `JsonDocStatusStorage` | processing state of each document |

`rag_storage/startupgo_documents.json` records what ProcessStorage processed: each document's text
digest and its startup info. A graph or vector database can replace these later: change the class
names in `[storage]` and run `process-storage` again. Searches never write to the storage, so the
Backend can search while `process-storage` runs.

## Models

Two models, both on NVIDIA's hosted API (OpenAI-compatible) by default. `.env` sets which models
and their keys; `config.toml` (`[chat]`, `[embedding]`) sets how they are called.

| `.env` | Default | Used for |
|---|---|---|
| `CHAT_MODEL`, `CHAT_API_KEY` | `nvidia/nemotron-3.5-lightning-30b-a3b` | process-storage: entities and relations from every chunk; search: keywords from each query |
| `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`, `EMBEDDING_DIM` | `nvidia/llama-3.2-nv-embedqa-1b-v1`, `2048` | process-storage: chunks, entities and relations; search: each query |

A model left unset in `.env` uses the default; environment variables override `.env`. Keys are free at
build.nvidia.com, and one NVIDIA key can be used for both.

Why these models:

- **Chat:** LightRAG recommends a fast model with thinking off for extraction and for query
  keywords. This 30B MoE model is in the class LightRAG names as the minimum. Thinking is off
  (`[chat] reasoning = false`, sent as `chat_template_kwargs.enable_thinking`): with it on, one call
  took ~27 s in our test. For a richer graph, `nvidia/nemotron-3-super-120b-a12b` is slower but stronger.
- **Embedding:** a retrieval model with separate query and passage modes that takes inputs up to 8192
  tokens, so LightRAG's ~1200-token chunks fit.
- **Not used:** LightRAG's answer-writing and image models, because the search only retrieves. No
  reranker: NVIDIA's rerankers aren't on the OpenAI-compatible endpoint.

The embedding model is fixed once storage exists. A new `EMBEDDING_MODEL` or `EMBEDDING_DIM` needs new
storage: delete `rag_storage/` and run `process-storage`. `uv run startup-search check` makes one
small call to each model and prints the embedding size the model really returns.

## Setup and use

From `Modules/` (one uv workspace for every module):

```bash
uv sync --all-packages
cp Search/.env.example Search/.env        # then add CHAT_API_KEY and EMBEDDING_API_KEY

cd Search
uv run startup-search documents                      # what will be processed (no model calls)
uv run startup-search documents --id startup:notpla  # one document's text
uv run startup-search check                          # each model answers; embedding size matches
uv run process-storage                               # database -> vector + graph storage
uv run startup-search query "seaweed packaging replacing plastic"
```

LightRAG itself is a library dependency of this package (`lightrag-hku==1.5.7`). A
`uv tool install "lightrag-hku[api]"` installs the LightRAG Server (`lightrag-server`) in its own
isolated environment, which this code can't import from. The version is pinned to the same 1.5.7
so both read the same storage format.

## Tests

```bash
cd Modules/Search && uv run pytest
```

The tests use fake models. One runs the real LightRAG pipeline end to end: ProcessStorage writes the
graph and vector files, then StartupSearch finds the startups in them.
