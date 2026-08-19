import json
import time

import pytest

from src.pipeline.cache import TTLFileCache


def test_ttl_cache_records_miss_hit_and_expiry(tmp_path):
    cache = TTLFileCache(tmp_path)
    key = cache.cache_key({"series": "DGS10"})

    assert cache.get("fred", key, 1) is None
    assert cache.set("fred", key, {"value": 4.25}) is True
    assert cache.get("fred", key, 1) == {"value": 4.25}

    cache_file = next((tmp_path / "fred").glob("*.json"))
    envelope = json.loads(cache_file.read_text(encoding="utf-8"))
    envelope["created_epoch"] = time.time() - 7200
    cache_file.write_text(json.dumps(envelope), encoding="utf-8")

    assert cache.get("fred", key, 1) is None
    assert cache.metrics.snapshot() == {
        "cache_hits": 1,
        "cache_misses": 2,
        "cache_expired": 1,
        "cache_writes": 1,
        "cache_disabled_providers": [],
    }


def test_cache_rejects_secret_bearing_payloads(tmp_path):
    cache = TTLFileCache(tmp_path)

    with pytest.raises(ValueError, match="secret-bearing"):
        cache.set("news", "unsafe", {"authorization": "Bearer private"})

    assert not list(tmp_path.rglob("*.json"))
