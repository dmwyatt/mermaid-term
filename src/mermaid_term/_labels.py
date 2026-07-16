"""Label sanitization: statement splitting, HTML/entity/markdown stripping."""

from __future__ import annotations

ENTITY_LOOKAHEAD = 10

HTML_FORMAT_TAGS = frozenset(
    [
        "b", "strong", "i", "em", "u", "s", "strike", "del", "ins", "mark",
        "small", "big", "sub", "sup", "code", "kbd", "samp", "var", "tt",
        "span", "font", "q", "abbr", "cite", "pre",
    ]
)


def split_statements(line: str, out: list[str]) -> None:
    cur: list[str] = []
    in_quotes = False
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if in_quotes:
            if c == '"':
                in_quotes = False
            cur.append(c)
        elif c == '"':
            in_quotes = True
            cur.append(c)
        elif c == "%" and i + 1 < n and line[i + 1] == "%":
            break
        elif c == ";":
            _flush_statement(cur, out)
        else:
            cur.append(c)
        i += 1
    _flush_statement(cur, out)


def _flush_statement(cur: list[str], out: list[str]) -> None:
    trimmed = "".join(cur).strip()
    if trimmed:
        out.append(trimmed)
    cur.clear()


def statements_of(src: str) -> list[str]:
    out: list[str] = []
    for raw_line in src.splitlines():
        split_statements(raw_line, out)
    return out


def clean_label(raw: str) -> str:
    stripped = strip_html_tags(raw.strip())
    trimmed = stripped.strip()
    unquoted = trimmed
    if len(trimmed) >= 2 and trimmed[0] == '"' and trimmed[-1] == '"':
        unquoted = trimmed[1:-1].strip()
    elif len(trimmed) >= 2 and trimmed[0] == "'" and trimmed[-1] == "'":
        unquoted = trimmed[1:-1].strip()
    if len(unquoted) >= 2 and unquoted[0] == "`" and unquoted[-1] == "`":
        text = strip_markdown(unquoted[1:-1].strip())
    else:
        text = unquoted
    # Decode after tag-stripping so `<b>` is removed as markup while `&lt;b&gt;`
    # survives as a literal `<b>`; one decode at the single return covers both paths.
    return decode_html_entities(text)


def decode_html_entities(s: str) -> str:
    if "&" not in s:
        return s
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] != "&":
            out.append(s[i])
            i += 1
            continue
        # Scan window (includes the terminating `;`) so a stray `&` or
        # over-long run stays literal.
        hi = min(i + 1 + ENTITY_LOOKAHEAD, n)
        semi = s.find(";", i + 1, hi)
        decoded = _decode_entity_body(s[i + 1 : semi]) if semi != -1 else None
        if decoded is not None:
            # Resume past the `;`; the single pass never re-scans emitted text,
            # so `&amp;lt;` decodes to the literal `&lt;` rather than to `<`.
            out.append(decoded)
            i = semi + 1
        else:
            out.append("&")
            i += 1
    return "".join(out)


_NAMED_ENTITIES = {"lt": "<", "gt": ">", "amp": "&", "quot": '"', "apos": "'"}


def _decode_entity_body(body: str) -> str | None:
    named = _NAMED_ENTITIES.get(body)
    if named is not None:
        return named
    if not body.startswith("#"):
        return None
    num = body[1:]
    try:
        if num[:1] in ("x", "X"):
            code = int(num[1:], 16)
        else:
            code = int(num, 10)
        c = chr(code)
    except ValueError:
        return None
    # Reject control chars (Unicode Cc): NUL collides with the CONT sentinel
    # and ESC would inject ANSI into scrollback. Surrogates are not valid
    # scalar values (chr() allows them; Rust's char does not).
    if code < 0x20 or 0x7F <= code <= 0x9F or 0xD800 <= code <= 0xDFFF:
        return None
    return c


def strip_markdown(s: str) -> str:
    no_code = s.replace("`", "")
    no_strong = no_code.replace("**", "").replace("__", "")
    out: list[str] = []
    n = len(no_strong)
    for i, c in enumerate(no_strong):
        if c in "*_" and not (
            i > 0
            and no_strong[i - 1].isalnum()
            and i + 1 < n
            and no_strong[i + 1].isalnum()
        ):
            continue
        out.append(c)
    return "".join(out).strip()


def strip_html_tags(s: str) -> str:
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "<":
            tag = _html_tag_at(s, i)
            if tag is not None:
                name, end = tag
                lower = name.lower()
                if lower == "br":
                    out.append(" ")
                    i = end
                    continue
                if lower in HTML_FORMAT_TAGS:
                    i = end
                    continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _html_tag_at(s: str, start: int) -> tuple[str, int] | None:
    i = start + 1
    n = len(s)
    if i < n and s[i] == "/":
        i += 1
    name_start = i
    while i < n and s[i].isascii() and s[i].isalnum():
        i += 1
    if i == name_start:
        return None
    name = s[name_start:i]
    while i < n and s[i] != ">":
        if s[i] == "<":
            return None
        i += 1
    if i < n and s[i] == ">":
        return (name, i + 1)
    return None


def non_empty(s: str) -> str | None:
    return s if s else None


def display_generics(s: str) -> str:
    out: list[str] = []
    open_ = False
    for c in s:
        if c == "~":
            out.append(">" if open_ else "<")
            open_ = not open_
        else:
            out.append(c)
    return "".join(out)
