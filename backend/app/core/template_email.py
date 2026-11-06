"""Email-only allowlist preserving visual layouts without active content."""
import re
from html import unescape
import bleach
from bleach.css_sanitizer import CSSSanitizer

CSS = CSSSanitizer(allowed_css_properties={
    'color', 'background-color', 'font-family', 'font-size', 'font-weight', 'text-align',
    'line-height', 'letter-spacing', 'text-decoration', 'overflow-wrap', 'box-sizing',
    'padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right',
    'margin', 'margin-left', 'margin-right', 'margin-top', 'margin-bottom', 'display',
    'width', 'height', 'min-width', 'max-width', 'max-height', 'border', 'border-top',
    'border-bottom', 'border-radius', 'border-collapse', 'vertical-align', 'table-layout',
})


def attribute(tag, name, value):
    if name == 'style': return True
    if tag == 'div' and name == 'data-suite-template': return value == 'v1'
    if tag == 'img' and name == 'alt': return True
    if tag == 'img' and name == 'src': return bool(re.fullmatch(r'https://[^\s<>"\']+', unescape(value), re.I))
    if tag == 'a' and name == 'href': return bool(re.fullmatch(r'(?:https://|mailto:)[^\s<>"\']+', unescape(value), re.I))
    if tag in {'td', 'th'} and name in {'colspan', 'rowspan'}: return value.isdigit() and 1 <= int(value) <= 30
    return False


def sanitize_template_email(value):
    # No CSS URLs, scripts, event handlers, forms, embedded documents or SVG.
    from app.core.rich_text import TAGS
    return bleach.clean(value, tags=(TAGS - {'input', 'label'}) | {'div', 'img'}, attributes=attribute, protocols={'https', 'mailto'}, css_sanitizer=CSS, strip=True, strip_comments=True)
