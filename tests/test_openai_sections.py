from src.llm.openai_sections import _story_copy_aligned, _story_topic_aligned


def test_story_topic_guard_accepts_a_close_rewrite():
    assert _story_topic_aligned(
        "Bond yields rise as investors reprice rates",
        "Rising bond yields force a market repricing",
    )


def test_story_topic_guard_rejects_an_unrelated_rewrite():
    assert not _story_topic_aligned(
        "Bond yields rise as investors reprice rates",
        "Big Oil liabilities are shrinking",
    )


def test_story_copy_guard_rejects_generic_unrelated_implication():
    assert not _story_copy_aligned(
        "The cooperative spirit at the heart of the digital euro",
        "Monitor whether the theme affects rates, FX, commodities, and sector leadership.",
    )


def test_story_copy_guard_accepts_topic_specific_implication():
    assert _story_copy_aligned(
        "The cooperative spirit at the heart of the digital euro",
        "The digital euro could change European payments infrastructure.",
    )
