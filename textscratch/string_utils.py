"""String manipulation utilities for text-to-blocks parsing."""

from typing import Dict, List, Optional, Tuple


def escape_text(value: str) -> str:
    """Quote syntax characters without changing Scratch's literal value."""
    return (str(value).replace("\\", "\\\\").replace("\n", "\\n")
            .replace("\r", "\\r").replace("\t", "\\t")
            .translate(str.maketrans({c: "\\" + c for c in "[](){}<>:"})))


def unescape_text(value: str) -> str:
    import re
    return re.sub(r"\\([\\\[\](){}<>:nrt])",
                  lambda m: {"n": "\n", "r": "\r", "t": "\t"}.get(m[1], m[1]), value)


def top_level_positions(text: str):
    """Yield boundaries outside nested inputs; square literals are opaque.

    Spaced < and > are comparison operators, not boolean delimiters.
    """
    stack = []
    pairs = {"[": "]", "(": ")", "{": "}", "<": ">"}
    i = 0
    while i < len(text):
        if not stack:
            yield i
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            i += 2
            continue
        comparison = (ch in "<>" and i > 0 and i + 1 < len(text)
                      and text[i - 1].isspace() and text[i + 1].isspace())
        if stack and stack[-1] == "]":
            if ch == "]":
                stack.pop()
        elif not comparison:
            if ch in pairs:
                stack.append(pairs[ch])
            elif stack and ch == stack[-1]:
                stack.pop()
        i += 1
    if not stack:
        yield len(text)


def match_parts(text: str, literals: List[str]) -> Optional[List[str]]:
    """Match a template, capturing complete inputs instead of greedy regex spans."""
    if not text.startswith(literals[0]):
        return None
    def match_from(pos, index):
        if index == len(literals):
            return [] if pos == len(text) else None
        tail = text[pos:]
        literal = literals[index]
        for boundary in top_level_positions(tail):
            if boundary == 0 or not tail.startswith(literal, boundary):
                continue
            end = pos + boundary
            rest = match_from(end + len(literal), index + 1)
            if rest is not None:
                return [text[pos:end]] + rest
        return None
    return match_from(len(literals[0]), 1)


def strip_line_comment(text: str) -> str:
    """Strip a trailing comment, leaving literals and a custom // call intact."""
    for pos in top_level_positions(text):
        if pos > 0 and text.startswith("//", pos) and text[pos - 1].isspace():
            return text[:pos].rstrip()
    return text


def split_scripts(content: str) -> List[List[Tuple[int, str, int]]]:
    """Split code content into separate scripts based on blank lines.
    
    Returns:
        A list of scripts, where each script is a list of tuples:
        (indent_level, line_text, line_number).
        Line numbers are 1-based.
    """
    scripts: List[List[Tuple[int, str, int]]] = []
    current: List[Tuple[int, str, int]] = []
    nesting = 0
    for line_num, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line.strip():
            if current and nesting == 0:
                scripts.append(current)
                current = []
            continue
        text = strip_line_comment(raw_line.strip())
        if nesting == 0 and current and text.startswith(("when ", "define ")):
            scripts.append(current)
            current = []
        if text == "end":
            nesting = max(0, nesting - 1)
        elif text == "forever" or text == "all at once" or text.startswith(("repeat ", "if ", "while ", "for each ")):
            nesting += 1
        indent_spaces = len(raw_line) - len(raw_line.lstrip(" "))
        indent_level = indent_spaces // 4
        current.append((indent_level, raw_line.strip(), line_num))
    if current:
        scripts.append(current)
    return scripts


def strip_wrappers(val: str, strip_inner: bool = True) -> str:
    """Remove a single surrounding pair of [], (), or {} while optionally preserving inner whitespace."""
    without_newlines = val.strip("\n\r")
    trimmed = without_newlines.strip()
    for open_ch, close_ch in (("[", "]"), ("(", ")"), ("{", "}")):
        if trimmed.startswith(open_ch) and trimmed.endswith(close_ch):
            inner = trimmed[1:-1]
            return inner.strip() if strip_inner else inner
    # No wrapper; keep any leading/trailing spaces (except newlines) intact to preserve literals.
    return without_newlines


def coerce_number(val: str) -> Optional[float]:
    """Try to convert a string to a number, returning None if not possible."""
    try:
        num = float(val)
        if "." not in val and "e" not in val.lower() and "E" not in val:
            if num.is_integer():
                return int(num)
        return num
    except ValueError:
        return None


def strip_wrapping_parens(text: str) -> str:
    """Strip outermost matching parentheses if they wrap the entire expression."""
    trimmed = text.strip()
    if not (trimmed.startswith("(") and trimmed.endswith(")")):
        return trimmed

    depth = 0
    for idx, ch in enumerate(trimmed):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            # If we close the first opening paren before the end, the outer parens
            # are not a true wrapper; return the original text.
            if depth == 0 and idx != len(trimmed) - 1:
                return trimmed

    return trimmed[1:-1].strip()


def split_top_level(
    expr: str, token: str, extra_pairs: Optional[Dict[str, str]] = None
) -> Optional[Tuple[str, str]]:
    """Split expression at the first top-level occurrence of token."""
    depth = 0
    idx = 0
    limit = len(expr)
    token_len = len(token)
    opens = {"(": ")", "{": "}"}
    if extra_pairs:
        opens.update(extra_pairs)
    closes = set(opens.values())
    while idx <= limit - token_len:
        ch = expr[idx]
        if ch in opens:
            depth += 1
            idx += 1
            continue
        if ch in closes and depth > 0:
            depth -= 1
        if depth == 0 and expr.startswith(token, idx):
            left = expr[:idx].strip()
            right = expr[idx + token_len :].strip()
            return (left, right)
        idx += 1
    return None


def split_top_level_whitespace(text: str, expected_parts: int) -> List[str]:
    """Split text on whitespace at the top level (outside brackets)."""
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    opens = "([{<"
    closes = ")]}>"

    for idx, ch in enumerate(text):
        if ch in opens:
            depth += 1
        elif ch in closes and depth > 0:
            depth -= 1

        if ch.isspace() and depth == 0:
            if buf:
                parts.append("".join(buf).strip())
                buf = []
                if len(parts) == expected_parts - 1:
                    tail = text[idx + 1 :].strip()
                    parts.append(tail)
                    return parts
            continue

        buf.append(ch)

    if buf:
        parts.append("".join(buf).strip())
    return parts


def remove_literal_top_level(text: str, literal: str) -> str:
    """Remove the first top-level occurrence of a literal from text."""
    depth = 0
    idx = 0
    limit = len(text)
    lit_len = len(literal)

    while idx <= limit - lit_len:
        ch = text[idx]
        if ch in "([{<":
            depth += 1
            idx += 1
            continue
        if ch in ")]}>" and depth > 0:
            depth -= 1
        if depth == 0 and text.startswith(literal, idx):
            left = text[:idx].rstrip()
            right = text[idx + lit_len :].lstrip()
            mid = " " if left and right else ""
            return (left + mid + right).strip()
        idx += 1

    return text


def strip_inline_literals(text: str, literals: List[str]) -> str:
    """Remove multiple literals from text at the top level."""
    result = text
    for literal in literals:
        lit = literal.strip()
        if not lit:
            continue
        result = remove_literal_top_level(result, lit)
    return result
