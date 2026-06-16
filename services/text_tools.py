import re
from typing import Literal

from app.config import settings

Mode = Literal["shorten", "rewrite", "headline"]

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "was", "are", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "that",
    "this", "these", "those", "it", "its", "they", "them", "their", "he", "she", "his",
    "her", "we", "our", "you", "your", "i", "my", "me", "not", "no", "so", "if", "than",
    "then", "also", "into", "about", "over", "after", "before", "during", "while", "when",
    "where", "which", "who", "whom", "what", "how", "why", "said", "says", "say",
}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _extractive_shorten(text: str, ratio: float = 0.45) -> str:
    cleaned = _clean_text(text)
    sentences = _split_sentences(cleaned)
    if len(sentences) <= 2 or len(cleaned.split()) <= 40:
        return cleaned

    words = re.findall(r"\b[a-zA-Z]{3,}\b", cleaned.lower())
    freq: dict[str, int] = {}
    for word in words:
        if word not in STOP_WORDS:
            freq[word] = freq.get(word, 0) + 1

    def score(sentence: str, index: int) -> float:
        tokens = re.findall(r"\b[a-zA-Z]{3,}\b", sentence.lower())
        content = [t for t in tokens if t not in STOP_WORDS]
        keyword_score = sum(freq.get(t, 0) for t in content)
        length_penalty = abs(len(sentence.split()) - 18) * 0.15
        position_bonus = max(0, 3 - index) * 1.5
        return keyword_score + position_bonus - length_penalty

    ranked = sorted(enumerate(sentences), key=lambda pair: score(pair[1], pair[0]), reverse=True)
    keep_count = max(2, int(len(sentences) * ratio))
    keep_indices = sorted(idx for idx, _ in ranked[:keep_count])
    result = " ".join(sentences[i] for i in keep_indices)
    return result or cleaned


def _to_headline(text: str, max_words: int = 8) -> str:
    """Compress text into a short overlay headline."""
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    sentences = _split_sentences(cleaned)
    lead = sentences[0] if sentences else cleaned

    # Drop attribution tails common in tweet copy.
    lead = re.split(r"\s+[-–—]\s+|\s+via\s+@", lead, maxsplit=1, flags=re.I)[0]
    lead = re.sub(r"https?://\S+", "", lead).strip()
    lead = re.sub(r"^(BREAKING|JUST IN|UPDATE|WATCH|VIDEO|NEW)\s*[:.\-–—]?\s*", "", lead, flags=re.I)

    words = re.findall(r"[\w']+|[%$€£]\d[\d,.]*|\d[\d,.]*%?", lead)
    if not words:
        return cleaned[:80]

    stop_tail = {
        "said", "says", "after", "before", "during", "while", "that", "which", "who",
        "on", "at", "in", "near", "according", "local", "officials", "evening", "morning",
    }
    picked: list[str] = []
    for word in words:
        if len(picked) >= max_words:
            break
        if len(picked) >= 4 and word.lower() in stop_tail:
            break
        picked.append(word)

    headline = " ".join(picked)
    if headline and headline[0].islower():
        headline = headline[0].upper() + headline[1:]
    if headline and headline[-1] in ",;:":
        headline = headline[:-1]

    return headline or cleaned[:80]


def _rule_rewrite(text: str) -> str:
    """Lightweight offline rewrite when no LLM key is configured."""
    cleaned = _clean_text(text)
    replacements = [
        (r"\bsaid\b", "stated"),
        (r"\baccording to\b", "per"),
        (r"\bvery\b", ""),
        (r"\breally\b", ""),
        (r"\ba lot of\b", "many"),
        (r"\bbecause\b", "as"),
        (r"\bhowever\b", "yet"),
        (r"\balso\b", "additionally"),
        (r"\bpeople\b", "individuals"),
        (r"\bgovernment\b", "authorities"),
        (r"\bshowed\b", "revealed"),
        (r"\bannounced\b", "confirmed"),
    ]
    result = cleaned
    for pattern, repl in replacements:
        result = re.sub(pattern, repl, result, flags=re.I)
    result = re.sub(r"\s{2,}", " ", result).strip()
    return result


async def _llm_transform(text: str, mode: Mode) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    if mode == "shorten":
        instruction = (
            "Shorten the following journalist draft. Keep all key facts, names, dates, and quotes. "
            "Remove filler and redundancy. Return only the shortened text."
        )
    elif mode == "headline":
        instruction = (
            "Turn the following text into one brief news headline for a video overlay. "
            "Use 5–12 words. Keep the core fact, place, and who/what. No quotes, no hashtags, no URLs. "
            "Return only the headline."
        )
    else:
        instruction = (
            "Rewrite the following journalist draft in fresh wording while preserving every fact, "
            "name, date, number, and quote meaning. Keep a neutral news tone. Return only the rewritten text."
        )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert news editor for a freelance journalist."},
            {"role": "user", "content": f"{instruction}\n\n---\n{text}"},
        ],
        temperature=0.4,
    )
    return (response.choices[0].message.content or "").strip()


async def transform_text(text: str, mode: Mode) -> dict:
    cleaned = _clean_text(text)
    if not cleaned:
        return {"result": "", "mode": mode, "engine": "none", "original_words": 0, "result_words": 0}

    original_words = len(cleaned.split())

    local_handlers = {
        "shorten": _extractive_shorten,
        "rewrite": _rule_rewrite,
        "headline": _to_headline,
    }

    if settings.openai_api_key:
        try:
            result = await _llm_transform(cleaned, mode)
            engine = "openai"
        except Exception:
            result = local_handlers[mode](cleaned)
            engine = "fallback"
    else:
        result = local_handlers[mode](cleaned)
        engine = "local"

    result_words = len(result.split())
    return {
        "result": result,
        "mode": mode,
        "engine": engine,
        "original_words": original_words,
        "result_words": result_words,
    }
