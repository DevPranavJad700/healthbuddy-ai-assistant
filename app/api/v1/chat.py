"""
Chat API — Endpoints for interacting with the HealthBuddy chatbot.
Includes safety layer integration and analytics logging.
"""

import time
import uuid

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ChatFeedbackRequest,
    ClinicianReviewRequest,
)
from app.services.audit_service import audit_service
from app.services.rag_service import rag_service
from app.services.analytics_service import analytics_service
from app.services.user_service import user_service
from app.services.consent_service import (
    enforce_latest_consent_or_403,
    enforce_terms_acceptance_or_403,
    SENSITIVE_SCOPE_CHAT,
)
from app.core.database import get_db, ChatLog
from app.core.metrics import CLINICIAN_REVIEW_EVENTS_TOTAL
from app.core.security import get_current_user_optional, get_current_user_required
from app.core.config import settings
from app.core.logging_config import logger

router = APIRouter(prefix="/chat", tags=["Chat"])


def _build_request_personalization_context(base_context: str, overrides: dict | None, preferred_language: str | None) -> str:
    """Merge stored profile context with per-request personalization hints."""
    lines: list[str] = []
    if base_context:
        lines.append(base_context.strip())

    if overrides:
        normalized = {str(k).strip().lower(): v for k, v in overrides.items() if v is not None}
        if normalized:
            lines.append("REQUEST-SCOPED PROFILE HINTS:")
            for key, value in normalized.items():
                if isinstance(value, (list, tuple)):
                    rendered = ", ".join(str(item) for item in value if item is not None)
                else:
                    rendered = str(value)
                if rendered.strip():
                    lines.append(f"- {key}: {rendered.strip()}")

    if preferred_language:
        lines.append(f"Preferred language: {preferred_language.strip()}")

    return "\n".join(lines).strip()



