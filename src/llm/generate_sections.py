from __future__ import annotations

from src.analysis.story_selector import select_story_of_the_week
from src.llm.openai_sections import enhance_sections_with_openai


def source_from_article(article: dict) -> dict:
    return {"name": article.get("source", "Source"), "url": article.get("url")}


def make_section(title: str, bullets: list[str], sources: list[dict]) -> dict:
    return {"title": title, "bullets": bullets, "sources": sources}


def generate_sections(data: dict) -> dict:
    ranked = data["ranked_articles"]
    top_sources = [source_from_article(article) for article in ranked[:5]]
    sections: dict = {}

    sections["executive_snapshot"] = make_section(
        "Executive Snapshot",
        [
            "Cross-asset focus remains on rates, USD direction, commodity supply signals, and sector leadership.",
            "Portfolio relevance is weighted toward current equity holdings and issuer-level fixed income exposure.",
            "Manual/private pricing issues are retained in audit logs rather than repeated in the newsletter body.",
        ],
        top_sources,
    )

    equity_data = data.get("equity_monitor", {})
    if equity_data:
        sections["portfolio_snapshot"] = {
            "title": "Portfolio Snapshot",
            "kpis": equity_data.get("kpis", []),
            "top_holdings": equity_data.get("top_holdings", []),
            "manual_pricing_count": equity_data.get("manual_pricing_count", 0),
            "invalid_or_manual_holdings": equity_data.get("invalid_or_manual_holdings", []),
        }
        sections["equity_holdings_monitor"] = equity_data

    if data.get("chart_of_the_week"):
        sections["chart_of_the_week"] = data["chart_of_the_week"]

    if data.get("narrative_monitor"):
        sections["narrative_monitor"] = data["narrative_monitor"]

    sections["fx_markets"] = {"title": "FX Markets", "rows": data["fx"]}
    sections["commodities"] = {"title": "Commodities", "rows": data["commodities"]}
    sectors = data["sectors"]
    sections["sector_scoreboard"] = sectors if isinstance(sectors, dict) else {"title": "Sector Scoreboard", "rows": sectors}

    sections["macro_news"] = build_macro_news_section(data.get("macro", []), ranked)

    sections["private_markets"] = build_private_markets_section(data.get("private_markets", []), data.get("macro", []))

    sections["portfolio_linked_news"] = data.get(
        "portfolio_linked_news",
        {"title": "Portfolio-Linked News", "items": [], "empty_message": "No material portfolio-linked news captured from configured sources this week."},
    )

    sections["regional_headlines"] = data.get("regional_headlines", {"title": "Regional Headlines", "regions": []})

    sections["story_of_the_week"] = select_story_of_the_week(ranked)

    sections["portfolio_watchlist"] = data.get("portfolio_watchlist", {"title": "What to Watch This Week", "rows": []})

    sections["executive_snapshot"]["signals"] = _build_executive_signals(data, sections)

    return enhance_sections_with_openai(sections, data)


def _build_executive_signals(data: dict, sections: dict) -> list[dict]:
    signals = []
    macro_items = sections.get("macro_news", {}).get("items", [])
    if macro_items:
        item = macro_items[0]
        signals.append(
            _signal(
                "Macro",
                item.get("theme", "Macro conditions in focus"),
                item.get("summary") or item.get("market_implication", ""),
                "HIGH" if _contains_risk_terms(item.get("summary", "")) else "MEDIUM",
                _first_source(item.get("sources", [])),
            )
        )

    fx_row = _largest_move(data.get("fx", []), "one_week_change")
    if fx_row:
        signals.append(
            _signal(
                "FX",
                _move_headline(fx_row.get("label", "FX"), fx_row.get("one_week_change", 0)),
                fx_row.get("driver", ""),
                _move_risk(fx_row.get("one_week_change", 0), 1.0),
                fx_row.get("source"),
            )
        )

    commodity_row = _largest_move(data.get("commodities", []), "one_week_change")
    if commodity_row:
        signals.append(
            _signal(
                "Commodities",
                _move_headline(commodity_row.get("label", "Commodity"), commodity_row.get("one_week_change", 0)),
                commodity_row.get("driver", ""),
                _move_risk(commodity_row.get("one_week_change", 0), 3.0),
                commodity_row.get("source"),
            )
        )

    sector_row, sector_region = _largest_sector_move(data.get("sectors", {}))
    if sector_row:
        signals.append(
            _signal(
                "Equities",
                _move_headline(f"{sector_row.get('sector', 'Sector')} / {sector_region}", sector_row.get("one_week", 0)),
                sector_row.get("comment", ""),
                _move_risk(sector_row.get("one_week", 0), 3.0),
                sector_row.get("source"),
            )
        )

    equity = data.get("equity_monitor", {})
    linked_items = sections.get("portfolio_linked_news", {}).get("items", [])
    portfolio_detail = equity.get("interpretation") or "Portfolio headlines are ranked against current equity exposures."
    portfolio_headline = "Portfolio concentration remains the key lens"
    portfolio_source = None
    if linked_items:
        linked = linked_items[0]
        portfolio_headline = linked.get("news_theme") or linked.get("name") or portfolio_headline
        portfolio_detail = linked.get("why_it_matters") or portfolio_detail
        portfolio_source = linked.get("source")
    signals.append(_signal("Portfolio", portfolio_headline, portfolio_detail, "MEDIUM", portfolio_source))
    return signals[:5]


