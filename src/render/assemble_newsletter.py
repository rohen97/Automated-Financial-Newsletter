from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from src.llm.schemas import Newsletter
from src.utils.io import project_path


def assemble_newsletter(title: str, timezone: str, sections: dict, warnings: list[str] | None = None) -> Newsletter:
    return Newsletter(
        title=title,
        generated_at=datetime.now().astimezone(),
        timezone=timezone,
        sections=sections,
        warnings=warnings or [],
    )


def newsletter_to_markdown(newsletter: Newsletter) -> str:
    data = newsletter.model_dump(mode="json")
    lines = [f"# {data['title']}", "", f"Generated: {data['generated_at']}", ""]
    for key, section in data["sections"].items():
        lines.extend([f"## {section_title(key)}", ""])
        if isinstance(section, dict) and "bullets" in section:
            lines.extend(f"- {bullet}" for bullet in section.get("bullets", []))
        elif isinstance(section, dict) and "kpis" in section:
            for kpi in section.get("kpis", []):
                lines.append(f"- **{kpi['label']}**: {kpi['value']}")
            lines.append("")
            lines.append("| Holding | Currency | Sector | Current Value | YTD P&L | YTD % |")
            lines.append("|---|---|---|---:|---:|---:|")
            for holding in section.get("top_holdings", []):
                lines.append(
                    f"| {holding['holding']} | {holding['currency']} | {holding['sector']} | "
                    f"{holding['current_value_display']} | {holding['ytd_pnl_display']} | {holding['ytd_pct_display']} |"
                )
        elif isinstance(section, dict) and "top_contributors" in section:
            if section.get("interpretation"):
                lines.append(section["interpretation"])
            lines.append("")
            lines.append("| Holding | Sector | Currency | Current Value | YTD P&L | YTD % |")
            lines.append("|---|---|---|---:|---:|---:|")
            for holding in section.get("top_holdings", []):
                lines.append(
                    f"| {holding['holding']} | {holding['sector']} | {holding['currency']} | "
                    f"{holding['current_value_display']} | {holding['ytd_pnl_display']} | {holding['ytd_pct_display']} |"
                )
        elif isinstance(section, dict) and "items" in section:
            if section.get("items"):
                for item in section["items"]:
                    lines.append(f"- {item.get('name')}: {item.get('news_theme')} - {item.get('why_it_matters')}")
            else:
                lines.append(section.get("empty_message", "No material update captured."))
        elif isinstance(section, dict) and "regions" in section:
            for group in section.get("regions", []):
                lines.append(f"### {group['region']}")
                if group.get("headlines"):
                    for item in group["headlines"]:
                        lines.append(f"- {item['headline']} ({item['source']}, {item['category']})")
                else:
                    lines.append("- No material update captured from configured sources.")
        elif isinstance(section, dict) and "top_holdings" in section:
            lines.append("| Holding | Asset Class | Region | Currency | Weight |")
            lines.append("|---|---|---|---|---:|")
            for holding in section.get("top_holdings", []):
                lines.append(
                    f"| {holding['holding']} | {holding['asset_class']} | {holding['region']} | "
                    f"{holding['currency']} | {holding['weight']:.0%} |"
                )
            for flag in section.get("flags", []):
                lines.append(f"- {flag}")
        elif isinstance(section, dict) and "rows" in section:
            first = section["rows"][0] if section["rows"] else {}
            if "sector" in first:
                lines.append("| Sector | 1W | 1M | YTD | Comment |")
                lines.append("|---|---:|---:|---:|---|")
                for row in section["rows"]:
                    lines.append(f"| {row['sector']} | {row['one_week']} | {row['one_month']} | {row['ytd']} | {row['comment']} |")
            else:
                lines.append("| Asset | Last | 1W | 1M | Driver |")
                lines.append("|---|---:|---:|---:|---|")
                for row in section["rows"]:
                    lines.append(f"| {row['label']} | {row['last']} | {row['one_week_change']} | {row['one_month_change']} | {row['driver']} |")
        elif isinstance(section, dict) and "narrative" in section:
            lines.append(section["narrative"])
            lines.extend(f"- {item}" for item in section.get("implications", []))
        elif isinstance(section, list):
            for item in section:
                title = item.get("title") or item.get("event")
                detail = item.get("why_it_matters", "")
                lines.append(f"- {title}" + (f": {detail}" if detail else ""))
        lines.append("")
    if data.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in data["warnings"])
    return "\n".join(lines).strip() + "\n"


