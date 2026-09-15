# Design Decisions

This document records the reasoning behind the four most significant architectural choices in
HealthBuddy AI. It is written in first person so that I can defend each decision out loud — the
intent is not to make the project sound bigger than it is, but to make the thinking legible.

---

## 1. Deterministic Triage Ruleset Instead of an ML Classifier

The triage engine (`app/services/triage_rules.py`) is a set of versioned regex patterns that
assign an urgency level — `emergency`, `urgent`, or `self_care` — to every conversation turn.
It runs in under a millisecond. A trained classifier could not.

The first reason I went deterministic is straightforward: **I had no labeled clinical triage
dataset to train a classifier on**. Building a reliable ML triage model requires annotated
examples of real patient queries with ground-truth severity labels — ideally reviewed by
clinicians. I didn't have that, and I wasn't willing to train on a proxy dataset and claim
clinical validity I couldn't demonstrate. A rule-based system with clearly stated coverage limits
is more honest than a model whose failure modes are opaque.

The second reason is that in a safety-critical context, **auditable and explainable matters more
than raw accuracy**. A clinician or a legal reviewer can open `triage_rules.py` and read exactly
which pattern triggered an escalation, what the prescribed action is, and which ruleset version
produced the result. Every response carries the version string `clinician-v1.1`. You cannot hand
that transparency to a neural network — if a classifier fires on a false positive or misses a
cardiac alert, the only explanation is "the model assigned a low probability." That is not a
defensible answer in a health context.

The third reason is determinism itself: for any given input, the triage result is always the
same. An LLM or probabilistic classifier can weight surrounding context, phrasing, and tone in
ways that suppress a safety flag. For a cardiac event, a false negative isn't a degraded user
experience — it's potentially fatal latency. I was not willing to trade that guarantee for
higher F1 on a benchmark.

I'm aware of the coverage tradeoff. Regex patterns miss paraphrases — someone describing a
cardiac emergency as "my left arm feels like it's been run over by a truck and I can't catch my
breath" will not trigger `EMERG_CARDIO_RESP`. The safety layer (`safety_layer.py`) partially
mitigates this with a broader overlapping keyword set. But I would not claim the coverage is
complete. A production medical system would layer this with a fine-tuned intent classifier
trained on real crisis conversation datasets; the deterministic ruleset would still run first as
a guaranteed floor.

---

## 2. How the Emergency Archetypes Were Chosen

The six archetypes in `safety_layer.py` — cardiac arrest, stroke, respiratory failure, mental
health/suicide crisis, acute poisoning, and severe bleeding — evolved from WHO and NIH emergency
categorisation guidelines, adapted to this project's scope. They were not invented from scratch;
they represent the categories where time-to-intervention is the primary determinant of outcome
and where a layperson is most likely to mishandle the situation as a "Google it" problem rather
than calling emergency services immediately.

These categories map directly to the "golden hour" and "chain of survival" concepts in emergency
medicine. For cardiac events, the intervention window is minutes — the evidence on bystander CPR
and defibrillation response times is unambiguous. For stroke, the tPA treatment window is
3–4.5 hours from symptom onset, which means the moment a user types "face drooping and slurred
speech," the clock is already running. For poisoning, Poison Control's advice varies by substance
and time since ingestion — but the first action is always to call, not to wait and see.

Mental health crisis was treated as equally time-sensitive. Early chatbot safety research (before
ChatGPT-era systems) documented cases where conversational AI engaged with suicidal ideation as
though it were a general-topic query. I did not want to build another system that does that. The
crisis archetype fires before any RAG or LLM call is made; the user receives the Suicide
Prevention Lifeline numbers immediately, not as an afterthought appended to a generated response.

The set is deliberately narrow — six archetypes rather than twenty — because I prioritised
precision over recall on the patterns I included. A false positive (showing an emergency overlay
for a non-emergency query) erodes user trust and trains people to dismiss the overlay; a false
negative can cost a life. I biased toward precision with the understanding that the broader safety
layer keyword sets (`HARMFUL_PATTERNS`, `NON_DIAGNOSTIC_BOUNDARY_PATTERNS`) catch a wider range
of concerning content without triggering the full emergency overlay.

