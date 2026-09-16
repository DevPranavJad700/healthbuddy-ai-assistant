"""
Documents API — Endpoints for uploading and managing PDF documents.
"""

from datetime import UTC, datetime
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models.schemas import (
    DocumentUploadResponse,
    DocumentInfo,
    DocumentListResponse,
)
from app.services.document_processor import DocumentProcessor
from app.services.audit_service import audit_service
from app.services.vector_store import vector_store_service
from app.core.logging_config import logger
from app.core.config import settings

router = APIRouter(prefix="/documents", tags=["Documents"])

# Shared document processor instance
doc_processor = DocumentProcessor()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    summary="Upload a document",
    description="Upload a PDF or text file to be processed and added to the knowledge base.",
)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    """Upload and process a document for RAG."""
    try:
        # Validate file type
        allowed_types = {".pdf", ".txt", ".md"}
        allowed_mime_by_ext = {
            ".pdf": {"application/pdf"},
            ".txt": {"text/plain", "application/octet-stream"},
            ".md": {"text/markdown", "text/plain", "application/octet-stream"},
        }
        filename = file.filename or "document.txt"
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_types)}"
            )

        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if settings.strict_upload_mime_check:
            content_type = (file.content_type or "application/octet-stream").lower()
            global_allowed = set(settings.allowed_upload_mime_types_list)
            ext_allowed = allowed_mime_by_ext.get(ext, {"application/octet-stream"})
            if content_type not in global_allowed or content_type not in ext_allowed:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported content type '{content_type}' for {ext}. "
                        f"Allowed: {', '.join(sorted(ext_allowed))}"
                    ),
                )

        # Lightweight content signature checks to prevent extension spoofing.
        if ext == ".pdf" and not content.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Invalid PDF file signature")
        if ext in {".txt", ".md"}:
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Text/markdown files must be UTF-8 encoded",
                ) from exc

        max_upload_bytes = settings.upload_max_size_mb * 1024 * 1024
        if len(content) > max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {settings.upload_max_size_mb}MB.",
            )

        # Save file
        file_path = doc_processor.save_uploaded_file(filename, content)

        # Process document into chunks
        chunks = doc_processor.process_document(file_path)

        for chunk in chunks:
            chunk.metadata["original_filename"] = filename

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No content could be extracted from the document"
            )

        # Add to vector store
        vector_store_service.add_documents(chunks)

        doc_id = chunks[0].metadata.get("doc_id", "unknown")
        doc_info = DocumentInfo(
            doc_id=doc_id,
            filename=filename,
            num_chunks=len(chunks),
            upload_time=datetime.now(UTC),
        )

        logger.info(f"Document uploaded: {filename} ({len(chunks)} chunks)")
        audit_service.log(
            action="documents.upload",
            status="success",
            filename=filename,
            doc_id=doc_id,
            chunks=len(chunks),
        )

        return DocumentUploadResponse(
            success=True,
            message=f"Successfully processed '{filename}' into {len(chunks)} chunks",
            document=doc_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        audit_service.log(
            action="documents.upload",
            status="failure",
            filename=filename if 'filename' in locals() else None,
            reason=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}"
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all documents",
    description="Get a list of all documents in the knowledge base.",
)
async def list_documents() -> DocumentListResponse:
    """List all uploaded documents."""
    try:
        docs = vector_store_service.get_document_list()
        total_chunks = vector_store_service.get_total_chunks()

        doc_infos = [
            DocumentInfo(
                doc_id=d["doc_id"],
                filename=d["filename"],
                num_chunks=d["num_chunks"],
            )
            for d in docs
        ]

        return DocumentListResponse(
            documents=doc_infos,
            total_chunks=total_chunks,
        )

    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{doc_id}",
    summary="Get document details & content",
    description="Retrieve document metadata and text content from the knowledge base.",
)
async def get_document(doc_id: str):
    """Retrieve document details and content."""
    try:
        from pathlib import Path

        docs = vector_store_service.get_document_list()
        matching = next((d for d in docs if d["doc_id"] == doc_id), None)
        if not matching:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        filename = matching["filename"]
        content = ""

        kb_path = Path("./data/knowledge_base") / filename
        pdf_path = Path("./data/pdfs") / filename

        if kb_path.exists():
            content = kb_path.read_text(encoding="utf-8", errors="ignore")
        elif pdf_path.exists():
            try:
                content = pdf_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                content = f"[Binary PDF File: {filename}]"

        return {
            "doc_id": matching["doc_id"],
            "filename": matching["filename"],
            "num_chunks": matching["num_chunks"],
            "content": content,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{doc_id}",
    summary="Delete a document",
    description="Remove a document and its chunks from the knowledge base.",
)
async def delete_document(doc_id: str):
    """Delete a document from the vector store."""
    try:
        deleted = vector_store_service.delete_by_doc_id(doc_id)
        if deleted == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Document not found: {doc_id}"
            )

        audit_service.log(
            action="documents.delete",
            status="success",
            doc_id=doc_id,
            deleted_chunks=deleted,
        )

        return {
            "message": f"Deleted {deleted} chunks for document {doc_id}",
            "deleted_chunks": deleted,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}", exc_info=True)
        audit_service.log(
            action="documents.delete",
            status="failure",
            doc_id=doc_id,
            reason=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))
