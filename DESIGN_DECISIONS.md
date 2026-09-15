# Design Decisions

This document records the reasoning behind the four most significant architectural choices in
HealthBuddy AI. It is written in first person so that I can defend each decision out loud — the
intent is not to make the project sound bigger than it is, but to make the thinking legible.

---

## 1. Deterministic Triage Ruleset Instead of an ML Classifier

The triage engine (`app/services/triage_rules.py`) is a set of versioned regex patterns that
assign an urgency level — `emergency`, `urgent`, or `self_care` — to every conversation turn.
It runs in under a millisecond. A trained classifier could not.

The core reason I went deterministic here is that **a safety-critical path cannot tolerate
hallucinated decisions**. If I handed triage to an LLM or a probabilistic classifier, I would
have no guarantee that a query containing "chest pain" would ever be classified as an emergency.
The model might weight context, tone, or surrounding text in ways that suppress the flag. For a
cardiac event, that kind of false negative isn't a degraded user experience — it's a potentially
fatal latency. I was not willing to accept that.

The secondary reason is interpretability. A clinician or a legal reviewer can read the ruleset in
`triage_rules.py` and understand exactly what triggers an escalation, what the escalation action
is, and which ruleset version produced it. Every response carries the version string
`clinician-v1.1`. You cannot hand that document to a clinician and ask them to audit a neural
network.

I'm aware of the tradeoffs. Regex patterns miss paraphrases — someone describing a cardiac
emergency as "my left arm feels like it's been run over by a truck and I can't catch my breath"
will not trigger `EMERG_CARDIO_RESP`. The safety layer (`safety_layer.py`) partially mitigates
this with a broader and overlapping keyword set that runs in parallel. But I would not claim the
coverage is complete. A production medical system would layer this with a fine-tuned intent
classifier trained on actual crisis conversation datasets; for a portfolio application where I had
neither the dataset nor the clinical validation infrastructure, a transparent, auditable ruleset
was the responsible choice.

---

## 2. How the Emergency Archetypes Were Chosen

The six archetypes in `safety_layer.py` — cardiac arrest, stroke, respiratory failure, mental
health/suicide crisis, acute poisoning, and severe bleeding — are not arbitrary. I started from
the WHO and NIH literature on the top causes of preventable death where **time-to-intervention is
the primary determinant of outcome**. These categories map directly to the "golden hour" and
"chain of survival" concepts in emergency medicine: each one has a well-established window within
which calling emergency services changes the outcome from death or permanent disability to
survival.

For cardiac events, that window is minutes — the evidence on bystander CPR and defibrillation
response times is clear. For stroke, the tPA treatment window is 3–4.5 hours from symptom onset,
which means the moment a user types "face drooping and slurred speech," the clock is already
running. For poisoning, Poison Control's advice changes depending on the substance and time since
ingestion — but the first action is always to call, not to wait and see.

Mental health crisis was treated as equally critical. Early chatbot safety research (before
ChatGPT-era systems) documented cases where conversational AI engaged with suicidal ideation as
though it were a general-topic query. I did not want to build another system that does that. The
crisis archetype fires before any RAG or LLM call is made; the user gets the Suicide Prevention
Lifeline numbers immediately, not as an afterthought at the bottom of a generated response.

The set is deliberately narrow — six archetypes instead of twenty — because I wanted high
precision on the patterns I included rather than noisy recall across a long list. A false positive
(showing an emergency overlay for a non-emergency) erodes trust and trains users to dismiss the
overlay; a false negative can cost a life. I biased toward precision with the understanding that
the broader safety layer keyword set (`HARMFUL_PATTERNS`, `NON_DIAGNOSTIC_BOUNDARY_PATTERNS`)
catches a wider range of concerning content without triggering the full emergency overlay.

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