def change_class(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return ""


def format_change(value: float) -> str:
    return f"{value:+.2f}"


def heat_class(value: float) -> str:
    if value > 0:
        return "heat-positive positive"
    if value < 0:
        return "heat-negative negative"
    return "heat-neutral neutral"


def display_header_date(generated_at: str, timezone: str) -> str:
    value = datetime.fromisoformat(generated_at)
    local = value.astimezone(ZoneInfo(timezone))
    day = local.strftime("%A")
    month = local.strftime("%B")
    return f"{day}, {local.day} {month} {local.year} | 9:00am SGT"


def executive_cards(sections: dict) -> list[dict[str, str]]:
    macro = sections.get("macro_news", {})
    fx = sections.get("fx_markets", {})
    commodities = sections.get("commodities", {})
    private = sections.get("private_markets", {})
    watchlist = sections.get("portfolio_watchlist", {})
    portfolio = sections.get("portfolio_snapshot", {})

    def first_bullet(section: dict, fallback: str) -> str:
        bullets = section.get("bullets") or []
        return bullets[0] if bullets else fallback

    def first_row_label(section: dict, fallback: str) -> str:
        rows = section.get("rows") or []
        return rows[0].get("driver", fallback) if rows else fallback

    def first_event(section: dict, fallback: str) -> str:
        rows = section.get("rows") or []
        return rows[0].get("event", fallback) if rows else fallback

    return [
        {
            "label": "Macro",
            "takeaway": first_bullet(macro, "Policy path remains central."),
            "implication": "Discount-rate sensitivity stays in focus.",
        },
        {
            "label": "FX",
            "takeaway": first_row_label(fx, "Broad USD momentum."),
            "implication": "Monitor translation and hedging risk.",
        },
        {
            "label": "Commodities",
            "takeaway": first_row_label(commodities, "Supply-demand balance in focus."),
            "implication": "Watch inflation and margin channels.",
        },
        {
            "label": "Private Markets",
            "takeaway": first_bullet(private, "Exit timing remains selective."),
            "implication": "Liquidity and valuations remain key.",
        },
        {
            "label": "Watchlist",
            "takeaway": first_event(watchlist, "Inflation and central banks."),
            "implication": "Potential cross-asset catalyst.",
        },
        {
            "label": "Portfolio",
            "takeaway": f"{len(portfolio.get('top_holdings', []))} key holdings monitored." if portfolio else "Portfolio file not loaded.",
            "implication": "Headlines ranked by exposure relevance.",
        },
    ]


def render_newsletter_html(newsletter: Newsletter | dict) -> str:
    if isinstance(newsletter, dict):
        newsletter = assemble_newsletter(
            newsletter["title"],
            newsletter["timezone"],
            newsletter["sections"],
            newsletter.get("warnings", []),
        )
    template_path = project_path("templates", "newsletter.html.j2")
    css_path = project_path("assets", "newsletter.css")
    if template_path.exists():
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape

            env = Environment(
                loader=FileSystemLoader(str(template_path.parent)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            template = env.get_template(template_path.name)
            css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
            return template.render(
                newsletter=newsletter.model_dump(mode="json"),
                css=css,
                change_class=change_class,
                format_change=format_change,
                heat_class=heat_class,
                display_header_date=display_header_date,
                executive_cards=executive_cards,
            )
        except Exception:
            return newsletter_to_basic_html(newsletter)
    return newsletter_to_basic_html(newsletter)


def newsletter_to_basic_html(newsletter: Newsletter) -> str:
    css_path = project_path("assets", "newsletter.css")
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    data = newsletter.model_dump(mode="json")
    sections = data.get("sections", {})
    parts = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{escape(data['title'])}</title><style>{css}</style></head><body>",
        "<table role='presentation' class='page' width='100%'><tr><td align='center'>",
        "<table role='presentation' class='container' width='720'>",
        "<tr><td class='masthead'>",
        "<div class='brand'>Wolf Research</div>",
        f"<h1 class='title'>{escape(data['title'])}</h1>",
        f"<div class='date'>{escape(display_header_date(data['generated_at'], data['timezone']))}</div>",
        "<div class='distribution'>Internal Office Distribution</div>",
        "</td></tr>",
    ]

    parts.append("<tr><td class='section'><div class='kicker'>At a Glance</div><h2 class='section-title'>Executive Snapshot</h2>")
    parts.append("<table role='presentation' class='snapshot-grid' width='100%'>")
    cards = executive_cards(sections)
    for idx in range(0, len(cards), 3):
        parts.append("<tr>")
        for card in cards[idx : idx + 3]:
            parts.append(
                "<td class='snapshot-card'>"
                f"<div class='snapshot-label'>{escape(card['label'])}</div>"
                f"<div class='snapshot-takeaway'>{escape(card['takeaway'])}</div>"
                f"<div class='snapshot-implication'>{escape(card['implication'])}</div>"
                "</td>"
            )
        parts.append("</tr>")
    parts.append("</table></td></tr>")

    portfolio = sections.get("portfolio_snapshot")
    if portfolio:
        parts.append("<tr><td class='section'><div class='kicker'>Portfolio Lens</div><h2 class='section-title'>Portfolio Snapshot</h2>")
        parts.append("<table role='presentation' class='snapshot-grid' width='100%'>")
        kpis = portfolio.get("kpis", [])
        for idx in range(0, len(kpis), 3):
            parts.append("<tr>")
            for kpi in kpis[idx : idx + 3]:
                parts.append(
                    "<td class='snapshot-card'>"
                    f"<div class='snapshot-label'>{escape(str(kpi.get('label', '')))}</div>"
                    f"<div class='snapshot-takeaway'>{escape(str(kpi.get('value', '')))}</div>"
                    "</td>"
                )
            parts.append("</tr>")
        parts.append("</table>")
        parts.append("<table class='data-table' width='100%'><tr><th>Holding</th><th>Currency</th><th>Sector</th><th>Current Value</th><th>YTD P&L</th><th>YTD %</th></tr>")
        for holding in portfolio.get("top_holdings", []):
            manual = holding.get("is_manual_pricing")
            value_class = "neutral" if manual else ""
            pnl_class = "neutral" if manual else change_class(float(holding.get("ytd_pnl") or 0))
            pct_class = "neutral" if manual else change_class(float(holding.get("ytd_pct") or 0))
            parts.append(
                "<tr>"
                f"<td>{escape(str(holding.get('holding', '')))}</td>"
                f"<td>{escape(str(holding.get('currency', '')))}</td>"
                f"<td>{escape(str(holding.get('sector', '')))}</td>"
                f"<td class='number {value_class}'>{escape(str(holding.get('current_value_display', '')))}</td>"
                f"<td class='number {pnl_class}'>{escape(str(holding.get('ytd_pnl_display', '')))}</td>"
                f"<td class='number {pct_class}'>{escape(str(holding.get('ytd_pct_display', '')))}</td>"
                "</tr>"
            )
        parts.append("</table></td></tr>")

    equity = sections.get("equity_holdings_monitor")
    if equity:
        parts.append("<tr><td class='section'><div class='kicker'>Equity Book</div><h2 class='section-title'>Equity Holdings Monitor</h2>")
        if equity.get("interpretation"):
            parts.append(f"<div class='callout'>{escape(equity['interpretation'])}</div>")
        parts.append(_simple_holdings_table("Top Equity Contributors", equity.get("top_contributors", [])))
        parts.append(_simple_holdings_table("Top Equity Detractors", equity.get("top_detractors", [])))
        parts.append(_exposure_table("Sector Exposure", "Sector", equity.get("sector_exposure", [])))
        parts.append(_exposure_table("Currency Exposure", "Currency", equity.get("currency_exposure", [])))
        parts.append("</td></tr>")

    fixed_income = sections.get("fixed_income_monitor")
    if fixed_income:
        parts.append("<tr><td class='section-tight'><div class='kicker'>Fixed Income</div><h2 class='section-title'>Fixed Income Monitor</h2>")
        if fixed_income.get("mode") == "position-level":
            parts.append("<table class='data-table' width='100%'><tr><th>Issuer</th><th>Count</th><th>Type</th><th>Region</th><th>Market Value</th><th>Gain/Loss</th></tr>")
            for row in fixed_income.get("rows", []):
                parts.append(
                    "<tr>"
                    f"<td>{escape(str(row.get('issuer', '')))}</td><td class='number'>{escape(str(row.get('count', '')))}</td>"
                    f"<td>{escape(str(row.get('type', '')))}</td><td>{escape(str(row.get('region', '')))}</td>"
                    f"<td class='number'>{escape(str(row.get('market_value_display', '')))}</td>"
                    f"<td class='number {change_class(float(row.get('gain_loss_usd') or 0))}'>{escape(str(row.get('gain_loss_display', '')))}</td>"
                    "</tr>"
                )
        else:
            parts.append("<table class='data-table' width='100%'><tr><th>Issuer</th><th>Count</th><th>Type</th><th>Region</th><th>Notes</th></tr>")
            for row in fixed_income.get("rows", []):
                parts.append(
                    "<tr>"
                    f"<td>{escape(str(row.get('issuer', '')))}</td><td class='number'>{escape(str(row.get('count', '')))}</td>"
                    f"<td>{escape(str(row.get('type', '')))}</td><td>{escape(str(row.get('region', '')))}</td>"
                    f"<td>{escape(str(row.get('notes', '')))}</td>"
                    "</tr>"
                )
        parts.append("</table>")
        if fixed_income.get("note"):
            parts.append(f"<div class='section-note'>{escape(fixed_income['note'])}</div>")
        parts.append("</td></tr>")

    for key in ("fx_markets", "commodities", "sector_scoreboard"):
        section = sections.get(key)
        if section:
            parts.append(_market_table(section, key))

    for key, kicker in (("macro_news", "Macro Pulse"), ("private_markets", "Private Markets")):
        section = sections.get(key)
        if section:
            parts.append(f"<tr><td class='section-tight'><div class='kicker'>{kicker}</div><h2 class='section-title'>{escape(section.get('title', section_title(key)))}</h2>")
            for bullet in section.get("bullets", []):
                parts.append(f"<div class='bullet'>• {escape(str(bullet))}</div>")
            parts.append("</td></tr>")

    linked = sections.get("portfolio_linked_news")
    if linked:
        parts.append("<tr><td class='section-tight'><div class='kicker'>Portfolio-Linked News</div><h2 class='section-title'>Portfolio-Linked News</h2>")
        if linked.get("items"):
            parts.append("<table class='data-table' width='100%'><tr><th>Holding / Issuer</th><th>Region</th><th>Asset Class</th><th>News Theme</th><th>Why It Matters</th><th>Source</th></tr>")
            for item in linked["items"]:
                source = item.get("source", {})
                parts.append(
                    "<tr>"
                    f"<td>{escape(str(item.get('name', '')))}</td><td>{escape(str(item.get('region', '')))}</td>"
                    f"<td>{escape(str(item.get('asset_class', '')))}</td><td>{escape(str(item.get('news_theme', '')))}</td>"
                    f"<td>{escape(str(item.get('why_it_matters', '')))}</td><td>{_link(source.get('url'), source.get('name'))}</td>"
                    "</tr>"
                )
            parts.append("</table>")
        else:
            parts.append(f"<div class='section-note'>{escape(linked.get('empty_message', 'No material portfolio-linked news captured from configured sources this week.'))}</div>")
        parts.append("</td></tr>")

    regional = sections.get("regional_headlines")
    if regional:
        parts.append("<tr><td class='section-tight'><div class='kicker'>Regional Monitor</div><h2 class='section-title'>Regional Headlines</h2>")
        for group in regional.get("regions", []):
            parts.append(f"<div class='region-chip'>{escape(str(group.get('region', '')))}</div>")
            if group.get("headlines"):
                for item in group["headlines"]:
                    parts.append(
                        "<div class='headline'>• "
                        f"{_link(item.get('url'), item.get('headline'))} "
                        f"<span class='source-tag'>{escape(str(item.get('source', 'Source')))}</span> "
                        f"<span class='source'>{escape(str(item.get('category', 'markets')))}</span></div>"
                    )
            else:
                parts.append("<div class='section-note'>No material update captured from configured sources.</div>")
        parts.append("</td></tr>")

    story = sections.get("story_of_the_week")
    if story:
        parts.append("<tr><td class='section'><div class='feature-card'><div class='feature-label'>Story of the Week</div>")
        parts.append(f"<h3>{escape(str(story.get('title', '')))}</h3><p>{escape(str(story.get('narrative', '')))}</p><ul>")
        for item in story.get("implications", []):
            parts.append(f"<li>{escape(str(item))}</li>")
        parts.append("</ul></div></td></tr>")

    watchlist = sections.get("portfolio_watchlist")
    if watchlist:
        parts.append("<tr><td class='section-tight'><div class='kicker'>Forward Watchlist</div><h2 class='section-title'>What to Watch This Week</h2>")
        parts.append("<table class='data-table' width='100%'><tr><th>Period</th><th>Region</th><th>Event / Theme</th><th>Portfolio Relevance</th><th>Asset Classes Affected</th></tr>")
        for row in watchlist.get("rows", []):
            parts.append(
                "<tr>"
                f"<td>{escape(str(row.get('period', '')))}</td><td>{escape(str(row.get('region', '')))}</td>"
                f"<td>{escape(str(row.get('event', '')))}</td><td>{escape(str(row.get('portfolio_relevance', '')))}</td>"
                f"<td>{escape(str(row.get('asset_classes', '')))}</td>"
                "</tr>"
            )
        parts.append("</table></td></tr>")

    parts.append(
        "<tr><td class='footer'>"
        f"<strong>Generated timestamp:</strong> {escape(data['generated_at'])}<br>"
        "Internal distribution only. Analytical context, not investment advice.<br>"
        "Source/audit note: manual/private pricing and issuer-only fixed income limitations are retained in audit logs. "
        "Portfolio relevance is a ranking overlay, not a recommendation engine."
        "</td></tr></table></td></tr></table></body></html>"
    )
    return "".join(parts)


def _link(url: str | None, label: str | None) -> str:
    text = escape(str(label or "Source"))
    if url:
        return f"<a href='{escape(str(url), quote=True)}'>{text}</a>"
    return text


def _simple_holdings_table(title: str, holdings: list[dict]) -> str:
    rows = [f"<h3 class='subhead'>{escape(title)}</h3>"]
    rows.append("<table class='data-table' width='100%'><tr><th>Holding</th><th>Sector</th><th>Currency</th><th>Current Value</th><th>YTD P&L</th><th>YTD %</th></tr>")
    if holdings:
        for holding in holdings:
            rows.append(
                "<tr>"
                f"<td>{escape(str(holding.get('holding', '')))}</td><td>{escape(str(holding.get('sector', '')))}</td>"
                f"<td>{escape(str(holding.get('currency', '')))}</td><td class='number'>{escape(str(holding.get('current_value_display', '')))}</td>"
                f"<td class='number {change_class(float(holding.get('ytd_pnl') or 0))}'>{escape(str(holding.get('ytd_pnl_display', '')))}</td>"
                f"<td class='number {change_class(float(holding.get('ytd_pct') or 0))}'>{escape(str(holding.get('ytd_pct_display', '')))}</td>"
                "</tr>"
            )
    else:
        rows.append("<tr><td colspan='6'>Manual pricing required before ranking is available.</td></tr>")
    rows.append("</table>")
    return "".join(rows)


def _exposure_table(title: str, label: str, exposures: list[dict]) -> str:
    rows = [f"<h3 class='subhead'>{escape(title)}</h3>"]
    rows.append(f"<table class='data-table' width='100%'><tr><th>{escape(label)}</th><th>Current Value</th><th>Weight</th><th>YTD P&L</th></tr>")
    for item in exposures:
        pnl = item.get("ytd_pnl")
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('name', '')))}</td><td class='number'>{escape(str(item.get('current_value_display', '')))}</td>"
            f"<td class='number'>{escape(str(item.get('weight_display', '')))}</td>"
            f"<td class='number {change_class(float(pnl or 0)) if pnl is not None else 'neutral'}'>{escape(str(item.get('ytd_pnl_display', '')))}</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "".join(rows)


