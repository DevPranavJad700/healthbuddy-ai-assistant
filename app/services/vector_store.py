"""
Vector Store Service — ChromaDB operations for document storage and retrieval.

Handles:
- Collection management
- Document embedding and storage
- Similarity search
- Document deletion
"""

from pathlib import Path
from typing import Optional

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import settings
from app.core.logging_config import logger


class VectorStoreService:
    """Manages the vector store for document retrieval (supports ChromaDB and PGVector)."""

    def __init__(self):
        self._embeddings = None
        self._vectorstore = None
        self._client = None
        self._store_type = "chroma"
        self._initialized = False

    def initialize(self):
        """Initialize the embedding model and vector store."""
        if self._initialized:
            return

        logger.info("Initializing vector store...")

        # Initialize embedding model
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        self._embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        desired_type = getattr(settings, "vector_store_type", "chroma").lower()
        use_pgvector = (
            desired_type == "pgvector"
            and settings.effective_database_url.startswith("postgresql")
        )

        if use_pgvector:
            try:
                from langchain_community.vectorstores import PGVector

                self._store_type = "pgvector"
                self._vectorstore = PGVector(
                    connection_string=settings.effective_database_url,
                    embedding_function=self._embeddings,
                    collection_name=settings.pgvector_collection_name,
                )
                self._initialized = True
                logger.info(
                    f"PGVector store initialized "
                    f"(collection: {settings.pgvector_collection_name})"
                )
                return
            except Exception as e:
                logger.warning(
                    f"Failed to initialize PGVector ({e}). "
                    "Falling back to ChromaDB vector store."
                )

        # Fallback / Default: ChromaDB
        self._store_type = "chroma"
        db_path = Path(settings.chroma_db_path)
        db_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB persistent client
        self._client = chromadb.PersistentClient(path=str(db_path))

        # Initialize LangChain Chroma wrapper
        self._vectorstore = Chroma(
            client=self._client,
            collection_name=settings.chroma_collection_name,
            embedding_function=self._embeddings,
        )

        self._initialized = True
        logger.info(
            f"Chroma vector store initialized "
            f"(collection: {settings.chroma_collection_name}, "
            f"path: {db_path})"
        )

    def reload(self):
        """Force re-initialization of vector store and Chroma collection handle."""
        logger.info("Reloading vector store connection...")
        self._vectorstore = None
        self._client = None
        self._initialized = False
        self.initialize()

    @property
    def vectorstore(self) -> Chroma:
        """Get the vector store instance."""
        if not self._initialized:
            self.initialize()
        return self._vectorstore

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """Get the embedding model."""
        if not self._initialized:
            self.initialize()
        return self._embeddings

    def add_documents(self, documents: list[Document]) -> list[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of LangChain Document objects with metadata.

        Returns:
            List of document IDs.
        """
        if not documents:
            return []

        logger.info(f"Adding {len(documents)} documents to vector store")
        ids = self.vectorstore.add_documents(documents)
        logger.info(f"Successfully added {len(ids)} documents")
        return ids

    def similarity_search(
        self,
        query: str,
        k: int | None = None,
        score_threshold: float = 0.3,
    ) -> list[Document]:
        """
        Search for similar documents.

        Args:
            query: Search query text.
            k: Number of results to return.
            score_threshold: Minimum similarity score (0-1).

        Returns:
            List of relevant Document objects.
        """
        if k is None:
            k = settings.max_retrieval_results

        # Use distance scores and convert to bounded relevance to avoid model-specific warnings.
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=k)
        except Exception as e:
            err_msg = str(e).lower()
            if "not found" in err_msg or "does not exist" in err_msg or "collection" in err_msg:
                logger.warning("Chroma collection missing or stale (%s). Reloading vector store...", e)
                self.reload()
                results = self.vectorstore.similarity_search_with_score(query, k=k)
            else:
                raise

        filtered = []
        for doc, distance in results:
            relevance = 1.0 / (1.0 + max(distance, 0.0))
            if relevance >= score_threshold:
                doc.metadata["relevance"] = round(relevance, 4)
                filtered.append(doc)

        logger.info(
            f"Search: '{query[:50]}...' -> "
            f"{len(filtered)}/{len(results)} results "
            f"(threshold: {score_threshold})"
        )
        return filtered

    def get_retriever(self, k: int | None = None):
        """Get a LangChain retriever for use in LCEL chains."""
        if k is None:
            k = settings.max_retrieval_results

        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k},
        )

    def similarity_search_with_language(
        self,
        query: str,
        k: int | None = None,
        score_threshold: float = 0.3,
        language: str | None = None,
    ) -> list[Document]:
        """
        Language-aware similarity search.

        When a language code ('hi', 'es', 'ar') is provided, retrieval
        first tries documents tagged with that language. If fewer than
        `min_hits` language-specific results are returned, it blends in
        English fallback results to ensure the user always gets context.

        Args:
            query: Search query text.
            k: Number of results to return.
            score_threshold: Minimum relevance threshold.
            language: ISO 639-1 code ('hi', 'es', 'ar', 'en', or None).
        """
        if k is None:
            k = settings.max_retrieval_results

        # No filtering needed for English or unset language
        if not language or language == "en":
            return self.similarity_search(query, k=k, score_threshold=score_threshold)

        # Step 1: Language-filtered search
        try:
            lang_results_raw = self.vectorstore.similarity_search_with_score(
                query,
                k=k,
                filter={"language": language},
            )
        except Exception as e:
            err_msg = str(e).lower()
            if "not found" in err_msg or "does not exist" in err_msg or "collection" in err_msg:
                logger.warning("Chroma collection missing or stale during lang search (%s). Reloading...", e)
                self.reload()
                try:
                    lang_results_raw = self.vectorstore.similarity_search_with_score(
                        query,
                        k=k,
                        filter={"language": language},
                    )
                except Exception as inner_e:
                    logger.warning("Language-filtered search failed after reload: %s", inner_e)
                    lang_results_raw = []
            else:
                logger.warning("Language-filtered search failed (%s), falling back: %s", language, e)
                lang_results_raw = []

        lang_results = []
        for doc, distance in lang_results_raw:
            relevance = 1.0 / (1.0 + max(distance, 0.0))
            if relevance >= score_threshold:
                doc.metadata["relevance"] = round(relevance, 4)
                lang_results.append(doc)

        MIN_HITS = 2
        if len(lang_results) >= MIN_HITS:
            logger.info(
                "Language search: lang=%s query='%s...' -> %d results",
                language, query[:40], len(lang_results),
            )
            return lang_results

        # Step 2: Fallback — blend English results for the gap
        english_k = max(1, k - len(lang_results))
        english_results = self.similarity_search(query, k=english_k, score_threshold=score_threshold)

        # Deduplicate by doc_id+chunk_index
        seen = {
            (d.metadata.get("doc_id"), d.metadata.get("chunk_index"))
            for d in lang_results
        }
        for doc in english_results:
            key = (doc.metadata.get("doc_id"), doc.metadata.get("chunk_index"))
            if key not in seen:
                lang_results.append(doc)
                seen.add(key)

        logger.info(
            "Language search (blended): lang=%s query='%s...' -> %d results (%d lang + %d EN fallback)",
            language, query[:40], len(lang_results[:k]),
            sum(1 for d in lang_results if d.metadata.get("language") == language),
            sum(1 for d in lang_results if d.metadata.get("language", "en") == "en"),
        )
        return lang_results[:k]

    @property
    def store_type(self) -> str:
        """Return the active vector store type ('chroma' or 'pgvector')."""
        return self._store_type

    def delete_by_doc_id(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document ID."""
        if self._store_type == "pgvector":
            try:
                from sqlalchemy import text
                from app.core.database import SessionLocal

                with SessionLocal() as db:
                    result = db.execute(
                        text("DELETE FROM langchain_pg_embedding WHERE cmetadata->>'doc_id' = :doc_id"),
                        {"doc_id": doc_id},
                    )
                    db.commit()
                    count = result.rowcount
                    logger.info(f"Deleted {count} chunks for doc_id: {doc_id} from pgvector")
                    return count
            except Exception as e:
                logger.error(f"Error deleting doc_id from pgvector: {e}")
                return 0

        # ChromaDB deletion
        collection = self._client.get_collection(settings.chroma_collection_name)

        # Get all documents with this doc_id
        results = collection.get(where={"doc_id": doc_id})

        if results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for doc_id: {doc_id}")
            return len(results["ids"])

        logger.warning(f"No chunks found for doc_id: {doc_id}")
        return 0

    def get_document_list(self) -> list[dict]:
        """Get list of all unique documents in the store."""
        if self._store_type == "pgvector":
            try:
                from sqlalchemy import text
                from app.core.database import SessionLocal

                with SessionLocal() as db:
                    rows = db.execute(
                        text("""
                            SELECT 
                                cmetadata->>'doc_id' as doc_id,
                                COALESCE(cmetadata->>'original_filename', cmetadata->>'filename', 'unknown') as filename,
                                COUNT(*) as num_chunks
                            FROM langchain_pg_embedding
                            WHERE cmetadata->>'doc_id' IS NOT NULL
                            GROUP BY cmetadata->>'doc_id', COALESCE(cmetadata->>'original_filename', cmetadata->>'filename', 'unknown')
                        """)
                    ).mappings().all()
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning(f"Failed to fetch document list from pgvector: {e}")
                return []

        try:
            collection = self._client.get_collection(settings.chroma_collection_name)
            all_docs = collection.get(include=["metadatas"])
        except Exception as e:
            err_msg = str(e).lower()
            if "not found" in err_msg or "does not exist" in err_msg or "collection" in err_msg:
                try:
                    logger.warning("Chroma collection missing/stale in get_document_list (%s). Reloading...", e)
                    self.reload()
                    collection = self._client.get_collection(settings.chroma_collection_name)
                    all_docs = collection.get(include=["metadatas"])
                except Exception:
                    return []
            else:
                return []

        # Group by doc_id
        doc_map = {}
        for metadata in all_docs["metadatas"]:
            doc_id = metadata.get("doc_id", "unknown")
            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "doc_id": doc_id,
                    "filename": metadata.get("original_filename") or metadata.get("filename", "unknown"),
                    "num_chunks": 0,
                }
            doc_map[doc_id]["num_chunks"] += 1

        return list(doc_map.values())

    def get_total_chunks(self) -> int:
        """Get total number of chunks in the vector store."""
        if self._store_type == "pgvector":
            try:
                from sqlalchemy import text
                from app.core.database import SessionLocal

                with SessionLocal() as db:
                    res = db.execute(text("SELECT COUNT(*) FROM langchain_pg_embedding")).scalar()
                    return int(res or 0)
            except Exception:
                return 0

        try:
            collection = self._client.get_collection(settings.chroma_collection_name)
            return collection.count()
        except Exception as e:
            err_msg = str(e).lower()
            if "not found" in err_msg or "does not exist" in err_msg or "collection" in err_msg:
                try:
                    logger.warning("Chroma collection missing/stale in get_total_chunks (%s). Reloading...", e)
                    self.reload()
                    collection = self._client.get_collection(settings.chroma_collection_name)
                    return collection.count()
                except Exception:
                    return 0
            return 0

    def is_ready(self) -> bool:
        """Check if vector store is initialized and ready."""
        return self._initialized


# Singleton instance
vector_store_service = VectorStoreService()
