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


class SectorRow(BaseModel):
    sector: str
    one_week: float
    one_month: float
    ytd: float
    comment: str
    source: SourceItem


class SectorTable(BaseModel):
    title: str
    rows: list[SectorRow]


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


class PortfolioExposureItem(BaseModel):
    name: str
    weight: float


class PortfolioSnapshot(BaseModel):
    title: str
    kpis: list[dict] = Field(default_factory=list)
    top_holdings: list[dict] = Field(default_factory=list)
    manual_pricing_count: int = 0
    missing_pricing_count: int = 0
    invalid_or_manual_holdings: list[str] = Field(default_factory=list)


class GenericTableSection(BaseModel):
    title: str
    rows: list[dict] = Field(default_factory=list)
    items: list[dict] = Field(default_factory=list)
    regions: list[dict] = Field(default_factory=list)
    kpis: list[dict] = Field(default_factory=list)
    top_holdings: list[dict] = Field(default_factory=list)
    top_contributors: list[dict] = Field(default_factory=list)
    top_detractors: list[dict] = Field(default_factory=list)
    sector_exposure: list[dict] = Field(default_factory=list)
    currency_exposure: list[dict] = Field(default_factory=list)
    region_exposure: list[dict] = Field(default_factory=list)
    maturity_exposure: list[dict] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    note: str | None = None
    empty_message: str | None = None
    interpretation: str | None = None
    mode: str | None = None
    issuer_count: int | None = None
    position_count: int | None = None
    holdings_count: int | None = None
    usable_equity_pricing_count: int | None = None
    manual_pricing_count: int | None = None
    missing_pricing_count: int | None = None
    total_equity_portfolio_value_usd: float | None = None
    total_ytd_equity_pnl_usd: float | None = None
    best_contributor: str | None = None
    worst_contributor: str | None = None
    largest_sector_exposure: str | None = None
    largest_currency_exposure: str | None = None
    total_market_value_usd: float | None = None
    total_market_value_display: str | None = None
    total_gain_loss_usd: float | None = None
    total_gain_loss_display: str | None = None
    invalid_or_manual_holdings: list[str] = Field(default_factory=list)
    missing_bond_fields: list[str] = Field(default_factory=list)


class Newsletter(BaseModel):
    title: str
    generated_at: datetime
    timezone: str
    sections: dict[
        str,
        NewsletterSection
        | MarketTable
        | SectorTable
        | StoryOfTheWeek
        | PortfolioSnapshot
        | GenericTableSection
        | list[HeadlineItem]
        | list[WatchlistItem],
    ]
    warnings: list[str] = Field(default_factory=list)
