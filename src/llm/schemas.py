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
    ytd_change: float = 0.0
    driver: str
    source: SourceItem
    latest_date: str | None = None
    is_stale: bool | None = None
    confidence_score: float | None = None
    comment_method: str | None = None
    driver_1w: str | None = None
    driver_1m: str | None = None
    driver_ytd: str | None = None
    portfolio_relevance: str | None = None


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
    signals: list[dict] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)


class StoryOfTheWeek(BaseModel):
    title: str
    narrative: str
    implications: list[str]
    sources: list[SourceItem]
    selection_signal: dict = Field(default_factory=dict)
    openai_rewrite_status: str | None = None


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
    subtitle: str | None = None
    takeaway: str | None = None
    source: dict | None = None
    source_name: str | None = None
    source_type: str | None = None
    published_at: str | None = None
    original_url: str | None = None
    image_url: str | None = None
    local_image_path: str | None = None
    image_src: str | None = None
    email_image_src: str | None = None
    preview_image_src: str | None = None
    summary: str | None = None
    portfolio_relevance: str | None = None
    extraction_method: str | None = None
    copyright_note: str | None = None
    compliance_approved: bool | None = None
    embedded_image: bool | None = None
    fallback_mode: bool | None = None
    generated_at: str | None = None
    rotation_week_number: int | None = None
    rotation_selected_source: str | None = None
    source_attempts: list[dict] = Field(default_factory=list)
    chart_id: str | None = None
    series_used: list[str] = Field(default_factory=list)
    transformation_used: dict | None = None
    latest_values: dict[str, float] = Field(default_factory=dict)
    unit_label: str | None = None
    lookback: str | None = None
    market_signal_reason: str | None = None
    selection_score: float | None = None
    fred_chart_scores: list[dict] = Field(default_factory=list)
    chart_selection_history_updated: bool | None = None
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
    provider_used: str | None = None
    missing_proxies: list[dict] = Field(default_factory=list)
    stale_prices: list[dict] = Field(default_factory=list)
    document_count: int | None = None
    source_count: int | None = None
    baseline_periods: int | None = None
    status_counts: dict[str, int] = Field(default_factory=dict)
    history_updated: bool | None = None
    model_version: str | None = None


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
