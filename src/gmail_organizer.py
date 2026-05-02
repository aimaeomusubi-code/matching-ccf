#!/usr/bin/env python3
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import anthropic
from dotenv import load_dotenv
from googleapiclient.errors import HttpError

from ai_analyzer import AIAnalyzer
from gmail_client import GmailClient
from models import AUTO_ARCHIVE_CATEGORIES, Category, DailySummary, EmailMessage, Priority

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("organizer.log"),
    ],
)
logger = logging.getLogger(__name__)


# ── HTML generation ──────────────────────────────────────────────────────────

def _category_short(email: EmailMessage) -> str:
    if email.category:
        return email.category.value.split("/", 1)[-1]
    return "未分類"


def _badge(text: str, bg: str = "#e0e7ff", fg: str = "#3730a3") -> str:
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:12px;font-size:12px;font-weight:600;">{text}</span>'
    )


def _email_card(email: EmailMessage, compact: bool = False) -> str:
    cat = _category_short(email)
    subject = email.subject or "(件名なし)"
    sender = email.sender or "(送信者不明)"

    if compact:
        return (
            f'<tr style="border-bottom:1px solid #f3f4f6;">'
            f'<td style="padding:8px 12px;font-size:13px;">'
            f'{_badge(cat)} {subject}'
            f'<span style="color:#6b7280;margin-left:8px;font-size:12px;">{sender}</span>'
            f"</td></tr>"
        )

    summary_row = ""
    if email.summary:
        summary_row = f'<p style="margin:4px 0;color:#374151;font-size:13px;">{email.summary}</p>'
    action_row = ""
    if email.action_suggestion:
        action_row = (
            f'<p style="margin:4px 0;font-size:12px;color:#6b7280;">'
            f"アクション: {email.action_suggestion}</p>"
        )

    return (
        f'<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin:8px 0;">'
        f'<div style="margin-bottom:4px;">{_badge(cat)} '
        f'<strong style="font-size:14px;">{subject}</strong></div>'
        f'<p style="margin:4px 0;font-size:12px;color:#6b7280;">{sender} | {email.date}</p>'
        f"{summary_row}{action_row}"
        f"</div>"
    )


def _section(title: str, color: str, emails: list[EmailMessage], compact: bool = False) -> str:
    if not emails:
        return ""
    count = len(emails)
    if compact:
        rows = "".join(_email_card(e, compact=True) for e in emails)
        inner = f'<table style="width:100%;border-collapse:collapse;">{rows}</table>'
    else:
        inner = "".join(_email_card(e) for e in emails)

    return (
        f'<div style="margin-bottom:24px;">'
        f'<h2 style="font-size:16px;color:{color};margin:0 0 8px 0;">{title} ({count}件)</h2>'
        f"{inner}"
        f"</div>"
    )


