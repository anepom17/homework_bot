"""Приведение HTML от модели к подмножеству, которое понимает Telegram, и разбивка на сообщения."""

import html
import re

# Лимит Telegram — 4096 символов; оставляем запас на закрывающие/открывающие теги.
MESSAGE_LIMIT = 3900

# Теги, которые Telegram поддерживает в parse_mode=HTML (кроме <a> — он обрабатывается отдельно).
_SIMPLE_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "code", "pre", "blockquote", "tg-spoiler",
}
_NEWLINE_TAGS = {"br", "p", "div", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "hr"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
# Обычные HTML-теги без аналога в Telegram: сам тег убираем, содержимое оставляем.
_DROP_TAGS = {
    "span", "font", "small", "big", "mark", "center", "section", "article", "header", "footer",
    "table", "thead", "tbody", "td", "th", "sub", "img", "label", "kbd", "samp", "var", "tt",
}

_TAG_RE = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9-]*)((?:\s[^<>]*)?)/?\s*>")
_HREF_RE = re.compile(r"""href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _escape_text(text: str) -> str:
    """Экранирует текст для Telegram; сущности вроде &nbsp; раскрываются, т.к. Telegram их не знает."""
    escaped = html.escape(html.unescape(text), quote=False)
    return _MD_BOLD_RE.sub(r"<b>\1</b>", escaped)


def sanitize_html(text: str) -> str:
    """Оставляет только поддерживаемые Telegram теги, балансирует их и экранирует всё остальное."""
    out: list[str] = []
    stack: list[str] = []
    pos = 0

    for m in _TAG_RE.finditer(text):
        out.append(_escape_text(text[pos:m.start()]))
        pos = m.end()
        closing, name, attrs = m.group(1) == "/", m.group(2).lower(), m.group(3)

        if name == "strong":
            name = "b"
        elif name == "em":
            name = "i"

        if name in _SIMPLE_TAGS or name == "a":
            if closing:
                if name in stack:
                    while stack:
                        top = stack.pop()
                        out.append(f"</{top}>")
                        if top == name:
                            break
            elif name == "a":
                href = _HREF_RE.search(attrs or "")
                if href:
                    url = next(g for g in href.groups() if g is not None)
                    out.append(f'<a href="{html.escape(url, quote=True)}">')
                    stack.append("a")
            elif name not in stack:  # Telegram не поддерживает вложение тега в самого себя
                out.append(f"<{name}>")
                stack.append(name)
        elif name in _HEADING_TAGS:
            # Заголовок → жирная строка.
            if not closing:
                out.append("\n")
                if "b" not in stack:
                    out.append("<b>")
                    stack.append("b")
            else:
                if stack and stack[-1] == "b":
                    out.append("</b>")
                    stack.pop()
                out.append("\n")
        elif name == "li":
            out.append("" if closing else "\n• ")
        elif name in _NEWLINE_TAGS:
            out.append("\n")
        elif name == "sup":
            out.append("" if closing else "^")
        elif name in _DROP_TAGS:
            out.append(" " if closing and name in {"td", "th"} else "")
        else:
            # Неизвестный «тег» — скорее всего это текст (например, «a<b» в формуле): экранируем.
            out.append(_escape_text(m.group(0)))

    out.append(_escape_text(text[pos:]))
    out.extend(f"</{name}>" for name in reversed(stack))

    result = "".join(out)
    result = re.sub(r"[ \t]+\n", "\n", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def html_to_plain(text: str) -> str:
    """Текст без разметки — запасной вариант, если Telegram всё же отклонил HTML."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _split_text_piece(piece: str, limit: int) -> list[str]:
    """Режет слишком длинный текстовый фрагмент по строкам, затем по словам."""
    parts: list[str] = []
    for line in re.split(r"(?<=\n)", piece):
        while len(line) > limit:
            cut = line.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            parts.append(line[:cut])
            line = line[cut:]
        if line:
            parts.append(line)
    return parts


def split_html(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Делит очищенный HTML на сообщения, закрывая и заново открывая теги на границах."""
    chunks: list[str] = []
    stack: list[str] = []  # открывающие теги целиком, например '<a href="...">'
    current = ""

    def closing() -> str:
        return "".join(f"</{t[1:].split()[0].rstrip('>')}>" for t in reversed(stack))

    for token in re.split(r"(<[^>]+>)", text):
        if not token:
            continue
        is_tag = token.startswith("<")
        for piece in [token] if is_tag else _split_text_piece(token, limit // 2):
            if current.strip() and len(current) + len(piece) + len(closing()) > limit:
                chunks.append(current + closing())
                current = "".join(stack)
            current += piece
            if is_tag:
                if piece.startswith("</"):
                    if stack:
                        stack.pop()
                else:
                    stack.append(piece)

    if current.strip():
        chunks.append(current + closing())
    return [c.strip() for c in chunks if html_to_plain(c).strip()]


def split_plain(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in _split_text_piece(text, limit):
        if current and len(current) + len(piece) > limit:
            chunks.append(current)
            current = ""
        current += piece
    if current.strip():
        chunks.append(current)
    return chunks
