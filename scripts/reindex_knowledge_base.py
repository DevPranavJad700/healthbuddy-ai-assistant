#!/usr/bin/env python3
"""
Re-index Knowledge Base — One-time script to rebuild ChromaDB with language metadata.

Run this after deploying language-aware retrieval to tag all existing chunks with
their language (en/hi/es) so similarity_search_with_language() works correctly.

Usage:
    python scripts/reindex_knowledge_base.py
    python scripts/reindex_knowledge_base.py --dry-run
    python scripts/reindex_knowledge_base.py --knowledge-dir data/knowledge_base
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Re-index ChromaDB knowledge base with language metadata")
    parser.add_argument("--knowledge-dir", default="data/knowledge_base", help="Path to knowledge base directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying ChromaDB")
    parser.add_argument("--collection", default=None, help="Override ChromaDB collection name")
    args = parser.parse_args()

    from app.core.config import settings
    from app.core.logging_config import logger
    from app.services.document_processor import DocumentProcessor
    from app.services.vector_store import vector_store_service

    knowledge_dir = Path(args.knowledge_dir)
    if not knowledge_dir.exists():
        print(f"[ERROR] Knowledge base directory not found: {knowledge_dir}")
        sys.exit(1)

    files = [f for f in knowledge_dir.iterdir() if f.suffix.lower() in (".txt", ".pdf", ".md")]
    print(f"\nFound {len(files)} files in {knowledge_dir}\n")

    # Preview language detection
    processor = DocumentProcessor()
    file_info = []
    for f in sorted(files):
        lang = processor._detect_language_from_filename(f.name)
        file_info.append((f, lang))
        print(f"  {lang.upper()}  {f.name}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made to ChromaDB.")
        return

    print("\n" + "="*60)
    print("Step 1: Clearing existing ChromaDB collection...")
    print("="*60)

    try:
        vector_store_service.initialize()
        import chromadb
        client = chromadb.PersistentClient(path=str(settings.chroma_db_abs_path))
        collection_name = args.collection or settings.chroma_collection_name

        try:
            client.delete_collection(collection_name)
            print(f"  Deleted collection: {collection_name}")
        except Exception:
            print(f"  Collection '{collection_name}' not found — creating fresh.")

        # Re-initialize with fresh collection
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings

        print("\nStep 2: Loading embedding model...")
        embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        vectorstore = Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=embeddings,
        )

        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

        print("\nStep 3: Processing and indexing documents...")
        total_chunks = 0
        for file_path, lang in file_info:
            try:
                chunks = processor.process_document(str(file_path))
                if chunks:
                    vectorstore.add_documents(chunks)
                    total_chunks += len(chunks)
                    print(f"  [OK] [{lang.upper()}] {file_path.name} -> {len(chunks)} chunks")
                else:
                    print(f"  [WARN] [{lang.upper()}] {file_path.name} -> 0 chunks (skipped)")
            except Exception as e:
                print(f"  [ERROR] [{lang.upper()}] {file_path.name} -> ERROR: {e}")

        print(f"\n{'='*60}")
        print(f"Re-index complete! {total_chunks} total chunks indexed.")
        print(f"Collection: {collection_name}")
        print(f"Path: {settings.chroma_db_abs_path}")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] Re-index failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
