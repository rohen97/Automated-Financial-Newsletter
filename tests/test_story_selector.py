from src.analysis.story_selector import select_story_of_the_week


def _article(title: str, score: float) -> dict:
    return {
        "title": title,
        "summary": f"Summary for {title}",
        "source": "Reuters",
        "url": f"https://example.test/{title.lower().replace(' ', '-')}",
        "importance_score": score,
    }


def test_emerging_narrative_can_promote_a_close_feature_candidate():
    articles = [
        _article("General equity market update", 0.82),
        _article("Oil price shock reaches inflation expectations", 0.76),
    ]
    monitor = {
        "rows": [
            {
                "phrase": "Oil Price",
                "status": "Accelerating",
                "source_count": 4,
                "article_count": 9,
            }
        ]
    }

    story = select_story_of_the_week(articles, monitor)

    assert story["title"].startswith("Oil price")
    assert story["selection_signal"]["phrase"] == "Oil Price"
    assert story["selection_signal"]["boost"] > 0


def test_fading_narrative_does_not_override_a_stronger_article():
    articles = [
        _article("General equity market update", 0.82),
        _article("Oil price stabilises", 0.75),
    ]
    monitor = {
        "rows": [
            {
                "phrase": "Oil Price",
                "status": "Fading",
                "source_count": 2,
                "article_count": 3,
            }
        ]
    }

    story = select_story_of_the_week(articles, monitor)

    assert story["title"] == "General equity market update"
    assert story["selection_signal"] == {}


def test_summary_only_topic_noise_does_not_receive_a_narrative_boost():
    noisy = _article("Big Oil liabilities are shrinking", 0.82)
    noisy["summary"] = "Plus, soaring bond yields spook investors."
    coherent = _article("Bond yields rise as investors reprice rates", 0.78)
    monitor = {
        "rows": [
            {
                "phrase": "Bond Yield",
                "status": "Accelerating",
                "source_count": 5,
                "article_count": 8,
            }
        ]
    }

    story = select_story_of_the_week([noisy, coherent], monitor)

    assert story["title"] == coherent["title"]
    assert story["selection_signal"]["match_field"] == "title_or_entity"


def test_coherent_summary_can_supply_a_lower_weight_topic_match():
    article = _article("Digital euro project reaches its next stage", 0.78)
    article["summary"] = "The central bank advanced the digital euro project after its latest review."
    monitor = {
        "rows": [
            {
                "phrase": "Central Bank",
                "status": "Accelerating",
                "source_count": 4,
                "article_count": 7,
            }
        ]
    }

    story = select_story_of_the_week([article], monitor)

    assert story["selection_signal"]["match_field"] == "summary"
    assert 0 < story["selection_signal"]["boost"] < 0.12


def test_digital_euro_story_gets_topic_specific_fallback_implication():
    article = _article("The cooperative spirit at the heart of the digital euro", 0.8)
    article["summary"] = "An ECB lecture on the digital euro project."

    story = select_story_of_the_week([article])

    assert "European payments infrastructure" in story["implications"][0]
    assert "commodities and sector leadership" not in story["implications"][0]
