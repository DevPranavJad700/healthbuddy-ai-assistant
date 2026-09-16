"""
RAG Service — LangChain LCEL-based Retrieval-Augmented Generation pipeline.

Pipeline:
1. User query -> Retrieve relevant chunks from ChromaDB
2. Format context + question into prompt
3. Send to LLM for generation
4. Parse and return response with source citations
"""

import asyncio
import hashlib
import random
import re
from typing import Optional
from datetime import UTC, datetime

from operator import itemgetter
from sqlalchemy.orm import Session

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.logging_config import logger
from app.services.vector_store import vector_store_service
from app.services.llm_provider import get_llm
from app.services.safety_layer import safety_layer
from app.services.analytics_service import analytics_service
from app.services.triage_rules import assess_triage
from app.services.source_traceability import resolve_traceability
from app.core.metrics import (
    CHAT_FALLBACK_RESPONSES,
    CHAT_PROVIDER_FAILURES,
    CHAT_ZERO_SOURCE_EVENTS_TOTAL,
)
from app.models.schemas import ChatResponse, SourceDocument


# ==========================================
# Prompt Templates
# ==========================================

RAG_SYSTEM_PROMPT = """You are HealthBuddy, a board-certified-equivalent AI health assistant with deep expertise in clinical medicine, nutrition, pharmacology, and preventive care. Your role is to provide clear, synthesised, expert-quality health information — not to copy text, but to think through the evidence and explain it naturally.

YOUR REASONING PROCESS (follow silently before responding):
Step 1 — Understand: Identify exactly what the user is asking. Is it a factual question, a symptom concern, a medication query, or lifestyle advice?
Step 2 — Synthesise: Read ALL provided context chunks. Do NOT copy sentences verbatim. Cross-reference the information, identify the most clinically relevant facts, and build a coherent expert understanding.
Step 3 — Personalise: If the user profile contains age, gender, or conditions, tailor the advice to their specific situation.
Step 4 — Respond: Write using structured markdown for clarity.

CRITICAL RULES:
1. SYNTHESISE — never copy-paste chunks. Merge ideas from multiple sources into your own expert words.
2. If context lacks relevant information, say: "I don't have enough clinical data in my knowledge base for this. Please consult a healthcare professional."
3. NEVER reference document names, chunk numbers, or file sources in your answer.
4. NEVER diagnose a condition definitively or prescribe specific dosages.
5. Be empathetic and warm — acknowledge the patient's concern before answering.
6. Default length: 120–250 words with structure. If the user asks for detail, go deeper.
7. Do NOT repeat the same point twice in one response.
8. For follow-ups (“more”, “continue”, “explain”): provide only NEW information not already stated.
9. Respond in the user's preferred language when specified.
10. The system adds a medical disclaimer automatically — do NOT add your own “consult a doctor” conclusion.

OUTPUT FORMAT (always use this structure):
- Start with 1 warm sentence acknowledging the user's concern
- Use **bold** for key terms
- Use bullet points or numbered lists for steps/options
- Include a short section titled "⚠️ When to see a doctor" at the end with 2–3 clear red-flag signs
- Do NOT use h1 (#) headers — use **bold** subheadings instead

RESPONSE STYLE:
{response_style}

USER HEALTH PROFILE (personalise your answer to this person):
{user_context}

PREFERRED LANGUAGE:
{preferred_language}

CONVERSATION HISTORY (for continuity — do not repeat what was already said):
{chat_history}

KNOWLEDGE BASE CONTEXT (synthesise this — do NOT copy verbatim):
{context}

USER'S QUESTION:
{question}

EXPERT ANSWER (structured, warm, clinically sound):"""

STANDALONE_PROMPT = """You are HealthBuddy, a board-certified-equivalent AI health assistant with deep clinical knowledge. Even without a specific knowledge base document, you have comprehensive training in medicine, nutrition, pharmacology, and public health.

YOUR APPROACH:
- Think like an expert clinician. Reason through the question before answering.
- Provide synthesised, expert-quality information — not generic disclaimers.
- Acknowledge the user's concern empathetically, then answer clearly and specifically.
- Tailor the answer to the user's health profile if provided.

RULES:
1. Default length: 120–250 words with structured format.
2. Never repeat the same point in one response.
3. For follow-ups (“more”, “continue”): provide only NEW information.
4. Respond in the user's preferred language. Use medically accurate terminology.
5. Do NOT add “consult a doctor” as a conclusion — the system adds disclaimers automatically.
6. NEVER diagnose definitively or prescribe specific dosages.
7. Sound like a knowledgeable, caring physician — not a FAQ bot.

OUTPUT FORMAT (always use this structure):
- Start with 1 warm sentence acknowledging the user's concern
- Use **bold** for key medical terms
- Use bullet points or numbered lists for steps, options, or lists
- Always end with a short "⚠️ When to see a doctor" section with 2–3 red-flag symptoms
- Do NOT use h1 (#) headers — use **bold** subheadings instead

RESPONSE STYLE:
{response_style}

USER HEALTH PROFILE (personalise if relevant):
{user_context}

PREFERRED LANGUAGE:
{preferred_language}

CONVERSATION HISTORY:
{chat_history}

USER'S QUESTION:
{question}

EXPERT ANSWER:"""