---

## 3. pgvector vs ChromaDB — When Each Is Used

The vector store (`app/services/vector_store.py`) initialises against pgvector if
`VECTOR_STORE_TYPE=pgvector` is set and the database URL points to PostgreSQL; otherwise it falls
back to ChromaDB. Both use the same LangChain interface, so the RAG pipeline does not change
between environments.

**Why ChromaDB for local development:** ChromaDB runs as a persistent in-process client with no
external dependencies. A developer can clone the repo, set a Groq API key, and have a working
vector search without provisioning a database server. That matters for the Quick Start experience.
ChromaDB's weakness in this project is operational — there is no built-in replication, no
connection pool, and its on-disk format is opaque compared to SQL. For a single-process dev
server those weaknesses are irrelevant.

**Why pgvector for production:** When you are already running PostgreSQL (which you have to for
user accounts, chat logs, and session data), adding pgvector costs one SQL extension and one
`CREATE TABLE` call. You get ACID transactions, connection pooling via `pool_size`/`max_overflow`
in the engine config, and the ability to run `DELETE FROM langchain_pg_embedding WHERE
cmetadata->>'doc_id' = $1` as a plain SQL statement that participates in the same transaction as
a user's data deletion. That last point matters for GDPR: when a user requests account deletion,
their uploaded document chunks can be removed atomically alongside their profile. With ChromaDB,
the deletion is a separate call with no transactional guarantee.

The limitation of pgvector in this project is that I am using the LangChain community wrapper
(`langchain_community.vectorstores.PGVector`), which manages its own table schema
(`langchain_pg_embedding`). That schema is outside my Alembic control, meaning if LangChain
changes the schema in a future version, upgrades require manual intervention. A more robust
implementation would own the embedding table schema directly.

---

## 4. What the Moderation Layer Actually Checks

The `SafetyLayer` class in `app/services/safety_layer.py` runs two distinct passes with different
purposes.

**Input moderation (`check_user_input`)** scans the user's raw message for the six emergency
archetypes described above. If any pattern matches, the function returns an `is_emergency=True`
result immediately — no LLM call is made, no RAG retrieval happens. The emergency message is
assembled from hardcoded, clinically reviewed text and returned directly. This is a deliberate
design: I do not want the LLM to be involved in the emergency response path at all. An LLM could
rephrase, soften, add caveats, or in a worst-case hallucination scenario, provide incorrect
first-aid steps. The hardcoded messages are wrong in some edge cases but they are consistently
safe.

**Output moderation (`check_model_output`)** scans the LLM's generated response for two pattern
classes. The first is `HARMFUL_PATTERNS` — things like dosage-specific instructions, advice to
self-medicate with opioids, or instructions to stop prescribed medication. If any of these match,
the entire generated response is discarded and replaced with a standardised refusal message. The
second is `NON_DIAGNOSTIC_BOUNDARY_PATTERNS` — phrases like "you have cancer" or "I diagnose."
If those match, the response is replaced with a message redirecting to a healthcare provider.

The distinction between the two pass types matters: input moderation decides whether to proceed
with generation at all; output moderation is a post-generation safety net that catches cases where
the LLM's instruction-following fails. In practice, the RAG system prompt already forbids
diagnosis and dosage recommendations, so output moderation mostly catches edge cases — but I
wanted a deterministic backstop that does not depend on the model following its instructions
correctly.

What the moderation layer does **not** do: it does not perform semantic analysis, it does not use
a separate classifier, and it does not have coverage for all harmful health advice (there are many
ways to phrase dangerous recommendations that would pass the current regex patterns). In a
production medical application this layer would need to be significantly more sophisticated —
likely a dedicated content-safety model trained on adversarial medical queries.

---

*Last updated: September 2026. Ruleset version: clinician-v1.1.*
