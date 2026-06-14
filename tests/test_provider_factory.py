import pytest

from git_auto_sync.models import FileChange
from git_auto_sync.providers import build_provider


def test_build_rules_provider():
    p = build_provider("rules")
    changes = [FileChange("A", "a.py", 1)]
    assert ":" in p.generate_message(changes, "")


def test_fallback_to_rules_on_error(monkeypatch):
    # claude-cli provider whose underlying call raises -> wrapper returns rules result.
    p = build_provider("claude-cli")

    def boom(*a, **k):
        raise RuntimeError("claude not installed")

    # Patch the inner provider's raw call.
    monkeypatch.setattr(p.inner, "_raw_message", boom, raising=False)
    monkeypatch.setattr(p.inner, "_raw_staging", boom, raising=False)

    changes = [FileChange("A", "a.py", 1)]
    msg = p.generate_message(changes, "")
    assert ":" in msg  # produced by RulesProvider fallback

    decision = p.analyze_staging(changes)
    assert "a.py" in decision.stage  # rules fallback staged it


def test_parse_staging_json():
    from git_auto_sync.providers.claude_cli import parse_staging_json
    d = parse_staging_json('{"stage": ["a.py"], "ignore": [".env"]}')
    assert d.stage == ["a.py"] and d.ignore == [".env"]


def test_parse_staging_json_without_object_raises():
    from git_auto_sync.providers.claude_cli import parse_staging_json
    with pytest.raises(ValueError):
        parse_staging_json("sorry, no json here")


def test_build_provider_unknown_raises():
    with pytest.raises(ValueError):
        build_provider("gpt")
