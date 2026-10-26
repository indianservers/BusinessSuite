"""Versioned, opt-in rich content. Legacy strings remain unchanged on read/write."""
import re
from html import unescape
from html.parser import HTMLParser
import bleach
from typing import Annotated
from pydantic import AfterValidator
from bleach.css_sanitizer import CSSSanitizer
from fastapi import HTTPException

PREFIX = "<!--suite-richtext:v1-->"
TAGS = {"p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "em", "i", "u", "s", "del", "span", "mark", "a", "ul", "ol", "li", "blockquote", "pre", "code", "hr", "table", "thead", "tbody", "tr", "th", "td", "colgroup", "col", "label", "input"}
CSS = CSSSanitizer(allowed_css_properties={"color", "background-color", "font-family", "font-size", "text-align", "margin-left"})
FONTS = {"Inter", "Arial", "Georgia", "Times New Roman", "Courier New"}
SIZES = {"12px", "14px", "16px", "18px", "20px", "24px", "32px", "40px"}


def allowed_attribute(tag, name, value):
    if name == "style":
        return True
    if tag == "a" and name == "href":
        return bool(re.fullmatch(r"(?:https?://|mailto:)[^\s<>]+", unescape(value), re.I))
    if tag == "a" and name == "rel":
        return value == "noopener noreferrer"
    if tag == "a" and name == "target":
        return value == "_blank"
    if tag in {"td", "th"} and name in {"colspan", "rowspan"}:
        return value.isdigit() and 1 <= int(value) <= 30
    if tag == "p" and name == "data-note-image":
        return value.isdigit() and int(value) > 0
    if tag == "p" and name == "data-note-width":
        return value.isdigit() and 120 <= int(value) <= 1200
    if tag == "p" and name == "data-note-align":
        return value in {"left", "center", "right"}
    if tag == "p" and name == "data-note-caption":
        return len(value) <= 240 and not any(ord(char) < 32 for char in value)
    if name == "data-indent":
        return value.isdigit() and 0 <= int(value) <= 6
    if name == "data-type":
        return value in {"taskList", "taskItem"}
    if name == "data-checked":
        return value in {"true", "false"}
    return tag == "input" and ((name == "type" and value == "checkbox") or name in {"checked", "disabled"})


class SafeHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        from html import escape
        values = dict(attrs)
        if tag == "input":
            if values.get("type") != "checkbox":
                return
            values["disabled"] = ""
        if "style" in values:
            import tinycss2
            styles = []
            for item in tinycss2.parse_declaration_list(values["style"]):
                if item.type != "declaration":
                    continue
                value = tinycss2.serialize(item.value).strip()
                name = item.lower_name
                valid = (name == "font-family" and value.strip("\"'") in FONTS
                         or name == "font-size" and value in SIZES
                         or name == "text-align" and value in {"left", "center", "right", "justify"}
                         or name == "margin-left" and value in {f"{n * 24}px" for n in range(7)}
                         or name in {"color", "background-color"} and re.fullmatch(r"(?:#[a-f0-9]{3,8}|rgba?\([\d\s,.%]+\)|[a-z]+)", value, re.I))
                if valid:
                    styles.append(f"{name}: {value}")
            if styles:
                values["style"] = "; ".join(styles)
            else:
                values.pop("style")
        if tag == "a":
            values["rel"] = "noopener noreferrer"
        self.parts.append("<" + tag + "".join(f' {key}="{escape(value or "", quote=True)}"' for key, value in values.items()) + ">")

    def handle_endtag(self, tag):
        if tag not in {"input", "br", "hr", "col"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, value):
        from html import escape
        self.parts.append(escape(value))


def sanitize_rich_text(value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value
    if len(value) > 1_000_000:
        raise HTTPException(422, "Rich content is too large")
    # Bleach uses an HTML5 parser, handling malformed markup and mutation-XSS.
    cleaned = bleach.clean(value[len(PREFIX):], tags=TAGS, attributes=allowed_attribute,
                           protocols={"http", "https", "mailto"}, strip=True, strip_comments=True, css_sanitizer=CSS)
    parser = SafeHTML()
    parser.feed(cleaned)
    html = "".join(parser.parts)
    plain = rich_text_plain(PREFIX + html)
    if len(plain) > 200_000:
        raise HTTPException(422, "Rich content exceeds 200,000 text characters")
    return PREFIX + html if plain.strip() or any(f"<{tag}" in html for tag in ("table", "hr")) else ""


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote", "pre"}:
            self.parts.append("\n")
        if tag in {"td", "th"}:
            self.parts.append("\t")


def rich_text_plain(value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value
    parser = PlainHTML()
    parser.feed(value[len(PREFIX):])
    return "".join(parser.parts).replace("\xa0", " ").strip()


def rich_text_type(max_length=200000, min_length=0):
    """Schema field whose limits count meaningful text, with a separate markup cap."""
    def validate(value):
        value = sanitize_rich_text(value)
        if not min_length <= len(rich_text_plain(value)) <= max_length:
            raise ValueError(f"Content must contain {min_length}–{max_length} text characters")
        return value
    return Annotated[str, AfterValidator(validate)]


def email_body_parts(value):
    """Safe HTML alternative plus readable plain text for rich and legacy email."""
    from html import escape
    if value.startswith(PREFIX) or re.search(r"<(?:p|div|span|strong|b|em|i|u|h[1-4]|table|a|br)\b", value, re.I):
        safe = sanitize_rich_text(value if value.startswith(PREFIX) else PREFIX + value)
        return rich_text_plain(safe), safe.removeprefix(PREFIX)
    return value, escape(value).replace("\n", "<br/>")


def rich_text_pdf_markup(value):
    """ReportLab's limited paragraph dialect, never arbitrary browser HTML."""
    from html import escape
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return escape(str(value or "")).replace("\n", "<br/>")

    class PDFHTML(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts, self.stack = [], []

        def handle_starttag(self, tag, attrs):
            supported = {"strong": "b", "b": "b", "em": "i", "i": "i", "u": "u", "s": "strike", "del": "strike"}
            if tag in supported:
                name = supported[tag]
                self.parts.append(f"<{name}>")
                self.stack.append((tag, name))
            elif tag in {"h1", "h2", "h3", "h4", "h5", "h6", "th"}:
                self.parts.append("<b>")
                self.stack.append((tag, "b"))
            elif tag == "li":
                self.parts.append("&#8226; ")
            elif tag in {"br", "hr"}:
                self.parts.append("<br/>")

        def handle_endtag(self, tag):
            if self.stack and self.stack[-1][0] == tag:
                _, name = self.stack.pop()
                self.parts.append(f"</{name}>")
            if tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote", "pre"}:
                self.parts.append("<br/>")
            elif tag in {"td", "th"}:
                self.parts.append(" | ")

        def handle_data(self, data):
            self.parts.append(escape(data))

    parser = PDFHTML()
    parser.feed(sanitize_rich_text(value)[len(PREFIX):])
    return "".join(parser.parts)


def sanitize_tree(value):
    if isinstance(value, dict):
        return {key: item if key in {"password", "new_password", "current_password", "token", "secret", "api_key"} else sanitize_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_tree(item) for item in value]
    return sanitize_rich_text(value)