def _market_table(section: dict, key: str) -> str:
    title = escape(str(section.get("title", section_title(key))))
    kickers = {
        "fx_markets": "Currency Dashboard",
        "commodities": "Commodity Dashboard",
        "sector_scoreboard": "Sector Heatmap",
    }
    html = [f"<tr><td class='section-tight'><div class='kicker'>{escape(kickers.get(key, 'Market Dashboard'))}</div><h2 class='section-title'>{title}</h2>"]
    if key == "sector_scoreboard":
        html.append("<table class='data-table' width='100%'><tr><th>Sector</th><th>1W</th><th>1M</th><th>YTD</th><th>Comment</th></tr>")
        for row in section.get("rows", []):
            html.append(
                "<tr>"
                f"<td>{escape(str(row.get('sector', '')))}</td>"
                f"<td class='number {heat_class(float(row.get('one_week', 0)))}'>{format_change(float(row.get('one_week', 0)))}</td>"
                f"<td class='number {heat_class(float(row.get('one_month', 0)))}'>{format_change(float(row.get('one_month', 0)))}</td>"
                f"<td class='number {heat_class(float(row.get('ytd', 0)))}'>{format_change(float(row.get('ytd', 0)))}</td>"
                f"<td>{escape(str(row.get('comment', '')))}</td>"
                "</tr>"
            )
    else:
        html.append("<table class='data-table' width='100%'><tr><th>Asset</th><th>Last</th><th>1W</th><th>1M</th><th>Driver</th></tr>")
        for row in section.get("rows", []):
            html.append(
                "<tr>"
                f"<td>{escape(str(row.get('label', '')))}</td><td class='number'>{escape(str(row.get('last', '')))}</td>"
                f"<td class='number {change_class(float(row.get('one_week_change', 0)))}'>{format_change(float(row.get('one_week_change', 0)))}</td>"
                f"<td class='number {change_class(float(row.get('one_month_change', 0)))}'>{format_change(float(row.get('one_month_change', 0)))}</td>"
                f"<td class='driver'>{escape(str(row.get('driver', '')))}</td>"
                "</tr>"
            )
    html.append("</table></td></tr>")
    return "".join(html)


def newsletter_to_html(newsletter: Newsletter) -> str:
    return render_newsletter_html(newsletter)


def section_title(key: str) -> str:
    titles = {
        "fx_markets": "FX Markets",
        "story_of_the_week": "Story of the Week",
        "week_in_headlines": "The Week in Headlines",
        "regional_headlines": "Regional Headlines",
        "portfolio_snapshot": "Portfolio Snapshot",
        "equity_holdings_monitor": "Equity Holdings Monitor",
        "fixed_income_monitor": "Fixed Income Monitor",
        "portfolio_linked_news": "Portfolio-Linked News",
        "portfolio_watchlist": "What to Watch This Week",
    }
    return titles.get(key, key.replace("_", " ").title())
