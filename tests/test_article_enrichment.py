from src.processing.article_enrichment import classify_region


def test_region_classifier_does_not_match_boe_inside_boeing():
    assert classify_region("Moody's places all of Boeing's ratings on review") != "UK"


def test_region_classifier_recognizes_bank_of_england_abbreviation():
    assert classify_region("BOE seen on hold despite inflation spike") == "UK"


def test_region_classifier_recognizes_libya_as_emea():
    assert classify_region("Libya seeks investment to develop oil resources") == "EMEA"
