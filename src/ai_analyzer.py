import json
import logging
import os
import time
from typing import Optional

import anthropic

from models import AnalysisResult, Category, EmailMessage, Priority

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """
あなたはメール管理の専門家AIです。受信したメールを分析し、以下の作業を行います：
1. カテゴリ分類
2. 優先度評価
3. 日本語での要約
4. アクション提案

必ず以下のJSON形式のみで回答してください。説明文やコードブロックは不要です。

カテゴリの選択肢（必ずこの値のいずれかを使用）:
- "AI-Organizer/仕事" : 仕事・ビジネス関連
- "AI-Organizer/個人" : 個人・友人・家族
- "AI-Organizer/金融・請求" : 銀行・クレジットカード・請求書・支払い
- "AI-Organizer/ショッピング" : EC・注文確認・配送通知
- "AI-Organizer/ニュースレター" : メルマガ・ニュース配信・マーケティング
- "AI-Organizer/SNS通知" : Twitter/X・GitHub・Slack・Facebook等の通知
- "AI-Organizer/通知" : サービス自動通知・アラート・システムメール
- "AI-Organizer/その他" : 上記に該当しない

優先度の判断基準:
- "high": 返信・対応期限がある、重要な金融取引確認、重要な仕事メール
- "medium": 情報共有・報告、配送・注文確認、要確認だが緊急でない
- "low": ニュースレター、SNS通知、マーケティング、自動通知、広告

should_archiveをtrueにする条件:
- カテゴリが "AI-Organizer/ニュースレター" または "AI-Organizer/SNS通知"
- 優先度が "low" かつ明らかな自動通知メールの場合

重要: 仕事・個人メールのshould_archiveは必ずfalseにすること。

回答フォーマット（このJSONのみ出力すること）:
{"category": "<カテゴリ値>", "priority": "<high|medium|low>", "summary": "<1〜2文の日本語要約>", "action_suggestion": "<推奨アクション（例：返信が必要、確認のみ、無視可能）>", "should_archive": <true|false>}
"""


class AIAnalyzer:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-5")

    def analyze_email_with_retry(
        self, email: EmailMessage, max_retries: int = 3
    ) -> Optional[AnalysisResult]:
        for attempt in range(max_retries):
            try:
                return self._analyze_email(email)
            except anthropic.RateLimitError:
                wait = 2**attempt
                logger.warning(
                    f"Rate limited, waiting {wait}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
            except anthropic.APIConnectionError:
                raise  # bubble up — orchestrator will disable AI
        return None

    def _analyze_email(self, email: EmailMessage) -> Optional[AnalysisResult]:
        prompt = f"""件名: {email.subject}
送信者: {email.sender}
日時: {email.date}
本文（最初の2000文字）:
{email.body_text[:2000] if email.body_text else email.snippet}
"""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            data = json.loads(raw)
            return AnalysisResult(
                category=Category(data["category"]),
                priority=Priority(data["priority"]),
                summary=data["summary"],
                action_suggestion=data["action_suggestion"],
                should_archive=bool(data["should_archive"]),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(
                f"Failed to parse Claude response for '{email.subject}': {e}\nRaw: {raw[:200]}"
            )
            return None
