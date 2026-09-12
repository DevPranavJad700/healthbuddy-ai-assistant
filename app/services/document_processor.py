"""
Document Processor — Handles PDF/text loading, chunking, and embedding.

Pipeline:
1. Load documents (PDF, TXT)
2. Split into semantic chunks
3. Attach metadata (source, page, chunk index)
4. Return processed documents ready for vector store
"""

import os
import hashlib
import re
import uuid
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.core.config import settings
from app.core.logging_config import logger


class DocumentProcessor:
    """Processes documents into chunks suitable for the vector store."""

    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
            is_separator_regex=False,
        )
        self.upload_dir = Path("./data/pdfs")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def load_pdf(self, file_path: str) -> list[Document]:
        """Load and split a PDF file."""
        logger.info(f"Loading PDF: {file_path}")
        loader = PyPDFLoader(file_path)
        pages = loader.load()
        logger.info(f"Loaded {len(pages)} pages from {file_path}")
        return pages

    def load_text(self, file_path: str) -> list[Document]:
        """Load a text file."""
        logger.info(f"Loading text file: {file_path}")
        loader = TextLoader(file_path, encoding="utf-8")
        docs = loader.load()
        return docs

    def load_document(self, file_path: str) -> list[Document]:
        """Load a document based on file extension."""
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return self.load_pdf(file_path)
        elif ext in (".txt", ".md", ".text"):
            return self.load_text(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def process_document(
        self,
        file_path: str,
        doc_id: Optional[str] = None,
    ) -> list[Document]:
        """
        Full processing pipeline: Load → Split → Add Metadata.

        Returns list of Document chunks ready for vector store.
        """
        # Generate document ID
        if doc_id is None:
            doc_id = self._generate_doc_id(file_path)

        # Load raw documents
        raw_docs = self.load_document(file_path)

        # Split into chunks
        chunks = self.text_splitter.split_documents(raw_docs)

        # Enrich metadata
        filename = Path(file_path).name
        language = self._detect_language_from_filename(filename)
        for i, chunk in enumerate(chunks):
            chunk.metadata.update({
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "language": language,
            })
            # Ensure page number exists
            if "page" not in chunk.metadata:
                chunk.metadata["page"] = 0

        logger.info(
            f"Processed '{filename}' into {len(chunks)} chunks "
            f"(doc_id: {doc_id}, language: {language})"
        )
        return chunks

    def save_uploaded_file(self, filename: str, content: bytes) -> str:
        """Save an uploaded file to the upload directory."""
        safe_name = self._safe_upload_filename(filename)
        file_path = (self.upload_dir / safe_name).resolve()

        # Ensure the resolved path stays inside upload_dir.
        upload_root = self.upload_dir.resolve()
        if upload_root not in file_path.parents:
            raise ValueError("Invalid upload path")

        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved uploaded file: {file_path}")
        return str(file_path)

    @staticmethod
    def _safe_upload_filename(filename: str) -> str:
        """Generate a safe server-side filename preserving extension."""
        original = Path(filename or "document.txt").name
        stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(original).stem).strip("._")
        stem = stem or "document"
        ext = Path(original).suffix.lower()
        unique = uuid.uuid4().hex[:10]
        return f"{stem}_{unique}{ext}"

    def process_directory(self, dir_path: str) -> list[Document]:
        """Process all supported documents in a directory."""
        all_chunks = []
        supported_extensions = {".pdf", ".txt", ".md", ".text"}
        dir_path = Path(dir_path)

        if not dir_path.exists():
            logger.warning(f"Directory not found: {dir_path}")
            return []

        for file_path in dir_path.iterdir():
            if file_path.suffix.lower() in supported_extensions:
                try:
                    chunks = self.process_document(str(file_path))
                    all_chunks.extend(chunks)
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")

        logger.info(f"Processed {len(all_chunks)} total chunks from {dir_path}")
        return all_chunks

    @staticmethod
    def _generate_doc_id(file_path: str) -> str:
        """Generate a deterministic document ID from file path."""
        return hashlib.md5(file_path.encode(), usedforsecurity=False).hexdigest()[:12]

    @staticmethod
    def _detect_language_from_filename(filename: str) -> str:
        """
        Detect document language from filename conventions.

        Convention:
          - Files ending in '_hindi.txt' or 'naidanik*.txt' → 'hi'
          - Files ending in '_espanol.txt' or 'guia*.txt'   → 'es'
          - Everything else                                  → 'en'
        """
        name_lower = filename.lower()
        # Hindi indicators
        if any(token in name_lower for token in ("hindi", "_hi.", "naidanik", "margdarshika")):
            return "hi"
        # Spanish indicators
        if any(token in name_lower for token in ("espanol", "_es.", "guia", "español")):
            return "es"
        # Arabic (future-proofing)
        if any(token in name_lower for token in ("arabic", "_ar.", "murshid")):
            return "ar"
        return "en"