@router.post(
    "/stream",
    summary="Stream a response from HealthBuddy",
    description="Server-Sent Events endpoint for real-time text generation.",
)
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    try:
        logger.info(f"Chat stream request: '{request.message[:80]}...'")
        start_time = time.time()

        if not request.consent_to_ai_guidance:
            raise HTTPException(
                status_code=400,
                detail="consent_to_ai_guidance must be true to receive medical AI guidance.",
            )

        # --- Daily quota check ---
        if user and settings.quota_enabled:
            from app.services.usage_service import check_and_increment_quota, QuotaExceeded
            try:
                is_admin = user.get("role") == "admin"
                check_and_increment_quota(user_id=user["user_id"], is_admin=is_admin)
            except QuotaExceeded as qe:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "daily_limit_reached",
                        "message": f"Daily query limit of {qe.limit} reached. Resets at {qe.resets_at}.",
                        "upgrade_url": "/pricing",
                    },
                )

        enforce_latest_consent_or_403(
            db=db,
            user=user,
            consent_type="ai_guidance",
            scope=SENSITIVE_SCOPE_CHAT,
        )
        enforce_terms_acceptance_or_403(db=db, user=user)

        session_id = request.session_id or str(uuid.uuid4())[:8]
        subject_key = str(user.get("user_id")) if user else f"anon:{session_id}"
        ab_variant = analytics_service.get_or_assign_variant(
            db,
            experiment="response_style",
            subject_key=subject_key,
            variants=("control", "tailored"),
        )

        persisted_context = user_service.get_personalization_context(db, user["user_id"]) if user else ""
        user_context = _build_request_personalization_context(
            persisted_context,
            request.personalization_overrides,
            request.preferred_language,
        )

        async def event_generator():
            try:
                import json
                async for event in rag_service.astream_query(
                    question=request.message,
                    session_id=session_id,
                    use_rag=request.use_rag,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    user_context=user_context,
                    db=db,
                    user_id=user.get("user_id") if user else None,
                    response_variant=ab_variant,
                    preferred_language=request.preferred_language,
                    personalization_applied=bool(user_context),
                ):
                    # Format as SSE (Note: ensure data is single-line or properly encoded JSON)
                    data_str = event['data']
                    if not isinstance(data_str, str):
                        data_str = json.dumps(data_str)
                    
                    # For SSE, multiline data needs multiple 'data: ' prefixes, 
                    # but since we are sending JSON or single tokens, we can just replace newlines 
                    # or better: for json objects, it's one line. For token strings, we can JSON encode.
                    # Wait, our astream yields JSON strings for metadata/sources/done.
                    # For tokens, it yields the raw token. Newlines in tokens will break SSE parsing!
                    # So we MUST json encode the token.
                    if event['event'] == 'token':
                        data_str = json.dumps(data_str)
                    
                    yield f"event: {event['event']}\ndata: {data_str}\n\n"

            except Exception as e:
                import traceback
                logger.error(f"Streaming generator error: {e}\n{traceback.format_exc()}")
                yield f"event: error\ndata: Connection interrupted.\n\n"
                
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat_stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to HealthBuddy",
    description="Send a health-related question and receive an AI-generated response with source citations.",
)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
) -> ChatResponse:
    """Process a chat message through the RAG pipeline with safety and analytics."""
    try:
        logger.info(f"Chat request: '{request.message[:80]}...'")
        start_time = time.time()

        if not request.consent_to_ai_guidance:
            raise HTTPException(
                status_code=400,
                detail="consent_to_ai_guidance must be true to receive medical AI guidance.",
            )

        enforce_latest_consent_or_403(
            db=db,
            user=user,
            consent_type="ai_guidance",
            scope=SENSITIVE_SCOPE_CHAT,
        )
        enforce_terms_acceptance_or_403(db=db, user=user)

        session_id = request.session_id or str(uuid.uuid4())[:8]
        subject_key = str(user.get("user_id")) if user else f"anon:{session_id}"
        ab_variant = analytics_service.get_or_assign_variant(
            db,
            experiment="response_style",
            subject_key=subject_key,
            variants=("control", "tailored"),
        )
        persisted_context = user_service.get_personalization_context(db, user["user_id"]) if user else ""
        user_context = _build_request_personalization_context(
            persisted_context,
            request.personalization_overrides,
            request.preferred_language,
        )

        response = await rag_service.query(
            question=request.message,
            session_id=session_id,
            use_rag=request.use_rag,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            user_context=user_context,
            db=db,
            user_id=user.get("user_id") if user else None,
            response_variant=ab_variant,
            disable_cache=request.disable_cache,
            preferred_language=request.preferred_language,
            personalization_applied=bool(user_context),
        )
        response.session_id = session_id
        response.ab_variant = ab_variant

        # Automatic clinician handoff for high-risk responses.
        if response.emergency_alert is not None or response.safety_flagged:
            review = analytics_service.create_clinician_review(
                db=db,
                session_id=session_id,
                question=request.message,
                response=response.response,
                user_id=user.get("user_id") if user else None,
                triage_level=response.triage_level,
                triage_rule_id=response.triage_rule_id,
            )
            CLINICIAN_REVIEW_EVENTS_TOTAL.labels(event="auto_handoff_created").inc()
            audit_service.log(
                action="chat.clinician_review.auto_handoff",
                status="success",
                user_id=user.get("user_id") if user else None,
                session_id=session_id,
                review_id=review.get("id"),
            )

        elapsed_ms = (time.time() - start_time) * 1000

        analytics_service.log_chat(
            db=db,
            session_id=session_id,
            question=request.message,
            response=response.response[:500],
            model_used=response.model_used,
            provider=response.provider,
            rag_enabled=response.rag_enabled,
            response_time_ms=elapsed_ms,
            sources_count=len(response.sources),
            temperature=request.temperature,
            safety_flagged=response.safety_flagged,
            emergency_detected=response.emergency_alert is not None,
            user_id=user.get("user_id") if user else None,
        )

        audit_service.log(
            action="chat.message",
            status="success",
            user_id=user.get("user_id") if user else None,
            session_id=session_id,
            rag_enabled=response.rag_enabled,
            safety_flagged=response.safety_flagged,
            emergency_detected=response.emergency_alert is not None,
        )

        return response

    except Exception as e:
        if isinstance(e, HTTPException):
            raise

        error_msg = str(e).lower()
        if "token" in error_msg or "auth" in error_msg:
            error_class = "auth"
        elif "timeout" in error_msg or "model" in error_msg:
            error_class = "model"
        elif "database" in error_msg or "sqlite" in error_msg:
            error_class = "dependency"
        elif "validation" in error_msg:
            error_class = "validation"
        else:
            error_class = "unknown"

        analytics_service.increment_counter("chat_errors")
        audit_service.log(
            action="chat.message",
            status="failure",
            user_id=user.get("user_id") if user else None,
            error_class=error_class,
            reason=str(e),
        )
        logger.error(f"Chat error class={error_class}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your message. Please try again."
        )


