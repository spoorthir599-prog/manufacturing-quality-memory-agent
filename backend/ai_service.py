"""
AI Service — Azure OpenAI with graceful local fallback.
Handles embeddings, chat completions, and similarity search.
"""
from __future__ import annotations
import json
import logging
import math
import hashlib
from typing import Optional
import numpy as np
from config import settings

logger = logging.getLogger(__name__)

# ── Embedding helpers ──────────────────────────────────────────────────────────

def _local_embedding(text: str, dim: int = 1536) -> list[float]:
    """
    Deterministic pseudo-embedding based on text hash.
    Produces a unit-normalised float vector — good enough for demo cosine search.
    """
    h = hashlib.sha256(text.encode()).digest()
    # Extend hash to fill dim dimensions deterministically
    rng = np.random.default_rng(int.from_bytes(h[:4], "big"))
    vec = rng.standard_normal(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    # Add word-level signal so similar texts get closer vectors
    words = set(text.lower().split())
    for i, w in enumerate(sorted(words)):
        idx = int(hashlib.md5(w.encode()).hexdigest(), 16) % dim
        vec[idx] += 0.3
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


async def get_embedding(text: str) -> list[float]:
    """Return an embedding vector for the given text."""
    if settings.azure_available:
        try:
            from openai import AsyncAzureOpenAI
            client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            response = await client.embeddings.create(
                model=settings.azure_openai_embedding_deployment,
                input=text[:8000],
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Azure embedding failed, falling back to local: {e}")

    return _local_embedding(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


# ── Chat completion ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the Manufacturing Quality Memory Agent — an AI assistant for industrial quality engineers.

Your role:
1. Help engineers investigate production defects by analysing historical quality data.
2. Identify patterns, recurring defects, probable root causes and previous corrective actions.
3. NEVER invent historical incidents, measurements, root causes or corrective actions.
4. If there is insufficient historical evidence, explicitly state: "Insufficient historical evidence to determine this."
5. Always distinguish clearly between: HISTORICAL EVIDENCE (from the database) and AI ANALYSIS (your interpretation).
6. Reference incident IDs (e.g. QIR-1023) for every factual claim.
7. Be concise, precise and structured — you are assisting a quality engineer, not a general user.

Output format guidelines:
- Use markdown headers and bullet points.
- Label sections: HISTORICAL EVIDENCE, AI ANALYSIS, RECOMMENDED INVESTIGATION, SOURCES.
- Keep responses focused on quality engineering.
"""


async def chat_completion(
    messages: list[dict],
    context_incidents: list[dict] | None = None,
    temperature: float = 0.2,
) -> str:
    """Generate an AI response grounded in the provided incident context."""

    # Build context block
    context_block = ""
    if context_incidents:
        context_block = "\n\n### HISTORICAL QUALITY MEMORY — Retrieved Incidents:\n"
        for inc in context_incidents[:12]:
            context_block += f"""
---
**{inc.get('incident_id', 'N/A')}** | {inc.get('title', '')}
- Date: {inc.get('occurred_at', 'N/A')}
- Line: {inc.get('production_line', 'N/A')} | Machine: {inc.get('machine', 'N/A')}
- Product: {inc.get('product', 'N/A')} | Severity: {inc.get('severity', 'N/A')}
- Defect Category: {inc.get('defect_category', 'N/A')}
- Description: {inc.get('description', '')}
- Inspection Findings: {inc.get('inspection_findings', 'None')}
- Root Causes: {inc.get('root_causes', 'None')}
- Corrective Actions: {inc.get('corrective_actions', 'None')}
- Status: {inc.get('status', 'N/A')}
- Similarity Score: {inc.get('similarity_score', 0):.2f}
"""
        context_block += "\n---\n"
        context_block += "\nUse ONLY the incidents above as historical evidence. Do not invent additional incidents.\n"

    system_content = SYSTEM_PROMPT
    if context_block:
        system_content += context_block

    full_messages = [{"role": "system", "content": system_content}] + messages

    if settings.azure_available:
        try:
            from openai import AsyncAzureOpenAI
            client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            response = await client.chat.completions.create(
                model=settings.azure_openai_deployment_name,
                messages=full_messages,
                temperature=temperature,
                max_tokens=1500,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"Azure chat failed, using local fallback: {e}")

    return _local_chat_response(messages, context_incidents)


def _local_chat_response(messages: list[dict], context_incidents: list[dict] | None) -> str:
    """Structured local response when Azure is unavailable."""
    user_q = messages[-1]["content"] if messages else ""

    if not context_incidents:
        return (
            "## HISTORICAL EVIDENCE\n\nNo sufficiently similar historical incidents were found "
            "in the quality memory database for this query.\n\n"
            "## AI ANALYSIS\n\nInsufficient historical evidence to determine root cause or "
            "provide pattern analysis.\n\n"
            "## RECOMMENDED INVESTIGATION\n\n"
            "1. Create a new quality incident record with full details.\n"
            "2. Conduct inspection and document findings.\n"
            "3. This will become the first data point for future pattern detection."
        )

    inc = context_incidents[0]
    count = len(context_incidents)
    lines_set = set(i.get("production_line", "") for i in context_incidents if i.get("production_line"))
    machines_set = set(i.get("machine", "") for i in context_incidents if i.get("machine"))
    rcs = [i.get("root_causes", "") for i in context_incidents if i.get("root_causes")]
    cas = [i.get("corrective_actions", "") for i in context_incidents if i.get("corrective_actions")]
    ids = [i.get("incident_id", "") for i in context_incidents]

    return f"""## HISTORICAL EVIDENCE

**{count} similar historical incident(s) found** in the quality memory database.

**Most relevant:** {inc.get('incident_id')} — {inc.get('title')}

| Attribute | Details |
|-----------|---------|
| Production Lines | {', '.join(lines_set) or 'Various'} |
| Machines | {', '.join(list(machines_set)[:3]) or 'Various'} |
| Defect Category | {inc.get('defect_category', 'N/A')} |
| Severity Range | Mixed |

**Common inspection findings:** {context_incidents[0].get('inspection_findings', 'See source records')}

**Known root causes:** {rcs[0] if rcs else 'See source records'}

**Previous corrective actions:** {cas[0] if cas else 'See source records'}

---

## AI ANALYSIS

Based on {count} retrieved incidents, a recurring pattern is present involving **{inc.get('defect_category', 'this defect type')}**.
The most common machines affected: {', '.join(list(machines_set)[:3]) or 'various'}.

> ⚠️ This analysis is grounded exclusively in historical records retrieved above. No additional incidents have been assumed.

---

## RECOMMENDED INVESTIGATION

1. Review the source incident records listed below.
2. Verify current machine calibration and process parameters.
3. Compare current measurements with historical deviations.
4. Check if the same corrective actions were previously applied.

---

## SOURCES

{chr(10).join(f'- {i}' for i in ids[:10])}
"""
