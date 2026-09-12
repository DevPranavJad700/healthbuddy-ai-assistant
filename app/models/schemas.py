"""
Pydantic schemas for API request/response validation.
"""

from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==========================================
# Chat Schemas
# ==========================================

class ChatRequest(BaseModel):
    """Incoming chat message from the user."""
    message: str = Field(..., min_length=1, max_length=2000, description="User's question")
    use_rag: bool = Field(default=True, description="Whether to use RAG pipeline")
    llm_provider: Optional[str] = Field(default=None, description="Override LLM provider")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=2048)
    session_id: Optional[str] = Field(default=None, description="Session ID for analytics")
    disable_cache: bool = Field(
        default=False,
        description="Bypass response cache for accuracy/performance benchmarking",
    )
    consent_to_ai_guidance: bool = Field(
        default=True,
        description="User consent flag for receiving AI health guidance",
    )
    personalization_overrides: Optional[dict] = Field(
        default=None,
        description="Optional per-request profile hints (region, language, medications, comorbidities)",
    )
    preferred_language: Optional[str] = Field(
        default=None,
        description="Optional response language preference (for localization)",
    )


class SourceDocument(BaseModel):
    """A source document chunk used in the response."""
    content: str
    source: str
    page: Optional[int] = None
    score: Optional[float] = None
    relevance: Optional[float] = None
    authority: Optional[str] = None
    citation_quality: Optional[str] = None
    guideline_ref: Optional[str] = None
    guideline_url: Optional[str] = None
    source_version: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response with optional source citations."""
    response: str
    sources: list[SourceDocument] = []
    model_used: str
    provider: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rag_enabled: bool = True
    session_id: Optional[str] = None
    # Safety & explainability
    safety_flagged: bool = False
    emergency_alert: Optional[str] = None
    safety_disclaimer: str = ""
    confidence_note: Optional[str] = None
    prompt_used: Optional[str] = None
    faithfulness_score: Optional[float] = None
    ab_variant: Optional[str] = None
    escalation_action: Optional[str] = None
    triage_level: str = "self_care"
    triage_reason: Optional[str] = None
    citation_quality: Optional[str] = None
    personalization_applied: bool = False
    triage_rule_id: Optional[str] = None
    triage_ruleset_version: Optional[str] = None
    urgency_explanation: Optional[str] = None
    next_actions: list[str] = Field(default_factory=list)


class ChatFeedbackRequest(BaseModel):
    """User outcome feedback for growth analytics."""
    session_id: str = Field(..., min_length=1, max_length=64)
    helpful: Optional[bool] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    resolved: Optional[bool] = None
    comment: Optional[str] = Field(default=None, max_length=1000)


class ClinicianReviewRequest(BaseModel):
    """Request manual clinician review for a chat answer."""
    session_id: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=2000)
    response: str = Field(..., min_length=1, max_length=4000)


class ChatHistoryItem(BaseModel):
    """Single item in chat history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sources: list[SourceDocument] = []


class UserGoalItem(BaseModel):
    id: int
    goal: str
    priority: str
    is_active: bool


class AddUserGoalRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=160)
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")


# ==========================================
# Document Schemas
# ==========================================

class DocumentInfo(BaseModel):
    """Metadata about an uploaded document."""
    doc_id: str
    filename: str
    num_chunks: int
    upload_time: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    success: bool
    message: str
    document: Optional[DocumentInfo] = None


class DocumentListResponse(BaseModel):
    """Response listing all documents."""
    documents: list[DocumentInfo]
    total_chunks: int


# ==========================================
# Health Check
# ==========================================

class HealthCheckResponse(BaseModel):
    """API health check response."""
    status: str = "healthy"
    version: str
    llm_provider: str
    llm_model: str
    documents_loaded: int
    vector_store_ready: bool
