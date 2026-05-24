import logging

from app.config import settings

logger = logging.getLogger(__name__)

SEED_INCIDENTS: list[dict[str, str]] = [
    {
        "id": "past-inc-2026-03-12",
        "error_signature": "Redis connection timeout cache eviction OOM memory pressure",
        "resolution": (
            "March 12 Outage: payment-api Redis cache saturation caused 503 errors. "
            "Solved by clearing Redis cache and scaling cache cluster from 2 to 4 nodes."
        ),
    },
    {
        "id": "past-inc-2026-01-05",
        "error_signature": "database connection pool exhausted HikariCP timeout thread limit",
        "resolution": (
            "Jan 05 Outage: payment-api connection pool exhaustion after aggressive pool "
            "downsizing. Solved by expanding DB pool max_connections from 10 back to 50 "
            "and reverting timeout from 2s to 30s."
        ),
    },
]


class IncidentRAGService:
    def __init__(self) -> None:
        self._collection = None
        self._client = None
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._client = chromadb.PersistentClient(
                path=settings.chroma_db_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name="incident_resolutions",
                metadata={"description": "Historical SRE incident resolutions"},
            )
            self._seed_if_empty()
        except Exception as exc:
            logger.warning("ChromaDB unavailable, using in-memory keyword RAG only: %s", exc)
            self._client = None
            self._collection = None

    def _seed_if_empty(self) -> None:
        if self._collection is None:
            return
        try:
            count = self._collection.count()
        except Exception as exc:
            logger.warning("ChromaDB count failed, re-seeding: %s", exc)
            count = 0

        if count > 0:
            return

        documents = [item["resolution"] for item in SEED_INCIDENTS]
        ids = [item["id"] for item in SEED_INCIDENTS]
        metadatas = [
            {"error_signature": item["error_signature"]} for item in SEED_INCIDENTS
        ]
        self._collection.add(documents=documents, ids=ids, metadatas=metadatas)
        logger.info("Seeded %d past incidents into ChromaDB RAG store", len(ids))

    def search_past_incidents(self, current_error_message: str) -> str:
        if not current_error_message or not current_error_message.strip():
            return "No historical incident context available."

        if self._collection is None:
            return self._keyword_fallback(current_error_message)

        try:
            count = self._collection.count()
            if count == 0:
                return self._keyword_fallback(current_error_message)

            results = self._collection.query(
                query_texts=[current_error_message],
                n_results=min(2, count),
            )
            documents = results.get("documents", [[]])
            if not documents or not documents[0]:
                return self._keyword_fallback(current_error_message)

            lines = [
                f"  {index + 1}. {doc}"
                for index, doc in enumerate(documents[0])
            ]
            return "Relevant past incident resolutions:\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("ChromaDB query failed, using keyword fallback: %s", exc)
            return self._keyword_fallback(current_error_message)

    def _keyword_fallback(self, current_error_message: str) -> str:
        query_lower = current_error_message.lower()
        matches: list[str] = []
        for item in SEED_INCIDENTS:
            signature_tokens = item["error_signature"].lower().split()
            if any(token in query_lower for token in signature_tokens if len(token) > 4):
                matches.append(item["resolution"])

        if not matches:
            return "No closely matching historical incidents found in the knowledge base."

        return "Relevant past incident resolutions (keyword match):\n" + "\n".join(
            f"  {index + 1}. {match}" for index, match in enumerate(matches[:2])
        )

    def store_resolution(
        self,
        incident_id: str,
        error_signature: str,
        resolution_summary: str,
    ) -> None:
        if self._collection is None:
            logger.debug("Skipping RAG store — ChromaDB not available")
            return
        try:
            self._collection.upsert(
                ids=[incident_id],
                documents=[resolution_summary],
                metadatas=[{"error_signature": error_signature}],
            )
            logger.info("Stored resolution for incident %s in RAG index", incident_id)
        except Exception as exc:
            logger.warning("Failed to store resolution in RAG index: %s", exc)
