"""Explicit conversation controls, never business-action approval."""
import re


def is_new_conversation(text):
    value=text.strip().casefold().strip(' .!?')
    return bool(re.fullmatch(r'(?:please\s+)?(?:(?:start|begin|open)\s+(?:a\s+)?(?:new|fresh|separate)|new)\s+(?:conversation|chat|request)',value))