def _signal(label: str, headline: str, detail: str, risk: str, source: dict | None) -> dict:
    return {
        "label": label,
        "headline": str(headline)[:120],
        "detail": str(detail)[:260],
        "risk": risk,
        "source": source or {},
    }


def _largest_move(rows: list[dict], field: str) -> dict | None:
    return max(rows, key=lambda row: abs(float(row.get(field) or 0)), default=None)


def _largest_sector_move(section: dict) -> tuple[dict | None, str]:
    candidates = []
    for block in section.get("regions", []) if isinstance(section, dict) else []:
        region = block.get("label") or block.get("region") or "Equities"
        candidates.extend((row, region) for row in block.get("rows", []))
    if not candidates:
        return None, ""
    return max(candidates, key=lambda pair: abs(float(pair[0].get("one_week") or 0)))


def _move_headline(label: str, value: float) -> str:
    direction = "rose" if float(value or 0) > 0 else "fell" if float(value or 0) < 0 else "was flat"
    return f"{label} {direction} {abs(float(value or 0)):.2f}% over the week"


def _move_risk(value: float, threshold: float) -> str:
    magnitude = abs(float(value or 0))
    if magnitude >= threshold * 2:
        return "HIGH"
    if magnitude >= threshold:
        return "MEDIUM"
    return "LOW"


def _contains_risk_terms(value: str) -> bool:
    text = str(value).lower()
    return any(term in text for term in ("war", "conflict", "shock", "crisis", "recession", "surge", "plunge"))


def _first_source(sources: list[dict]) -> dict | None:
    return sources[0] if sources else None


def build_macro_news_section(macro_rows: list[dict], articles: list[dict]) -> dict:
    themes = [
        ("Rates and yields", ("yield", "rates", "treasury", "fed", "policy"), "Rates affect equity duration, valuation multiples, REITs, utilities, and FX translation risk."),
        ("Inflation", ("inflation", "cpi", "prices"), "Inflation affects policy rates, real yields, airlines, utilities, and margin pressure."),
        ("Labour market", ("jobs", "payrolls", "unemployment", "labour", "labor"), "Labour cooling changes Fed reaction-function risk and demand sensitivity."),
        ("Credit conditions", ("credit", "spread", "financial conditions", "liquidity"), "Credit conditions affect private-market exits, refinancing risk, and risk appetite."),
        ("Europe growth and ECB path", ("ecb", "europe", "eurozone", "germany", "france"), "European growth affects Allianz, BMW, RWE, Sanofi, ING, and Meta Wolf AG."),
        ("China / APAC growth", ("china", "singapore", "apac", "asia"), "APAC growth affects Alibaba, SATS, Singapore Airlines, Sembcorp, CapitaLand, and SGD exposure."),
    ]
    items = []
    used_urls = set()
    for theme, keywords, relevance in themes:
        source_article = _best_article(articles, keywords, used_urls)
        data_point = _best_macro_row(macro_rows, keywords)
        if not source_article and not data_point:
            continue
        if source_article:
            used_urls.add(source_article.get("url"))
        changed = _summary_from_article_or_data(source_article, data_point)
        items.append(
            {
                "theme": theme,
                "summary": changed,
                "market_implication": _macro_implication(theme, data_point),
                "portfolio_relevance": relevance,
                "sources": _sources(source_article, data_point),
            }
        )
        if len(items) >= 6:
            break
    return {"title": "Macro News", "items": items, "empty_message": "No material macro update captured from configured sources this week."}