class RAGService:
    """
    RAG (Retrieval-Augmented Generation) service using LangChain LCEL.
    """

    _PROMPT_LEAK_PATTERNS = [
        r"\bpersonal preferences\b",
        r"\bproceed with this task\b",
        r"\bcomplete each step\b",
        r"\bour primary goal\b",
        r"\ball requests must include links\b",
        r"\battention through social media\b",
        r"\btheguardian\b",
        r"\bthis task\b",
        r"\bplease provide an explanation\b",
    ]

    _TOPIC_KEYWORDS = {
        "sleep": {"sleep", "insomnia", "bedtime", "melatonin", "rest", "nap", "night"},
        "stress": {"stress", "anxiety", "breathing", "mindfulness", "relax", "panic"},
        "nutrition": {"vitamin", "nutrition", "diet", "food", "supplement", "mineral"},
        "exercise": {"exercise", "workout", "fitness", "activity", "training", "aerobic"},
        "diabetes": {"diabetes", "blood sugar", "glucose", "insulin", "a1c"},
        "blood pressure": {"blood pressure", "hypertension", "pressure", "systolic", "diastolic"},
        "headache": {"headache", "migraine", "nausea", "light sensitivity"},
    }

    _FOLLOW_UP_HINTS = {
        "more",
        "elaborate",
        "details",
        "explain more",
        "go deeper",
        "continue",
        "why",
        "how",
        "next",
    }

    _DETAILED_REQUEST_HINTS = {
        "detailed",
        "detail",
        "in depth",
        "deep dive",
        "step by step",
        "comprehensive",
        "explain why",
    }

    _LOCAL_FALLBACK_MARKERS = {
        "i can help with general health information",
        "for urgent concerns, please contact a qualified healthcare professional",
    }

    def __init__(self):
        self._llm = None
        self._rag_chain = None
        self._standalone_chain = None
        self._chat_history: dict[str, list[dict]] = {}
        self._response_cache: dict[str, tuple[float, dict]] = {}
        self._cache_insert_counter: int = 0
        self._max_sessions: int = 1000
        self._initialized = False

    @staticmethod
    def _cache_key(
        question: str,
        use_rag: bool,
        response_variant: str,
        user_context: str,
        preferred_language: str,
    ) -> str:
        payload = "|".join([
            question.strip().lower(),
            "rag" if use_rag else "no_rag",
            response_variant.strip().lower(),
            user_context.strip().lower(),
            preferred_language.strip().lower(),
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _get_cached_response(self, cache_key: str) -> ChatResponse | None:
        now = datetime.now(UTC).timestamp()
        row = self._response_cache.get(cache_key)
        if not row:
            return None
        expires_at, payload = row
        if expires_at <= now:
            self._response_cache.pop(cache_key, None)
            return None

        return ChatResponse(
            response=payload["response"],
            sources=[SourceDocument(**source) for source in payload.get("sources", [])],
            model_used=payload["model_used"],
            provider=payload["provider"],
            timestamp=datetime.now(UTC),
            rag_enabled=payload["rag_enabled"],
            session_id=payload.get("session_id"),
            safety_flagged=payload["safety_flagged"],
            emergency_alert=payload.get("emergency_alert"),
            safety_disclaimer=payload["safety_disclaimer"],
            confidence_note=payload.get("confidence_note"),
            prompt_used=payload.get("prompt_used"),
            faithfulness_score=payload.get("faithfulness_score"),
            ab_variant=payload.get("ab_variant"),
            escalation_action=payload.get("escalation_action"),
            triage_level=payload.get("triage_level", "self_care"),
            triage_reason=payload.get("triage_reason"),
            citation_quality=payload.get("citation_quality"),
            personalization_applied=payload.get("personalization_applied", False),
            triage_rule_id=payload.get("triage_rule_id"),
            triage_ruleset_version=payload.get("triage_ruleset_version"),
            urgency_explanation=payload.get("urgency_explanation"),
            next_actions=payload.get("next_actions", []),
        )

    def _store_cached_response(self, cache_key: str, response: ChatResponse):
        ttl = max(10, settings.response_cache_ttl_seconds)
        if len(self._response_cache) >= max(10, settings.response_cache_max_entries):
            oldest_key = next(iter(self._response_cache.keys()))
            self._response_cache.pop(oldest_key, None)

        # Periodic cleanup of expired entries every 100 insertions
        self._cache_insert_counter += 1
        if self._cache_insert_counter % 100 == 0:
            now_ts = datetime.now(UTC).timestamp()
            expired_keys = [k for k, (exp, _) in self._response_cache.items() if exp <= now_ts]
            for k in expired_keys:
                self._response_cache.pop(k, None)
            if expired_keys:
                logger.debug("Cache cleanup: evicted %d expired entries", len(expired_keys))

        self._response_cache[cache_key] = (
            datetime.now(UTC).timestamp() + ttl,
            {
                "response": response.response,
                "sources": [
                    {
                        "content": s.content,
                        "source": s.source,
                        "page": s.page,
                        "score": s.score,
                        "relevance": s.relevance,
                        "authority": s.authority,
                        "citation_quality": s.citation_quality,
                        "guideline_ref": s.guideline_ref,
                        "guideline_url": s.guideline_url,
                        "source_version": s.source_version,
                    }
                    for s in (response.sources or [])
                ],
                "model_used": response.model_used,
                "provider": response.provider,
                "rag_enabled": response.rag_enabled,
                "session_id": response.session_id,
                "safety_flagged": response.safety_flagged,
                "emergency_alert": response.emergency_alert,
                "safety_disclaimer": response.safety_disclaimer,
                "confidence_note": response.confidence_note,
                "prompt_used": response.prompt_used,
                "faithfulness_score": response.faithfulness_score,
                "ab_variant": response.ab_variant,
                "escalation_action": response.escalation_action,
                "triage_level": response.triage_level,
                "triage_reason": response.triage_reason,
                "citation_quality": response.citation_quality,
                "personalization_applied": response.personalization_applied,
                "triage_rule_id": response.triage_rule_id,
                "triage_ruleset_version": response.triage_ruleset_version,
                "urgency_explanation": response.urgency_explanation,
                "next_actions": response.next_actions,
            },
        )

    @staticmethod
    def _build_action_card(triage_level: str, triage_reason: str, escalation_action: str | None) -> tuple[str | None, list[str]]:
        if triage_level == "emergency":
            return (
                triage_reason,
                [
                    "Call local emergency services now.",
                    "Do not drive yourself if severe symptoms are present.",
                    "Keep someone informed while awaiting medical help.",
                ],
            )
        if triage_level == "urgent":
            return (
                triage_reason,
                [
                    escalation_action or "Seek urgent in-person evaluation today.",
                    "Monitor worsening signs (breathing trouble, confusion, persistent severe pain).",
                    "Escalate to emergency services if severe red flags appear.",
                ],
            )
        return (
            triage_reason,
            [
                "Use self-care steps from the response.",
                "Monitor symptoms and seek care if they worsen or persist.",
                "Watch for red-flag symptoms requiring urgent escalation.",
            ],
        )

    def initialize(self):
        """Initialize the RAG pipeline components."""
        if self._initialized:
            return

        logger.info("Initializing RAG service...")

        # Load LLM
        logger.info(f"Loading LLM: {settings.llm_provider}/{settings.llm_model}")
        self._llm = get_llm()

        # Initialize vector store
        vector_store_service.initialize()

        # Build RAG chain (LCEL)
        rag_prompt = PromptTemplate.from_template(RAG_SYSTEM_PROMPT)
        retriever = vector_store_service.get_retriever()

        self._rag_chain = (
            RunnableParallel(
                context=itemgetter("question") | retriever | self._format_docs,
                question=itemgetter("question"),
                chat_history=itemgetter("chat_history"),
                user_context=itemgetter("user_context"),
                response_style=itemgetter("response_style"),
                preferred_language=itemgetter("preferred_language"),
            )
            | rag_prompt
            | self._llm
            | StrOutputParser()
        )

        # Build standalone chain (no RAG)
        standalone_prompt = PromptTemplate.from_template(STANDALONE_PROMPT)
        self._standalone_chain = (
            {
                "question": itemgetter("question"),
                "chat_history": itemgetter("chat_history"),
                "user_context": itemgetter("user_context"),
                "response_style": itemgetter("response_style"),
                "preferred_language": itemgetter("preferred_language"),
            }
            | standalone_prompt
            | self._llm
            | StrOutputParser()
        )

        self._initialized = True
        logger.info("RAG service initialized successfully")

    @staticmethod
    def _format_docs(docs) -> str:
        """Format retrieved documents into a context string."""
        if not docs:
            return "No relevant documents found."

        formatted = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("filename", "Unknown")
            page = doc.metadata.get("page", "N/A")
            formatted.append(
                f"[Document {i} | Source: {source} | Page: {page}]\n"
                f"{doc.page_content}"
            )
        return "\n\n---\n\n".join(formatted)

    @staticmethod
    def _tokenize_terms(text: str) -> set[str]:
        stopwords = {
            "what",
            "when",
            "where",
            "which",
            "would",
            "could",
            "should",
            "about",
            "there",
            "their",
            "these",
            "those",
            "please",
            "health",
            "healthbuddy",
            "answer",
            "question",
            "help",
            "need",
            "want",
            "have",
            "with",
            "from",
            "that",
            "this",
            "your",
            "them",
            "then",
        }
        return {
            term
            for term in re.findall(r"[a-zA-Z][a-zA-Z0-9']+", text.lower())
            if len(term) >= 4 and term not in stopwords
        }

    @classmethod
    def _detect_topic(cls, text: str) -> str | None:
        text_lower = text.lower()
        for topic, keywords in cls._TOPIC_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                return topic
        return None

    @classmethod
    def _looks_like_prompt_leak(cls, response: str) -> bool:
        response_lower = response.lower()
        if any(re.search(pattern, response_lower) for pattern in cls._PROMPT_LEAK_PATTERNS):
            return True
        if "http://" in response_lower or "https://" in response_lower:
            return True
        if response_lower.count("task") >= 2 and response_lower.count("you should") >= 1:
            return True
        return False

    def _is_response_relevant(self, question: str, response: str, sources: list[SourceDocument]) -> bool:
        if self._looks_like_prompt_leak(response):
            return False

        if self._is_followup_prompt(question):
            # Follow-up turns like "more" are often concise; avoid over-filtering.
            return len(response.strip()) >= 40

        question_terms = self._tokenize_terms(question)
        response_terms = self._tokenize_terms(response)

        if not question_terms or not response_terms:
            return False

        question_topic = self._detect_topic(question)
        if question_topic:
            topic_keywords = self._TOPIC_KEYWORDS[question_topic]
            if not any(keyword in response.lower() for keyword in topic_keywords):
                return False

        overlap = question_terms & response_terms
        if overlap:
            return True

        source_terms: set[str] = set()
        for source in sources[:3]:
            source_terms.update(self._tokenize_terms(source.content))
            source_terms.update(self._tokenize_terms(source.source))

        return bool(question_terms & source_terms and response_terms & source_terms)

    @classmethod
    def _is_followup_prompt(cls, question: str) -> bool:
        text = " ".join(question.lower().split())
        if not text:
            return False
        if text in cls._FOLLOW_UP_HINTS:
            return True
        if len(text) <= 16 and any(hint in text for hint in cls._FOLLOW_UP_HINTS):
            return True
        return False

    def _resolve_effective_question(self, question: str, session_id: str) -> str:
        """Expand short follow-up prompts using prior user context for better retrieval."""
        if not self._is_followup_prompt(question):
            return question

        history = self._chat_history.get(session_id, [])
        previous_user_question = ""
        previous_assistant_answer = ""
        for msg in reversed(history):
            role = msg.get("role")
            if role == "assistant" and not previous_assistant_answer:
                previous_assistant_answer = str(msg.get("content", "")).strip()
            if role == "user":
                previous_user_question = str(msg.get("content", "")).strip()
                if previous_user_question:
                    break

        if not previous_user_question:
            return question

        return (
            f"Follow-up request: {question.strip()}\n"
            f"Previous user question: {previous_user_question}\n"
            f"Previous assistant answer summary: {previous_assistant_answer[:500] or 'None'}\n"
            "Provide only new, non-overlapping information that was not already covered. "
            "Avoid repeating prior points. Keep the continuation brief and high-value."
        )

    @classmethod
    def _requests_detailed_answer(cls, question: str) -> bool:
        q = " ".join(question.lower().split())
        return any(hint in q for hint in cls._DETAILED_REQUEST_HINTS)

    def _sanitize_response(self, question: str, response: str) -> str:
        """Reduce repetition and keep responses brief unless detail is requested."""
        if not response:
            return response

        parts = re.split(r"(?<=[.!?])\s+|\n+", response)
        unique_parts: list[str] = []
        seen = set()

        for part in parts:
            cleaned = " ".join(part.strip().split())
            if not cleaned:
                continue
            key = re.sub(r"[^a-z0-9 ]+", "", cleaned.lower())
            if len(key) < 10:
                continue
            if key in seen:
                continue
            seen.add(key)
            unique_parts.append(cleaned)

        if not unique_parts:
            return response.strip()

        compact = " ".join(unique_parts)
        words = compact.split()

        max_words = 160 if self._requests_detailed_answer(question) else 95
        if len(words) <= max_words:
            return compact.strip()

        trimmed = " ".join(words[:max_words]).rstrip(" ,;:")
        if not trimmed.endswith((".", "!", "?")):
            trimmed += "..."
        return trimmed

    def _source_faithfulness_score(self, response: str, sources: list[SourceDocument]) -> float:
        if not response or not sources:
            return 0.0

        response_terms = self._tokenize_terms(response)
        if not response_terms:
            return 0.0

        source_blob = " ".join(s.content for s in sources if s.content)
        source_terms = self._tokenize_terms(source_blob)
        if not source_terms:
            return 0.0

        overlap = response_terms & source_terms
        return round(len(overlap) / max(1, len(response_terms)), 3)

    @staticmethod
    def _authority_from_source(source_name: str) -> str:
        name = (source_name or "").lower()
        if any(tag in name for tag in ("guideline", "protocol", "validation", "who", "cdc", "nih")):
            return "high"
        if any(tag in name for tag in ("expansion", "guide", "health_guide")):
            return "medium"
        return "base"

    @staticmethod
    def _citation_quality_label(avg_relevance: float, faithfulness_score: float, source_count: int) -> str:
        if source_count == 0:
            return "low"
        if faithfulness_score >= 0.3 and avg_relevance >= 0.5:
            return "high"
        if faithfulness_score >= 0.16 and avg_relevance >= 0.35:
            return "medium"
        return "low"

    def _build_extractive_answer_from_sources(self, question: str, sources: list[SourceDocument]) -> str:
        """Build a direct answer from retrieved chunks when model output is unavailable/generic."""
        if not sources:
            return ""

        question_terms = self._tokenize_terms(question)
        candidates: list[tuple[int, str]] = []

        for source in sources[:5]:
            text = source.content or ""
            # Split into concise sentence-like chunks.
            sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
            for sentence in sentences:
                cleaned = sentence.strip(" -\t\r\n")
                if len(cleaned) < 30:
                    continue
                terms = self._tokenize_terms(cleaned)
                overlap = len(question_terms & terms) if question_terms else 0
                numeric_bonus = 1 if re.search(r"\b\d+(?:[./-]\d+)?\b", cleaned) else 0
                score = overlap * 2 + numeric_bonus
                if score > 0:
                    candidates.append((score, cleaned))

        if not candidates:
            return ""

        # Highest-scoring unique lines first.
        candidates.sort(key=lambda x: x[0], reverse=True)
        picked: list[str] = []
        seen = set()
        for _, sentence in candidates:
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            picked.append(sentence)
            if len(picked) >= 3:
                break

        return " ".join(picked)

    def _retrieve_with_guardrail(self, question: str, mode: str, language: str | None = None) -> list:
        """Retrieve chunks with one retry when corpus exists but zero chunks are returned."""
        source_docs = vector_store_service.similarity_search_with_language(
            question, language=language
        )
        if source_docs:
            return source_docs

        if vector_store_service.get_total_chunks() <= 0:
            return source_docs

        CHAT_ZERO_SOURCE_EVENTS_TOTAL.labels(mode=mode, phase="initial").inc()
        logger.warning("Zero-source retrieval for mode=%s lang=%s, retrying once", mode, language)

        retry_docs = vector_store_service.similarity_search_with_language(
            question, language=language
        )
        if retry_docs:
            CHAT_ZERO_SOURCE_EVENTS_TOTAL.labels(mode=mode, phase="recovered_on_retry").inc()
            return retry_docs

        CHAT_ZERO_SOURCE_EVENTS_TOTAL.labels(mode=mode, phase="final_zero_sources").inc()
        logger.warning("Zero-source retrieval persisted after retry for mode=%s", mode)
        return retry_docs

    @classmethod
    def _is_local_fallback_response(cls, response: str) -> bool:
        text = response.lower()
        return all(marker in text for marker in cls._LOCAL_FALLBACK_MARKERS)

    def _build_safe_fallback_response(self, question: str) -> str:
        question_lower = question.lower()

        if "sleep" in question_lower:
            return (
                "For better sleep quality, try keeping a consistent sleep schedule, "
                "limiting caffeine later in the day, reducing screen time before bed, "
                "and keeping your room dark and cool. If sleep problems continue, "
                "consider speaking with a healthcare professional."
            )
        if "stress" in question_lower or "anxiety" in question_lower:
            return (
                "For stress or anxiety, start with slow breathing, regular movement, "
                "good sleep, and limiting caffeine and alcohol. If symptoms are severe "
                "or persistent, speak with a healthcare professional."
            )
        if "vitamin" in question_lower or "nutrition" in question_lower or "diet" in question_lower:
            return (
                "A balanced diet with fruits, vegetables, whole grains, lean protein, "
                "and healthy fats usually covers most vitamin needs. If you suspect a "
                "deficiency, ask a healthcare professional before taking supplements."
            )

        return (
            "I couldn't generate a reliable answer from the model right now. "
            "Please rephrase the question or upload relevant health documents, and I can try again."
        )

    def _get_history_str(self, session_id: str) -> str:
        """Format the chat history for a given session into a string limit to last 5 turns."""
        if session_id not in self._chat_history:
            return "No previous conversation context."
        
        history = self._chat_history[session_id][-10:] # last 5 turns (user+assistant)
        if not history:
            return "No previous conversation context."
            
        formatted = []
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            formatted.append(f"{role}: {msg['content']}")
        return "\n".join(formatted)

    async def _invoke_chain_with_retries(self, chain, payload: dict) -> str:
        """Invoke a chain with timeout + retry backoff to handle flaky provider/network errors."""
        loop = asyncio.get_event_loop()
        retries = max(0, settings.llm_max_retries)
        timeout = max(5, settings.llm_request_timeout_seconds)

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, chain.invoke, payload),
                    timeout=timeout,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    raise
                error_text = str(exc).lower()
                is_rate_limited = "429" in error_text or "rate" in error_text
                base_backoff = settings.llm_retry_backoff_seconds * (2 ** attempt)
                if is_rate_limited:
                    base_backoff += settings.llm_rate_limit_extra_backoff_seconds
                jitter = random.uniform(0.0, max(0.0, settings.llm_retry_jitter_ratio))
                backoff = min(
                    settings.llm_retry_backoff_max_seconds,
                    base_backoff * (1.0 + jitter),
                )
                logger.warning(
                    "LLM invoke failed attempt %s/%s: %s; retrying in %.2fs",
                    attempt + 1,
                    retries + 1,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)

        if last_error:
            raise last_error
        raise RuntimeError("Unknown LLM invocation failure")

    async def query(
        self,
        question: str,
        session_id: str = "default",
        use_rag: bool = True,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        user_context: str = "",
        db: Session | None = None,
        user_id: int | None = None,
        response_variant: str = "control",
        disable_cache: bool = False,
        preferred_language: str | None = None,
        personalization_applied: bool = False,
    ) -> ChatResponse:
        """
        Process a user query through the RAG pipeline with safety checks.

        Args:
            question: User's question.
            session_id: Session identifier for context memory.
            use_rag: Whether to use retrieval-augmented generation.
            temperature: LLM temperature.
            max_tokens: Maximum response tokens.

        Returns:
            ChatResponse with answer, source citations, and safety info.
        """
        if not self._initialized:
            self.initialize()

        if session_id not in self._chat_history:
            self._chat_history[session_id] = []

        effective_user_context = (user_context or "").strip()
        if db is not None and user_id is not None:
            try:
                from app.services.user_service import user_service

                persisted_profile_context = user_service.get_personalization_context(db, user_id)
                if persisted_profile_context:
                    persisted_profile_context = persisted_profile_context.strip()
                    if effective_user_context:
                        if persisted_profile_context not in effective_user_context:
                            effective_user_context = (
                                f"{persisted_profile_context}\n{effective_user_context}"
                            )
                    else:
                        effective_user_context = persisted_profile_context
            except Exception as exc:
                logger.warning("Could not inject persisted profile context: %s", exc)

        effective_question = self._resolve_effective_question(question, session_id)

        sources: list[SourceDocument] = []
        response_text = ""
        prompt_used = ""
        faithfulness_score = 0.0
        citation_quality = "low"
        emergency_alert = None
        safety_flagged = False

        # Get Chat History
        chat_history_str = self._get_history_str(session_id)
        has_prior_context = bool(self._chat_history.get(session_id))

        # 1. SAFETY CHECK — scan user input for emergencies
        input_check = safety_layer.check_user_input(question)
        if input_check.is_emergency:
            emergency_alert = input_check.warning_message
            logger.warning(f"Emergency detected: {input_check.emergency_type}")

        cache_key = self._cache_key(
            effective_question,
            use_rag,
            response_variant,
            effective_user_context,
            preferred_language or "auto",
        )
        if not disable_cache and not has_prior_context and not input_check.is_emergency:
            cached = self._get_cached_response(cache_key)
            if cached is not None:
                cached.session_id = session_id
                logger.info("Serving cached response for repeated query")
                return cached

        try:
            if use_rag and vector_store_service.get_total_chunks() > 0:
                logger.info(f"RAG query: '{effective_question[:80]}...'")

                # Get source documents for citation
                source_docs = self._retrieve_with_guardrail(
                    effective_question, mode="query", language=preferred_language
                )
                
                # Granular logging for RAG retrieval
                logger.info(f"RAG retrieved {len(source_docs)} chunks for query")
                for i, doc in enumerate(source_docs):
                    relevance = doc.metadata.get("relevance", "N/A")
                    filename = doc.metadata.get("filename", "Unknown")
                    logger.debug(f"Chunk {i+1}: Source={filename}, Relevance={relevance}, Content Preview='{doc.page_content[:100]}...'")

                sources = []
                for doc in source_docs:
                    fn = doc.metadata.get("filename", "Unknown")
                    rel = doc.metadata.get("relevance")
                    trace = resolve_traceability(fn)
                    sources.append(
                        SourceDocument(
                            content=doc.page_content[:200],
                            source=fn,
                            page=doc.metadata.get("page"),
                            score=rel,
                            relevance=rel,
                            authority=self._authority_from_source(fn),
                            guideline_ref=trace.get("guideline_ref"),
                            guideline_url=trace.get("guideline_url"),
                            source_version=trace.get("source_version"),
                        )
                    )
                sources.sort(key=lambda s: (s.relevance or 0.0), reverse=True)

                # Simulate the prompt for explainability UI
                context_str = "\n\n---\n\n".join([f"[Source: {d.source}]\n{d.content}" for d in sources])
                prompt_used = RAG_SYSTEM_PROMPT.format(
                    chat_history=chat_history_str,
                    response_style=response_variant,
                    user_context=effective_user_context or "None",
                    preferred_language=preferred_language or "auto",
                    context=context_str,
                    question=effective_question
                )

                # Run RAG chain with retries/timeouts.
                response_text = await self._invoke_chain_with_retries(
                    self._rag_chain,
                    {
                        "question": effective_question,
                        "chat_history": chat_history_str,
                        "user_context": effective_user_context or "None",
                        "response_style": response_variant,
                        "preferred_language": preferred_language or "auto",
                    },
                )
            else:
                logger.info(f"Standalone query: '{effective_question[:80]}...'")
                prompt_used = STANDALONE_PROMPT.format(
                    chat_history=chat_history_str,
                    user_context=effective_user_context or "None",
                    response_style=response_variant,
                    preferred_language=preferred_language or "auto",
                    question=effective_question
                )

                response_text = await self._invoke_chain_with_retries(
                    self._standalone_chain,
                    {
                        "question": effective_question,
                        "chat_history": chat_history_str,
                        "user_context": effective_user_context or "None",
                        "response_style": response_variant,
                        "preferred_language": preferred_language or "auto",
                    },
                )

            if use_rag and vector_store_service.get_total_chunks() > 0 and not sources:
                CHAT_ZERO_SOURCE_EVENTS_TOTAL.labels(mode="query", phase="response_no_sources").inc()

                response_text = await self._invoke_chain_with_retries(
                    self._standalone_chain,
                    {
                        "question": effective_question,
                        "chat_history": chat_history_str,
                        "user_context": effective_user_context or "None",
                        "response_style": response_variant,
                        "preferred_language": preferred_language or "auto",
                    },
                )

        except Exception as e:
            logger.error(f"Error during query: {e}", exc_info=True)
            analytics_service.increment_counter("provider_failures")
            CHAT_PROVIDER_FAILURES.inc()
            error_text = str(e).lower()
            if any(keyword in error_text for keyword in ["timeout", "rate", "429", "api", "connect", "service", "503"]):
                response_text = (
                    "I am temporarily unable to reach the AI model provider. "
                    "Please try again in a moment."
                )
                prompt_used = (
                    "[Explainability Unavailable]\n\n"
                    f"The LLM provider returned a transient error:\n{str(e)}\n\n"
                    "RAG retrieval may have succeeded, but the model could not generate a response.\n"
                    "Retry your query — the knowledge base is still available."
                )
            else:
                response_text = (
                    "I encountered an error processing your question. "
                    "Please try again or rephrase your question."
                )
                prompt_used = (
                    "[Explainability Unavailable]\n\n"
                    f"An unexpected error occurred during generation:\n{str(e)}\n\n"
                    "The question was received and processed up to the point of LLM invocation.\n"
                    "Please rephrase your question or try again."
                )

        # Ensure response_text is a string
        if not isinstance(response_text, str):
            response_text = str(response_text)

        # If provider/local-model output is generic, answer directly from retrieved sources.
        lower_response = response_text.lower()
        model_unavailable_markers = (
            "temporarily unable to reach the ai model provider",
            "encountered an error processing your question",
            "couldn't generate a reliable answer",
        )
        needs_extractive_fallback = self._is_local_fallback_response(response_text) or any(
            marker in lower_response for marker in model_unavailable_markers
        )
        if needs_extractive_fallback and sources:
            extractive = self._build_extractive_answer_from_sources(question, sources)
            if extractive:
                response_text = extractive

        # 2. SAFETY CHECK — scan model output for harmful content
        output_check = safety_layer.check_model_output(response_text)
        if not output_check.is_safe:
            response_text = output_check.modified_response or response_text
            safety_flagged = True

        # 2a. Response cleanup — remove repeated points and enforce concise default style.
        response_text = self._sanitize_response(question, response_text)

        skip_quality_filters = self._is_local_fallback_response(response_text)

        # 2b. Quality check — reject obviously off-topic or hallucinated answers.
        if not skip_quality_filters and not self._is_response_relevant(effective_question, response_text, sources):
            logger.warning(
                "Low-relevance answer detected for question '%s'; substituting safe fallback.",
                effective_question[:80],
            )
            extractive = self._build_extractive_answer_from_sources(question, sources)
            if extractive:
                response_text = extractive
            else:
                response_text = self._build_safe_fallback_response(question)
            analytics_service.increment_counter("fallback_responses")
            CHAT_FALLBACK_RESPONSES.inc()

        faithfulness_score = self._source_faithfulness_score(response_text, sources)
        avg_relevance = round(
            sum((s.relevance or 0.0) for s in sources) / max(1, len(sources)),
            3,
        )
        citation_quality = self._citation_quality_label(avg_relevance, faithfulness_score, len(sources))
        for source in sources:
            source.citation_quality = citation_quality

        if not skip_quality_filters and sources and faithfulness_score < 0.12:
            logger.warning(
                "Low faithfulness score %.3f for question '%s'; using safe fallback.",
                faithfulness_score,
                question[:80],
            )
            extractive = self._build_extractive_answer_from_sources(question, sources)
            if extractive:
                response_text = extractive
            else:
                response_text = self._build_safe_fallback_response(question)
            analytics_service.increment_counter("fallback_responses")
            CHAT_FALLBACK_RESPONSES.inc()
            faithfulness_score = self._source_faithfulness_score(response_text, sources)
            citation_quality = self._citation_quality_label(avg_relevance, faithfulness_score, len(sources))

        # 3. Add medical disclaimer
        disclaimer = safety_layer.add_disclaimer("")

        # 4. Explainability — confidence note
        confidence_note = None
        if sources:
            top_sources = ", ".join(
                f"{s.source}({(s.relevance or 0.0):.2f})" for s in sources[:3]
            )
            confidence_note = (
                f"This answer is based on {len(sources)} relevant document(s) "
                f"from the knowledge base. RAG retrieval was used for grounding. "
                f"Faithfulness score: {faithfulness_score:.2f}. "
                f"Citation quality: {citation_quality}. "
                f"Top sources by relevance: {top_sources}."
            )
        else:
            confidence_note = (
                "This answer was generated without document retrieval. "
                "Accuracy may be lower. Consider uploading relevant documents."
            )
            citation_quality = "low"

        # 5. Prepend emergency alert to response if detected
        if emergency_alert:
            response_text = f"{emergency_alert}\n\n---\n\n{response_text}"

        triage = assess_triage(question=question, response=response_text, emergency_alert=emergency_alert)
        triage_level = triage["level"]
        triage_reason = triage["reason"]
        escalation_action = triage["action"]
        triage_rule_id = triage["rule_id"]
        triage_ruleset_version = triage["ruleset_version"]
        urgency_explanation, next_actions = self._build_action_card(
            triage_level=triage_level,
            triage_reason=triage_reason,
            escalation_action=escalation_action,
        )

        # Add to chat history
        self._chat_history[session_id].append({"role": "user", "content": question})
        self._chat_history[session_id].append({"role": "assistant", "content": response_text})

        if len(self._chat_history[session_id]) > 40:
            self._chat_history[session_id] = self._chat_history[session_id][-40:]

        # LRU-style session eviction to prevent unbounded memory growth
        if len(self._chat_history) > self._max_sessions:
            oldest_session = next(iter(self._chat_history))
            self._chat_history.pop(oldest_session, None)
            logger.debug("Evicted oldest chat session to stay under %d limit", self._max_sessions)

        final_response = ChatResponse(
            response=response_text.strip(),
            sources=sources,
            model_used=settings.llm_model,
            provider=settings.llm_provider,
            timestamp=datetime.now(UTC),
            rag_enabled=use_rag and len(sources) > 0,
            session_id=session_id,
            safety_flagged=safety_flagged,
            emergency_alert=emergency_alert,
            safety_disclaimer=disclaimer.strip(),
            confidence_note=confidence_note,
            prompt_used=prompt_used,
            faithfulness_score=faithfulness_score,
            ab_variant=response_variant,
            escalation_action=escalation_action,
            triage_level=triage_level,
            triage_reason=triage_reason,
            citation_quality=citation_quality,
            personalization_applied=personalization_applied or bool(effective_user_context),
            triage_rule_id=triage_rule_id,
            triage_ruleset_version=triage_ruleset_version,
            urgency_explanation=urgency_explanation,
            next_actions=next_actions,
        )

        if not disable_cache and not has_prior_context and not safety_flagged and not emergency_alert:
            self._store_cached_response(cache_key, final_response)

        return final_response


    async def astream_query(
        self,
        question: str,
        session_id: str = "default",
        use_rag: bool = True,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        user_context: str = "",
        db: Session | None = None,
        user_id: int | None = None,
        response_variant: str = "control",
        preferred_language: str | None = None,
        personalization_applied: bool = False,
    ):
        """
        Async generator for streaming RAG responses.
        Yields dictionaries representing SSE events.
        """
        import json

        if not self._initialized:
            self.initialize()

        if session_id not in self._chat_history:
            self._chat_history[session_id] = []

        effective_user_context = (user_context or "").strip()
        if db is not None and user_id is not None:
            try:
                from app.services.user_service import user_service
                persisted_profile_context = user_service.get_personalization_context(db, user_id)
                if persisted_profile_context:
                    persisted_profile_context = persisted_profile_context.strip()
                    if effective_user_context:
                        if persisted_profile_context not in effective_user_context:
                            effective_user_context = f"{persisted_profile_context}\n{effective_user_context}"
                    else:
                        effective_user_context = persisted_profile_context
            except Exception as exc:
                logger.warning("Could not inject persisted profile context: %s", exc)

        effective_question = self._resolve_effective_question(question, session_id)
        chat_history_str = self._get_history_str(session_id)
        
        sources = []
        emergency_alert = None
        safety_flagged = False

        # 1. SAFETY CHECK (Input)
        input_check = safety_layer.check_user_input(question)
        if input_check.is_emergency:
            emergency_alert = input_check.warning_message
            logger.warning(f"Emergency detected: {input_check.emergency_type}")
            yield {"event": "emergency", "data": emergency_alert}

        # Yield initial metadata (sources, disclaimer)
        disclaimer = safety_layer.add_disclaimer("")
        yield {"event": "metadata", "data": json.dumps({"safety_disclaimer": disclaimer.strip()})}

        full_response = ""
        try:
            if use_rag and vector_store_service.get_total_chunks() > 0:
                logger.info(f"RAG streaming query: '{effective_question[:80]}...'")
                source_docs = self._retrieve_with_guardrail(
                    effective_question, mode="stream", language=preferred_language
                )
                
                # Granular logging for RAG retrieval
                logger.info(f"RAG retrieved {len(source_docs)} chunks for streaming query")
                for i, doc in enumerate(source_docs):
                    relevance = doc.metadata.get("relevance", "N/A")
                    filename = doc.metadata.get("filename", "Unknown")
                    logger.debug(f"Chunk {i+1}: Source={filename}, Relevance={relevance}, Content Preview='{doc.page_content[:100]}...'")

                sources = [
                    SourceDocument(
                        content=doc.page_content[:200],
                        source=doc.metadata.get("filename", "Unknown"),
                        page=doc.metadata.get("page"),
                        score=doc.metadata.get("relevance"),
                        relevance=doc.metadata.get("relevance"),
                        authority=self._authority_from_source(doc.metadata.get("filename", "Unknown"))
                    ) for doc in source_docs
                ]
                sources.sort(key=lambda s: (s.relevance or 0.0), reverse=True)
                
                yield {"event": "sources", "data": json.dumps([s.model_dump() for s in sources])}
                
                context_str = "\n\n---\n\n".join([f"[Source: {d.source}]\n{d.content}" for d in sources])
                payload = {
                    "question": effective_question,
                    "chat_history": chat_history_str,
                    "user_context": effective_user_context or "None",
                    "response_style": response_variant,
                    "preferred_language": preferred_language or "auto",
                    "context": context_str
                }
                async for chunk in self._rag_chain.astream(payload):
                    token = chunk if isinstance(chunk, str) else chunk.content
                    full_response += token
                    yield {"event": "token", "data": token}
            else:
                yield {"event": "sources", "data": "[]"}
                payload = {
                    "question": effective_question,
                    "chat_history": chat_history_str,
                    "user_context": effective_user_context or "None",
                    "response_style": response_variant,
                    "preferred_language": preferred_language or "auto",
                }
                async for chunk in self._standalone_chain.astream(payload):
                    token = chunk if isinstance(chunk, str) else chunk.content
                    full_response += token
                    yield {"event": "token", "data": token}

            if use_rag and vector_store_service.get_total_chunks() > 0 and not sources:
                CHAT_ZERO_SOURCE_EVENTS_TOTAL.labels(mode="stream", phase="response_no_sources").inc()

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            analytics_service.increment_counter("provider_failures")
            CHAT_PROVIDER_FAILURES.inc()
            fallback_text = self._build_safe_fallback_response(question)
            for word in fallback_text.split(" "):
                yield {"event": "token", "data": word + " "}
            full_response = fallback_text

        # 2. Post-generation safety checks
        output_check = safety_layer.check_model_output(full_response)
        if not output_check.is_safe:
            full_response = output_check.modified_response or full_response
            safety_flagged = True
            yield {"event": "safety_flag", "data": "Output was modified for safety."}

        # 3. Assess triage
        triage = assess_triage(question=question, response=full_response, emergency_alert=emergency_alert)
        
        # Save to history
        self._chat_history[session_id].append({"role": "user", "content": question})
        self._chat_history[session_id].append({"role": "assistant", "content": full_response})
        if len(self._chat_history[session_id]) > 40:
            self._chat_history[session_id] = self._chat_history[session_id][-40:]

        yield {"event": "done", "data": json.dumps({
            "session_id": session_id,
            "triage_level": triage["level"],
            "triage_reason": triage["reason"],
            "escalation_action": triage["action"],
            "safety_flagged": safety_flagged,
            "full_response": full_response
        })}

    def get_history(self, session_id: str) -> list[dict]:
        """Get current chat history for a session."""
        return self._chat_history.get(session_id, []).copy()

    def clear_history(self, session_id: str):
        """Clear chat history for a session."""
        if session_id in self._chat_history:
            self._chat_history[session_id].clear()
            logger.info(f"Chat history cleared for {session_id}")

    def is_ready(self) -> bool:
        """Check if the RAG service is initialized."""
        return self._initialized


# Singleton instance
rag_service = RAGService()
