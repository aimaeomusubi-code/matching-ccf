import base64
import logging
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models import EmailMessage

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailClient:
    def __init__(self):
        self._service = None

    def authenticate(self) -> None:
        creds = Credentials(
            token=None,
            refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
            client_id=os.environ["GMAIL_CLIENT_ID"],
            client_secret=os.environ["GMAIL_CLIENT_SECRET"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        creds.refresh(Request())
        self._service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail authentication successful")

    def get_unread_messages(self, max_results: int = 50) -> list[EmailMessage]:
        result = (
            self._service.users()
            .messages()
            .list(userId="me", q="is:unread in:inbox", maxResults=max_results)
            .execute()
        )
        messages = result.get("messages", [])
        if not messages:
            logger.info("No unread messages found")
            return []

        logger.info(f"Found {len(messages)} unread messages, fetching details...")
        return self._fetch_message_details([m["id"] for m in messages])

    def _fetch_message_details(self, message_ids: list[str]) -> list[EmailMessage]:
        emails = []
        for i in range(0, len(message_ids), 10):
            batch = message_ids[i : i + 10]
            for msg_id in batch:
                try:
                    msg = (
                        self._service.users()
                        .messages()
                        .get(userId="me", id=msg_id, format="full")
                        .execute()
                    )
                    email = self._parse_message(msg)
                    if email:
                        emails.append(email)
                except HttpError as e:
                    logger.warning(f"Failed to fetch message {msg_id}: {e}")
            if i + 10 < len(message_ids):
                time.sleep(0.1)
        return emails

    def _parse_message(self, msg: dict) -> Optional[EmailMessage]:
        try:
            headers = {
                h["name"].lower(): h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }
            body_text = self._extract_body(msg.get("payload", {}))
            return EmailMessage(
                message_id=msg["id"],
                thread_id=msg["threadId"],
                subject=headers.get("subject", "(件名なし)"),
                sender=headers.get("from", "(送信者不明)"),
                snippet=msg.get("snippet", ""),
                date=headers.get("date", ""),
                body_text=body_text[:2000],
                label_ids=msg.get("labelIds", []),
            )
        except Exception as e:
            logger.warning(f"Failed to parse message {msg.get('id')}: {e}")
            return None

    def _extract_body(self, payload: dict) -> str:
        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode(
                    "utf-8", errors="replace"
                )

        if mime_type.startswith("multipart/"):
            for part in payload.get("parts", []):
                text = self._extract_body(part)
                if text:
                    return text

        # Fall back to snippet if body is not plain text (e.g. HTML-only email)
        return ""

    def ensure_labels_exist(self, label_names: list[str]) -> dict[str, str]:
        existing = (
            self._service.users().labels().list(userId="me").execute().get("labels", [])
        )
        existing_map = {lbl["name"]: lbl["id"] for lbl in existing}

        label_map = {}
        for name in label_names:
            if name in existing_map:
                label_map[name] = existing_map[name]
            else:
                try:
                    created = (
                        self._service.users()
                        .labels()
                        .create(userId="me", body={"name": name})
                        .execute()
                    )
                    label_map[name] = created["id"]
                    logger.info(f"Created label: {name}")
                except HttpError as e:
                    logger.warning(f"Failed to create label '{name}': {e}")

        return label_map

    def apply_label(self, message_id: str, label_id: str) -> None:
        self._service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()

    def archive_message(self, message_id: str) -> None:
        self._service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["INBOX", "UNREAD"]},
        ).execute()

    def send_email(self, to: str, subject: str, html_body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["From"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        self._service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        logger.info(f"Summary email sent to {to}")
