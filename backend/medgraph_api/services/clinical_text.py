"""Text helpers for clinical documents extracted from PDFs and notes.

PDF extraction keeps hard line wraps, page headers, and template margin notes. These helpers
turn that into clean paragraphs, split them into sentences, track section headings, and rank
passages against a question so summaries and RAG answers quote readable evidence.
"""

import math
import re
from dataclasses import dataclass

BULLET_PATTERN = re.compile(r"^(?:[•▪●‣⁃◦•*]|-(?=\s))\s*")
NUMBERED_ITEM_PATTERN = re.compile(r"^(\d{1,2})[.)]\s+")
PAGE_MARKER_PATTERN = re.compile(r"^(?:sample\s+)?page\s+\d+(?:\s+of\s+\d+)?$", re.IGNORECASE)
PRINTED_BY_PATTERN = re.compile(r"^printed\s+(?:by|on)\b", re.IGNORECASE)
KEY_VALUE_PATTERN = re.compile(r"^(?P<label>[A-Z][A-Za-z0-9 /()&'’,-]{1,60}?):\s+(?P<value>\S.*)$")
SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'“])")
TOKEN_PATTERN = re.compile(r"[a-z]+|\d+(?:\.\d+)?")
SALUTATION_PATTERN = re.compile(r"^Dear\s+[^:]{1,40}:\s*")

ABBREVIATIONS = {"dr.", "mr.", "mrs.", "ms.", "vs.", "e.g.", "i.e.", "st.", "no.", "approx."}
EMPTY_VALUES = {"none", "n/a", "na", "nil", "-"}
TABLE_HEADER_WORDS = {
    "appointment", "comments", "comments/instructions", "date", "instructions", "location",
    "result", "results", "test", "time", "units", "value", "values", "with", "/",
}
STOP_WORDS = {
    "a", "about", "after", "all", "an", "and", "any", "are", "as", "at", "be", "been", "before",
    "but", "by", "can", "did", "do", "does", "during", "for", "from", "had", "has", "have", "he",
    "her", "his", "how", "i", "if", "in", "is", "it", "its", "of", "on", "or", "patient",
    "patients", "she", "should", "tell", "that", "the", "their", "there", "they", "this", "to",
    "was", "were", "what", "when", "where", "which", "who", "would", "you", "your",
}
SYNONYMS = {
    "med": "medication",
    "meds": "medication",
    "drug": "medication",
    "drugs": "medication",
    "rx": "medication",
    "dx": "diagnosis",
    "labs": "lab",
    "admitted": "admission",
    "admit": "admission",
}
# Related terms added to a question at reduced weight so "why admitted" finds the presentation.
QUESTION_EXPANSIONS = {
    "admission": ("presented", "presentation", "complaint", "diagnosis", "reason"),
    "why": ("diagnosis", "due", "secondary", "because", "presented"),
    "medication": ("mg", "tablet", "daily", "started", "po"),
    "follow": ("referral", "referred", "appointment", "repeat", "plan"),
    "diagnosis": ("impression", "assessment", "diagnosed"),
    "lab": ("result", "test", "level"),
    "result": ("lab", "test", "impression"),
    "show": ("impression", "finding", "confirmed", "revealed"),
    "allergy": ("allergic", "reaction"),
}
EXPANSION_WEIGHT = 0.5
HEADING_WEIGHT = 0.75

MARGIN_NOTE_MAX_CHARS = 40
MARGIN_NOTE_MIN_RUN = 6
WRAPPED_LINE_MIN_CHARS = 40


@dataclass(frozen=True)
class ClinicalSection:
    heading: str | None
    lines: list[str]


@dataclass(frozen=True)
class ClinicalPassage:
    text: str
    heading: str | None
    is_list_item: bool
    context: str = ""
    score: float = 0.0
    source_index: int = 0

    def display_text(self) -> str:
        # Short list items ("Tamsulosin 0.4mg po QHS") only make sense with their heading.
        needs_heading = len(self.text) < 80
        if self.heading and needs_heading and not KEY_VALUE_PATTERN.match(self.text):
            return f"{self.heading}: {self.text}"
        return self.text


def clean_clinical_text(text: str) -> str:
    """Remove page furniture and margin notes, then rejoin hard-wrapped lines."""
    lines = [_normalize_line(line) for line in text.splitlines()]
    lines = ["" if _is_page_furniture(line) else line for line in lines]
    lines = _drop_margin_note_runs(lines)
    return "\n".join(_unwrap_lines(lines)).strip()