@router.post("/feedback", summary="Submit chat outcome feedback")
async def submit_feedback(
    req: ChatFeedbackRequest,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    subject_key = str(user.get("user_id")) if user else f"anon:{req.session_id}"
    variant = analytics_service.get_or_assign_variant(
        db,
        experiment="response_style",
        subject_key=subject_key,
        variants=("control", "tailored"),
    )

    saved = analytics_service.log_outcome_feedback(
        db=db,
        session_id=req.session_id,
        user_id=user.get("user_id") if user else None,
        experiment_variant=variant,
        helpful=req.helpful,
        rating=req.rating,
        resolved=req.resolved,
        comment=req.comment,
    )

    audit_service.log(
        action="chat.feedback",
        status="success",
        user_id=user.get("user_id") if user else None,
        session_id=req.session_id,
    )
    return {"success": True, "feedback": saved}


@router.post("/clinician-review", summary="Request clinician review")
async def request_clinician_review(
    req: ClinicianReviewRequest,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    review = analytics_service.create_clinician_review(
        db=db,
        session_id=req.session_id,
        question=req.question,
        response=req.response,
        user_id=user.get("user_id") if user else None,
        triage_level="manual_request",
        triage_rule_id="MANUAL_REQUEST",
    )
    CLINICIAN_REVIEW_EVENTS_TOTAL.labels(event="manual_request_created").inc()
    audit_service.log(
        action="chat.clinician_review.request",
        status="success",
        user_id=user.get("user_id") if user else None,
        session_id=req.session_id,
        review_id=review["id"],
    )
    return {"success": True, "review": review}

@router.get("/sessions", summary="Get user chat sessions")
async def get_sessions(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    """Get authenticated user's unique chat sessions from the database."""
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user["user_id"])
        .order_by(ChatLog.created_at.desc())
        .all()
    )

    sessions = {}
    for log in logs:
        if log.session_id not in sessions:
            sessions[log.session_id] = {
                "session_id": log.session_id,
                "title": log.question[:40] + "..." if len(log.question) > 40 else log.question,
                "timestamp": log.created_at.isoformat()
            }
            
    audit_service.log(
        action="chat.sessions.list",
        status="success",
        user_id=user.get("user_id"),
        count=len(sessions),
    )
    return {"sessions": list(sessions.values())}


@router.get("/sessions/{session_id}", summary="Get history for a specific session")
async def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    """Get authenticated user's chat history for a specific session and load it into RAG memory."""
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.session_id == session_id, ChatLog.user_id == user["user_id"])
        .order_by(ChatLog.created_at.asc())
        .all()
    )

    if not logs:
        raise HTTPException(status_code=404, detail="Session not found")
    
    history = []
    # Pre-fill RAG memory so it regains context
    rag_service.clear_history(session_id)
    if session_id not in rag_service._chat_history:
        rag_service._chat_history[session_id] = []
        
    for log in logs:
        history.append({"role": "user", "content": log.question, "timestamp": log.created_at.isoformat()})
        history.append({"role": "assistant", "content": log.response, "timestamp": log.created_at.isoformat()})
        # Add to RAG internal memory limit to last 40
        rag_service._chat_history[session_id].append({"role": "user", "content": log.question})
        rag_service._chat_history[session_id].append({"role": "assistant", "content": log.response})
        
    if len(rag_service._chat_history[session_id]) > 40:
        rag_service._chat_history[session_id] = rag_service._chat_history[session_id][-40:]

    audit_service.log(
        action="chat.session.read",
        status="success",
        user_id=user.get("user_id"),
        session_id=session_id,
        messages=len(history),
    )
        
    return {"session_id": session_id, "history": history}


@router.delete("/sessions/{session_id}", summary="Clear specific chat history")
async def clear_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    """Clear authenticated user's in-memory history for a specific active session."""
    owns_session = (
        db.query(ChatLog.id)
        .filter(ChatLog.session_id == session_id, ChatLog.user_id == user["user_id"])
        .first()
    )
    if not owns_session:
        raise HTTPException(status_code=404, detail="Session not found")

    rag_service.clear_history(session_id)
    audit_service.log(
        action="chat.session.clear",
        status="success",
        user_id=user.get("user_id"),
        session_id=session_id,
    )
    return {"message": "Session memory cleared"}


@router.get("/sessions")
async def list_chat_sessions(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    """Return list of past chat sessions for the current user."""
    from sqlalchemy import func, distinct
    user_id = user["user_id"]

    # Get one representative row per session (earliest message)
    subq = (
        db.query(
            ChatLog.session_id,
            func.min(ChatLog.id).label("first_id"),
            func.count(ChatLog.id).label("message_count"),
            func.max(ChatLog.created_at).label("last_active"),
        )
        .filter(ChatLog.user_id == user_id)
        .group_by(ChatLog.session_id)
        .order_by(func.max(ChatLog.created_at).desc())
        .limit(limit)
        .subquery()
    )

    rows = (
        db.query(ChatLog, subq.c.message_count, subq.c.last_active)
        .join(subq, ChatLog.id == subq.c.first_id)
        .order_by(subq.c.last_active.desc())
        .all()
    )

    sessions = []
    for log, msg_count, last_active in rows:
        preview = (log.question[:80] + "…") if len(log.question) > 80 else log.question
        sessions.append({
            "session_id": log.session_id,
            "preview": preview,
            "message_count": msg_count,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "last_active": last_active.isoformat() if last_active else None,
            "emergency_detected": log.emergency_detected,
        })

    audit_service.log(
        action="chat.sessions.list",
        status="success",
        user_id=user_id,
        count=len(sessions),
    )
    return {"sessions": sessions, "total": len(sessions)}

