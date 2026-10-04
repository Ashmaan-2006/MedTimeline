def build_source_snippet(content: str, max_length: int = 280) -> str:
    normalized_content = " ".join(content.split())
    if len(normalized_content) <= max_length:
        return normalized_content

    truncated = normalized_content[: max_length - 3].rstrip()
    word_boundary = truncated.rfind(" ")
    if word_boundary > 0:
        truncated = truncated[:word_boundary]
    return truncated + "..."
