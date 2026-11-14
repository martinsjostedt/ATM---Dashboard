"""Server-side export of ATM campaign email to a Gmail draft with inline images."""
import base64
import html
import re
from email.message import EmailMessage
from email.utils import make_msgid

import boto3
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def render_campaign_html(message, images):
    """Render legacy plain text with inline image markers as email-safe HTML."""
    markers = list(re.finditer(r'<img\b[^>]*src=["\']cid:([^"\']+)["\'][^>]*>', message, re.I))
    # Legacy ATM body stores plain text, raw img placeholder and unformatted URLs.
    if not markers and "<img" in message.lower():
        raise ValueError("Ogiltig bildmarkör i kampanjmejlet.")
    parts = re.split(r'(<img\b[^>]*>)', message, flags=re.I)
    blocks = []
    for part in parts:
        if re.match(r'<img\b', part, re.I):
            cid_match = re.search(r'src=["\']cid:([^"\']+)["\']', part, re.I)
            if not cid_match:
                raise ValueError("En bild saknar CID.")
            cid = cid_match.group(1)
            if cid not in images:
                raise ValueError(f"Bild saknas för CID: {cid}")
            blocks.append(f'<p><img src="cid:{html.escape(cid, quote=True)}" alt="Konsertbild" style="width:100%;max-width:600px;height:auto;display:block;border:0;"></p>')
        else:
            for paragraph in re.split(r'\n\s*\n', part.strip()):
                if not paragraph:
                    continue
                safe = html.escape(paragraph)
                safe = re.sub(r'(https?://[^\s<]+)', lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', safe)
                blocks.append("<p>" + safe.replace("\n", "<br>") + "</p>")
    return ('<html><body style="font-family:Arial,sans-serif;font-size:15px;'
            'line-height:1.55;max-width:640px;margin:auto;color:#222;">'
            + "\n".join(blocks) + "</body></html>")


def make_draft_message(subject, body, recipient, images):
    """Build multipart/mixed > multipart/alternative > multipart/related.

    Each image is inline by CID, plus an independently downloadable attachment.
    """
    if not recipient or "@" not in recipient:
        raise ValueError("Ange mottagarens e-postadress.")
    outer = EmailMessage()
    outer["To"] = recipient
    outer["Subject"] = subject
    outer.set_content(re.sub(r'<img\b[^>]*>', '[Konsertbild]', body, flags=re.I))
    html_body = render_campaign_html(body, images)
    outer.add_alternative(html_body, subtype="html")
    related = outer.get_body(preferencelist=("html",))
    for cid, item in images.items():
        data, filename, mime = item
        maintype, subtype = mime.split("/", 1)
        related.add_related(data, maintype=maintype, subtype=subtype, cid=f"<{cid}>", filename=filename, disposition="inline")
        outer.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return outer


def export_gmail_draft(subject, body, recipient, images, settings):
    """Create, never send, a Gmail draft using stored OAuth refresh credentials."""
    scopes = ["https://www.googleapis.com/auth/gmail.compose"]
    creds = Credentials(
        token=None,
        refresh_token=settings["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings["GMAIL_CLIENT_ID"],
        client_secret=settings["GMAIL_CLIENT_SECRET"],
        scopes=scopes,
    )
    creds.refresh(Request())
    msg = make_draft_message(subject, body, recipient, images)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    result = gmail.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return result["id"]


def fetch_neon_image(object_key, settings):
    """Only retrieve a key already stored in ATM, never accept arbitrary URLs."""
    if not object_key.startswith("konsertbilder/") or ".." in object_key:
        raise ValueError("Ogiltig bildreferens.")
    s3 = boto3.client(
        "s3", endpoint_url=settings["AWS_ENDPOINT_URL_S3"],
        region_name=settings.get("AWS_REGION", "us-east-2"),
        aws_access_key_id=settings["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=settings["AWS_SECRET_ACCESS_KEY"],
    )
    response = s3.get_object(Bucket="uploads", Key=object_key)
    if response["ContentLength"] > 10 * 1024 * 1024:
        raise ValueError("Bilden överskrider gränsen på 10 MB.")
    data = response["Body"].read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Bilden överskrider gränsen på 10 MB.")
    mime = response.get("ContentType", "image/jpeg").split(";", 1)[0]
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Endast JPG, PNG och WebP stöds.")
    return (data, object_key.rsplit("/", 1)[-1], mime)
