"""Meta Cloud API transport. Credentials and sender belong to the deployment."""
import re
import httpx
from app.core.config import settings


class MetaWhatsAppProvider:
    name = "meta"

    def send(self, *, channel="whatsapp", to, body="", template=None):
        if channel != "whatsapp":
            raise RuntimeError("Meta transport supports WhatsApp only")
        if not settings.CRM_WHATSAPP_ACCESS_TOKEN or not settings.CRM_WHATSAPP_PHONE_NUMBER_ID:
            raise RuntimeError("WhatsApp access token and phone number ID are not configured")
        if not re.fullmatch(r"v\d+\.\d+", settings.CRM_WHATSAPP_API_VERSION) or not settings.CRM_WHATSAPP_PHONE_NUMBER_ID.isdecimal():
            raise RuntimeError("Invalid WhatsApp API version or sender ID")
        number = re.sub(r"[\s()+-]", "", to)
        if not re.fullmatch(r"[1-9]\d{6,14}", number):
            raise RuntimeError("Use an international recipient number including country code")
        payload = {"messaging_product": "whatsapp", "to": number}
        if template:
            payload.update(type="template", template=template)
        else:
            if not body.strip() or len(body) > 4096:
                raise RuntimeError("WhatsApp text must contain 1–4096 characters")
            payload.update(type="text", text={"body": body, "preview_url": False})
        try:
            response = httpx.post(
                f"https://graph.facebook.com/{settings.CRM_WHATSAPP_API_VERSION}/{settings.CRM_WHATSAPP_PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {settings.CRM_WHATSAPP_ACCESS_TOKEN}"},
                json=payload, timeout=20,
            )
        except httpx.TransportError:
            raise RuntimeError("WhatsApp outcome is uncertain; reconcile before retrying") from None
        try:
            result = response.json()
        except ValueError:
            raise RuntimeError("WhatsApp returned an unreadable response; reconcile before retrying") from None
        if response.is_error:
            code = result.get("error", {}).get("code", "unknown")
            # Never persist provider response text: it can contain credentials or recipient data.
            raise RuntimeError(f"Meta rejected WhatsApp message (HTTP {response.status_code}, code {code})")
        messages = result.get("messages") or []
        if not messages or not messages[0].get("id"):
            raise RuntimeError("WhatsApp acceptance is uncertain; reconcile before retrying")
        return "accepted", messages[0]["id"]
