from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class SourceItem(BaseModel):
    name: str
    url: HttpUrl


class HeadlineItem(BaseModel):
    title: str
    source: SourceItem
    category: str
    importance_score: float = Field(ge=0, le=1)


class MarketRow(BaseModel):
    label: str
    last: float | str
    one_week_change: float
    one_month_change: float
    driver: str
    source: SourceItem


class MarketTable(BaseModel):
    title: str
    rows: list[MarketRow]


class NewsletterSection(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)


class StoryOfTheWeek(BaseModel):
    title: str
    narrative: str
    implications: list[str]
    sources: list[SourceItem]


class WatchlistItem(BaseModel):
    event: str
    why_it_matters: str
    source: SourceItem


class Newsletter(BaseModel):
    title: str
    generated_at: datetime
    timezone: str
    sections: dict[str, NewsletterSection | MarketTable | StoryOfTheWeek | list[HeadlineItem] | list[WatchlistItem]]
    warnings: list[str] = Field(default_factory=list)
