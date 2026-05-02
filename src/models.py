from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    WORK = "AI-Organizer/仕事"
    PERSONAL = "AI-Organizer/個人"
    FINANCE = "AI-Organizer/金融・請求"
    SHOPPING = "AI-Organizer/ショッピング"
    NEWSLETTER = "AI-Organizer/ニュースレター"
    SOCIAL = "AI-Organizer/SNS通知"
    NOTIFICATION = "AI-Organizer/通知"
    OTHER = "AI-Organizer/その他"


# Emails in these categories are automatically archived (removed from inbox)
AUTO_ARCHIVE_CATEGORIES = {Category.NEWSLETTER, Category.SOCIAL}


@dataclass
class EmailMessage:
    message_id: str
    thread_id: str
    subject: str
    sender: str
    snippet: str
    date: str
    body_text: str
    label_ids: list = field(default_factory=list)

    # Populated by ai_analyzer
    category: Optional[Category] = None
    priority: Optional[Priority] = None
    summary: Optional[str] = None
    action_suggestion: Optional[str] = None
    ai_analyzed: bool = False


@dataclass
class AnalysisResult:
    category: Category
    priority: Priority
    summary: str
    action_suggestion: str
    should_archive: bool


@dataclass
class DailySummary:
    date: str
    total_unread: int
    analyzed_count: int
    archived_count: int
    high_priority: list = field(default_factory=list)
    medium_priority: list = field(default_factory=list)
    low_priority: list = field(default_factory=list)
    unanalyzed: list = field(default_factory=list)
    errors: list = field(default_factory=list)
