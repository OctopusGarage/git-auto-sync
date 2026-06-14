from git_auto_sync.models import FileChange
from git_auto_sync.providers.rules import RulesProvider


def test_staging_ignores_secrets_and_large_files():
    p = RulesProvider()
    changes = [
        FileChange("A", "src/main.py", 1200),
        FileChange("A", ".env", 30),
        FileChange("A", "id_rsa.pem", 50),
        FileChange("A", "build/bundle.bin", 50_000_000),
        FileChange("M", "README.md", 400),
    ]
    decision = p.analyze_staging(changes)
    assert "src/main.py" in decision.stage
    assert "README.md" in decision.stage
    assert ".env" in decision.ignore
    assert "id_rsa.pem" in decision.ignore
    assert "build/bundle.bin" in decision.ignore
    assert ".env" not in decision.stage


def test_generate_message_conventional_format():
    p = RulesProvider()
    changes = [FileChange("A", "src/feature.py", 100)]
    msg = p.generate_message(changes, diff_text="")
    assert msg.split(":")[0] in {"feat", "chore", "docs", "fix"}
    assert ":" in msg


def test_generate_message_summarizes_multiple():
    p = RulesProvider()
    changes = [
        FileChange("A", "a.py", 1),
        FileChange("M", "b.py", 1),
        FileChange("D", "c.py", 0),
    ]
    msg = p.generate_message(changes, diff_text="")
    lines = msg.splitlines()
    assert len(lines) == 3
    assert ":" in lines[0]
    assert all(line.startswith("- ") for line in lines[1:])


def test_generate_message_skips_ignored_and_falls_back():
    p = RulesProvider()
    # all changes are ignored -> fallback message
    only_ignored = [FileChange("A", ".env", 10), FileChange("A", "dist/x.bin", 10)]
    assert p.generate_message(only_ignored, diff_text="") == "chore: Sync changes"
    # ignored files are excluded from the summary of a mixed set
    mixed = [FileChange("A", "app.py", 10), FileChange("A", ".env", 10)]
    msg = p.generate_message(mixed, diff_text="")
    assert "app.py" in msg
    assert ".env" not in msg