def normalize_chunk_lines(text: str) -> str:
    """Collapse whitespace within lines but keep line breaks, which mark sentence boundaries."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        merged: list[str] = []
        for piece in SENTENCE_BOUNDARY_PATTERN.split(line):
            if merged and _should_merge_with_previous(merged[-1]):
                merged[-1] = f"{merged[-1]} {piece}"
            else:
                merged.append(piece)
        sentences.extend(piece.strip() for piece in merged if piece.strip())
    return sentences


def is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or is_list_item(stripped):
        return False
    words = stripped.rstrip(":").split()
    if not words or len(words) > 8:
        return False
    if stripped.endswith(":"):
        return True
    first_word_letters = re.sub(r"[^A-Za-z]", "", words[0])
    return len(first_word_letters) >= 4 and first_word_letters.isupper() and ":" not in stripped


def is_list_item(line: str) -> bool:
    stripped = line.strip()
    return bool(BULLET_PATTERN.match(stripped) or NUMBERED_ITEM_PATTERN.match(stripped))


def strip_list_marker(line: str) -> str:
    stripped = NUMBERED_ITEM_PATTERN.sub("", BULLET_PATTERN.sub("", line.strip()), count=1)
    return SALUTATION_PATTERN.sub("", stripped.strip()).strip()


def is_empty_value(value: str) -> bool:
    return value.strip().strip(".").lower() in EMPTY_VALUES


def parse_sections(text: str) -> list[ClinicalSection]:
    sections: list[ClinicalSection] = []
    heading: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if is_heading(stripped):
            if lines or heading is not None:
                sections.append(ClinicalSection(heading=heading, lines=lines))
            heading = stripped.rstrip(":").strip()
            lines = []
        else:
            lines.append(stripped)
    if lines or heading is not None:
        sections.append(ClinicalSection(heading=heading, lines=lines))
    return sections


def parse_key_values(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = KEY_VALUE_PATTERN.match(line.strip())
        if match is None:
            continue
        label = " ".join(match.group("label").lower().split())
        fields.setdefault(label, match.group("value").strip())
    return fields


def stem_terms(text: str) -> set[str]:
    terms = set()
    for token in TOKEN_PATTERN.findall(text.lower()):
        token = SYNONYMS.get(token, token)
        if token in STOP_WORDS or len(token) < 2:
            continue
        terms.add(_stem(token))
    return terms


def iter_passages(
    text: str,
    initial_section: str | None = None,
    source_index: int = 0,
) -> list[ClinicalPassage]:
    """Split text into sentence passages that remember their section heading path."""
    section_path = [part.strip() for part in (initial_section or "").split(">") if part.strip()]
    passages: list[ClinicalPassage] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if is_heading(stripped):
            section_path = _push_heading(section_path, stripped.rstrip(":").strip())
            continue
        item = is_list_item(stripped)
        heading = section_path[-1] if section_path else None
        for sentence in split_sentences(strip_list_marker(stripped)):
            if _is_low_value(sentence):
                continue
            passages.append(
                ClinicalPassage(
                    text=sentence,
                    heading=heading,
                    is_list_item=item,
                    context=" > ".join(section_path),
                    source_index=source_index,
                )
            )
    return passages


def section_path_at(text: str, position: int) -> str | None:
    """Heading path ("DISCHARGE PLAN > New Medications") in effect at a character offset."""
    section_path: list[str] = []
    for line in text[:position].splitlines():
        stripped = line.strip()
        if stripped and is_heading(stripped):
            section_path = _push_heading(section_path, stripped.rstrip(":").strip())
    return " > ".join(section_path) or None


def rank_passages(passages: list[ClinicalPassage], question: str) -> list[ClinicalPassage]:
    """Score passages by question-term overlap, weighting rare terms higher. Best first."""
    question_terms = stem_terms(question)
    if not question_terms or not passages:
        return []
    expansion_terms = _expand_terms(question_terms) - question_terms

    body_terms = [stem_terms(passage.text) for passage in passages]
    context_terms = [stem_terms(passage.context) for passage in passages]
    document_frequency: dict[str, int] = {}
    for terms in body_terms:
        for term in terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1

    def weight(term: str) -> float:
        return math.log(1 + len(passages) / (1 + document_frequency.get(term, 0)))

    ranked = []
    for position, passage in enumerate(passages):
        body, context = body_terms[position], context_terms[position]
        score = sum(weight(term) for term in question_terms & body)
        score += HEADING_WEIGHT * sum(weight(term) for term in question_terms & (context - body))
        score += EXPANSION_WEIGHT * sum(
            weight(term) for term in expansion_terms & (body | context)
        )
        if score > 0:
            ranked.append((score, position, passage))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        ClinicalPassage(
            text=passage.text,
            heading=passage.heading,
            is_list_item=passage.is_list_item,
            context=passage.context,
            score=round(score, 4),
            source_index=passage.source_index,
        )
        for score, _, passage in ranked
    ]


def select_relevant_passages(
    passages: list[ClinicalPassage],
    question: str,
    limit: int,
) -> list[ClinicalPassage]:
    """Top passages for a question, deduplicated, falling back to the first informative one."""
    selected: list[ClinicalPassage] = []
    seen: set[str] = set()
    for passage in rank_passages(passages, question):
        key = passage.text.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(passage)
        if len(selected) >= limit:
            break
    if selected:
        return selected

    # Nothing shares a term with the question: trust retrieval order and quote the first
    # informative sentence of each source instead.
    fallback: list[ClinicalPassage] = []
    seen_sources: set[int] = set()
    for passage in passages:
        if passage.source_index in seen_sources or len(passage.text.split()) < 5:
            continue
        seen_sources.add(passage.source_index)
        fallback.append(passage)
        if len(fallback) >= limit:
            break
    return fallback


def _normalize_line(line: str) -> str:
    normalized = " ".join(line.split())
    if BULLET_PATTERN.match(normalized):
        return BULLET_PATTERN.sub("• ", normalized, count=1)
    return normalized


def _is_page_furniture(line: str) -> bool:
    return bool(PAGE_MARKER_PATTERN.match(line) or PRINTED_BY_PATTERN.match(line))


def _is_margin_note_candidate(line: str) -> bool:
    return (
        0 < len(line) <= MARGIN_NOTE_MAX_CHARS
        and not any(character.isdigit() for character in line)
        and not line.endswith(":")
        and not is_list_item(line)
        and not is_heading(line)
        and not is_empty_value(line)
    )


def _drop_margin_note_runs(lines: list[str]) -> list[str]:
    """Drop long runs of short wrapped fragments, e.g. template guidance in a PDF margin."""
    kept: list[str] = []
    run: list[str] = []

    def flush() -> None:
        lowercase_starts = sum(1 for line in run if line[0].islower())
        is_margin_note = len(run) >= MARGIN_NOTE_MIN_RUN and lowercase_starts * 2 >= len(run)
        if not is_margin_note:
            kept.extend(run)
        run.clear()

    for line in lines:
        if _is_margin_note_candidate(line):
            run.append(line)
            continue
        flush()
        kept.append(line)
    flush()
    return kept


def _starts_new_block(line: str) -> bool:
    if is_list_item(line) or is_heading(line):
        return True
    match = KEY_VALUE_PATTERN.match(line)
    return match is not None and len(match.group("label").split()) <= 6


def _unwrap_lines(lines: list[str]) -> list[str]:
    output: list[str] = []
    blank_since_last = False
    for line in lines:
        if not line:
            blank_since_last = True
            continue

        previous = output[-1] if output else ""
        continues_sentence = (
            previous
            and not previous.endswith(":")
            and line[0].islower()
            and (not blank_since_last or not previous.endswith((".", "!", "?")))
        )
        continues_paragraph = (
            previous
            and not blank_since_last
            and len(previous) >= WRAPPED_LINE_MIN_CHARS
            and not previous.endswith(":")
            and not _starts_new_block(line)
        )
        if continues_sentence or continues_paragraph:
            output[-1] = f"{previous} {line}"
        else:
            if blank_since_last and output:
                output.append("")
            output.append(line)
        blank_since_last = False
    return output


def _should_merge_with_previous(previous: str) -> bool:
    words = previous.split()
    last_word = words[-1].lower() if words else ""
    if last_word in ABBREVIATIONS:
        return True
    # "1." list markers and single initials ("E.") are not sentence ends.
    return bool(re.fullmatch(r"\d{1,2}\.|[a-z]\.", last_word))


def _is_low_value(sentence: str) -> bool:
    letters = sum(1 for character in sentence if character.isalpha())
    words = sentence.lower().split()
    if letters < 4 or is_empty_value(sentence):
        return True
    if len(words) < 2:
        return True
    # Table header rows ("Test Test Date Results Units") carry no evidence.
    return all(word in TABLE_HEADER_WORDS for word in words)


def _push_heading(section_path: list[str], heading: str) -> list[str]:
    # ALL CAPS headings start a new top-level section; other headings nest one level below it.
    if _is_top_level(heading):
        return [heading]
    if section_path and _is_top_level(section_path[0]):
        return [section_path[0], heading]
    return [heading]


def _is_top_level(heading: str) -> bool:
    words = heading.split()
    letters = re.sub(r"[^A-Za-z]", "", words[0]) if words else ""
    return len(letters) >= 4 and letters.isupper()


def _expand_terms(terms: set[str]) -> set[str]:
    expanded = set(terms)
    for source, related in QUESTION_EXPANSIONS.items():
        if _stem(source) in terms:
            expanded.update(_stem(word) for word in related)
    return expanded


def _stem(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    return token[:6]