def build_summary_html(summary: DailySummary) -> str:
    high_section = _section("🔴 高優先度", "#dc2626", summary.high_priority)
    medium_section = _section("🟡 中優先度", "#d97706", summary.medium_priority)
    low_section = _section("🟢 低優先度", "#16a34a", summary.low_priority, compact=True)

    unanalyzed_section = ""
    if summary.unanalyzed:
        rows = "".join(
            f'<tr style="border-bottom:1px solid #f3f4f6;">'
            f'<td style="padding:8px 12px;font-size:13px;">'
            f'{e.subject} <span style="color:#6b7280;font-size:12px;">{e.sender}</span>'
            f"</td></tr>"
            for e in summary.unanalyzed
        )
        unanalyzed_section = (
            f'<div style="margin-bottom:24px;">'
            f'<h2 style="font-size:16px;color:#6b7280;margin:0 0 8px 0;">'
            f"⚠️ 未分析 ({len(summary.unanalyzed)}件)</h2>"
            f'<table style="width:100%;border-collapse:collapse;">{rows}</table>'
            f"</div>"
        )

    errors_section = ""
    if summary.errors:
        errors_html = "".join(f"<li>{e}</li>" for e in summary.errors)
        errors_section = (
            f'<div style="background:#fef2f2;border:1px solid #fecaca;'
            f'border-radius:8px;padding:12px;margin-bottom:16px;">'
            f'<strong>ℹ️ エラーログ</strong><ul style="margin:8px 0;">{errors_html}</ul>'
            f"</div>"
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:680px;margin:0 auto;padding:24px;color:#111827;">
  <div style="background:linear-gradient(135deg,#667eea,#764ba2);
              border-radius:12px;padding:24px;color:white;margin-bottom:24px;">
    <h1 style="margin:0 0 8px 0;font-size:22px;">📬 メール日次サマリー</h1>
    <p style="margin:0;opacity:0.9;">{summary.date}</p>
    <div style="margin-top:12px;font-size:14px;opacity:0.85;">
      合計 <strong>{summary.total_unread}件</strong> |
      AI分析済み <strong>{summary.analyzed_count}件</strong> |
      自動アーカイブ <strong>{summary.archived_count}件</strong>
    </div>
  </div>
  {errors_section}
  {high_section}
  {medium_section}
  {low_section}
  {unanalyzed_section}
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
  <p style="font-size:12px;color:#9ca3af;text-align:center;">
    Gmail Daily Organizer by Claude AI
  </p>
</body>
</html>"""


# ── Main orchestration ────────────────────────────────────────────────────────

def main() -> None:
    load_dotenv()

    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).strftime("%Y年%m月%d日")
    user_email = os.environ.get("GMAIL_USER_EMAIL", "")
    if not user_email:
        logger.error("GMAIL_USER_EMAIL is not set")
        sys.exit(1)

    summary = DailySummary(
        date=today, total_unread=0, analyzed_count=0, archived_count=0
    )

    # Step 1: Gmail auth
    gmail = GmailClient()
    try:
        gmail.authenticate()
    except Exception as e:
        logger.error(f"Gmail authentication failed: {e}")
        sys.exit(1)

    # Step 2: Ensure all AI-Organizer labels exist
    all_label_names = [cat.value for cat in Category]
    label_map = gmail.ensure_labels_exist(all_label_names)

    # Step 3: Fetch unread emails (cap at 50)
    emails: list[EmailMessage] = gmail.get_unread_messages(max_results=50)
    summary.total_unread = len(emails)
    logger.info(f"Fetched {len(emails)} unread messages")

    # Step 4: AI analysis with graceful degradation
    ai_available = True
    analyzer = AIAnalyzer()

    for i, email in enumerate(emails):
        if not ai_available:
            break
        logger.info(f"Analyzing {i + 1}/{len(emails)}: {email.subject[:60]}")
        try:
            result = analyzer.analyze_email_with_retry(email)
            if result:
                email.category = result.category
                email.priority = result.priority
                email.summary = result.summary
                email.action_suggestion = result.action_suggestion
                email.ai_analyzed = True
                summary.analyzed_count += 1
        except anthropic.APIConnectionError as e:
            logger.error(f"Claude API unreachable: {e}. Continuing without AI analysis.")
            ai_available = False
            summary.errors.append(f"AI分析エラー（接続不可）: {e}")
        time.sleep(0.5)

    # Step 5: Apply labels and archive
    archived_ids: set[str] = set()
    for email in emails:
        if not email.ai_analyzed:
            continue
        label_id = label_map.get(email.category.value) if email.category else None

        if email.category in AUTO_ARCHIVE_CATEGORIES:
            try:
                if label_id:
                    gmail.apply_label(email.message_id, label_id)
                gmail.archive_message(email.message_id)
                archived_ids.add(email.message_id)
                summary.archived_count += 1
            except HttpError as e:
                logger.warning(f"Failed to archive {email.message_id}: {e}")
        elif label_id:
            try:
                gmail.apply_label(email.message_id, label_id)
            except HttpError as e:
                logger.warning(f"Failed to label {email.message_id}: {e}")

    # Step 6: Bucket into priority groups
    for email in emails:
        if email.message_id in archived_ids:
            continue
        if not email.ai_analyzed:
            summary.unanalyzed.append(email)
        elif email.priority == Priority.HIGH:
            summary.high_priority.append(email)
        elif email.priority == Priority.MEDIUM:
            summary.medium_priority.append(email)
        else:
            summary.low_priority.append(email)

    # Step 7: Build and send summary email
    html = build_summary_html(summary)
    subject = f"📬 メール日次サマリー {today} ({summary.total_unread}件)"
    try:
        gmail.send_email(to=user_email, subject=subject, html_body=html)
    except Exception as e:
        logger.error(f"Failed to send summary email: {e}")
        sys.exit(1)

    logger.info(
        f"Done. Total: {summary.total_unread}, Analyzed: {summary.analyzed_count}, "
        f"Archived: {summary.archived_count}"
    )


if __name__ == "__main__":
    main()