def build_private_markets_section(private_articles: list[dict], macro_rows: list[dict]) -> dict:
    private_articles = [article for article in private_articles if _is_real_source_article(article)]
    themes = [
        ("Private credit fundraising", ("private credit", "direct lending", "fundraising"), "Funding availability is a read-through for refinancing windows and risk appetite."),
        ("Exit window and IPO activity", ("exit", "ipo", "listing", "m&a"), "Exit activity affects valuation marks, distributions, and reinvestment timing."),
        ("Valuation gaps", ("valuation", "buyer", "seller", "gap"), "Wide valuation gaps can slow deal activity and delay liquidity."),
        ("LP liquidity and secondaries", ("lp", "liquidity", "secondaries", "secondary"), "LP liquidity pressure can affect commitments and secondary-market pricing."),
        ("Asia deal activity", ("asia", "singapore", "china", "india", "apac"), "Asia activity matters for regional allocation and growth exposure."),
        ("Credit spreads and refinancing risk", ("credit", "spread", "refinancing"), "Credit spread pressure affects financing costs and private-market transaction windows."),
    ]
    items = []
    used_urls = set()
    for theme, keywords, relevance in themes:
        article = _best_article(private_articles, keywords, used_urls)
        if not article:
            continue
        used_urls.add(article.get("url"))
        items.append(
            {
                "theme": theme,
                "summary": _short_article_summary(article),
                "why_it_matters": _private_why(theme),
                "portfolio_relevance": relevance,
                "sources": [source_from_article(article)],
            }
        )
        if len(items) >= 5:
            break
    if not items:
        credit_row = _best_macro_row(macro_rows, ("credit", "financial conditions"))
        if credit_row:
            items.append(
                {
                    "theme": "Credit conditions",
                    "summary": credit_row.get("comment", ""),
                    "why_it_matters": "Credit conditions help frame private-market funding and exit windows.",
                    "portfolio_relevance": "Use as context for private-market liquidity and transaction risk.",
                    "sources": [credit_row.get("source")],
                }
            )
    return {
        "title": "Private Markets",
        "items": items,
        "empty_message": "No material private-market update captured from configured sources this week.",
    }


def _best_article(articles: list[dict], keywords: tuple[str, ...], used_urls: set[str]) -> dict | None:
    for article in articles:
        if not article.get("url") or article.get("url") in used_urls:
            continue
        if not _is_real_source_article(article):
            continue
        text = f"{article.get('title', '')} {article.get('summary', '')} {article.get('category', '')}".lower()
        if any(keyword in text for keyword in keywords):
            return article
    return None


def _is_real_source_article(article: dict) -> bool:
    url = str(article.get("url", ""))
    return bool(url) and "example.com/wolf-research" not in url and article.get("source") != "Sample Data"


def _best_macro_row(rows: list[dict], keywords: tuple[str, ...]) -> dict | None:
    for row in rows:
        text = f"{row.get('indicator', '')} {row.get('comment', '')}".lower()
        if any(keyword in text for keyword in keywords):
            return row
    return None


def _summary_from_article_or_data(article: dict | None, data_point: dict | None) -> str:
    if article:
        return _short_article_summary(article)
    if data_point:
        return f"{data_point.get('indicator')}: {data_point.get('value')}. {data_point.get('comment', '')}"
    return ""


def _short_article_summary(article: dict) -> str:
    summary = article.get("summary") or article.get("description") or ""
    title = article.get("title", "")
    return summary[:210] if summary else title


def _macro_implication(theme: str, data_point: dict | None) -> str:
    value = f" Latest data: {data_point.get('value')}." if data_point and data_point.get("value") else ""
    mapping = {
        "Rates and yields": "Discount-rate sensitivity remains the main transmission channel for equities and FX.",
        "Inflation": "Inflation data changes rate-cut timing, real yields, and margin expectations.",
        "Labour market": "Labour data affects recession risk, consumption, and central-bank reaction functions.",
        "Credit conditions": "Credit conditions influence risk appetite, funding costs, and private-market liquidity.",
        "Europe growth and ECB path": "European macro data frames earnings risk and rate expectations.",
        "China / APAC growth": "APAC data affects China-linked demand, Singapore exposures, and regional FX.",
    }
    return mapping.get(theme, "Monitor for cross-asset repricing.") + value


def _private_why(theme: str) -> str:
    mapping = {
        "Private credit fundraising": "Fundraising momentum indicates investor appetite for yield and direct-lending risk.",
        "Exit window and IPO activity": "Exit conditions affect distributions, marks, and manager liquidity.",
        "Valuation gaps": "Pricing gaps can keep deal volumes muted and delay exits.",
        "LP liquidity and secondaries": "Secondary-market activity reveals pressure points in institutional portfolios.",
        "Asia deal activity": "Regional transaction activity affects APAC allocation and growth exposure.",
        "Credit spreads and refinancing risk": "Spread pressure can reduce leverage availability and transaction appetite.",
    }
    return mapping.get(theme, "Relevant for capital allocation, liquidity, and risk appetite.")


def _sources(article: dict | None, data_point: dict | None) -> list[dict]:
    sources = []
    if article:
        sources.append(source_from_article(article))
    if data_point and data_point.get("source"):
        sources.append(data_point["source"])
    return sources
