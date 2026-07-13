from git_auto_sync.models import RepoResult, RunSummary
from git_auto_sync.notifiers import build_notifiers, format_summary


def test_format_summary_lists_repos():
    s = RunSummary(
        results=[
            RepoResult(path="/a", status="committed_pushed", message="feat: x"),
            RepoResult(path="/b", status="failed", error="push rejected"),
        ]
    )
    text = format_summary(s)
    assert "feat: x" in text
    assert "push rejected" in text


def test_format_summary_lists_blocked_paths():
    s = RunSummary(
        results=[
            RepoResult(path="/home", status="skipped", blocked_paths=[".npmrc", "cert.pem"]),
        ]
    )
    text = format_summary(s)
    assert "Blocked: .npmrc, cert.pem" in text


def test_format_summary_shortens_home_paths(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    s = RunSummary(
        results=[
            RepoResult(path=str(home), status="skipped"),
            RepoResult(path=str(home / ".alcove"), status="failed", error="push rejected"),
        ]
    )

    text = format_summary(s)

    assert "No changes  ~" in text
    assert "Failed  ~/.alcove" in text
    assert str(home) not in text


def test_log_notifier_writes_file(tmp_path):
    logfile = tmp_path / "sync.log"
    notifiers = build_notifiers({"log": {"enabled": True, "path": str(logfile)}})
    notifiers[0].send("hello world")
    assert "hello world" in logfile.read_text()


def test_telegram_notifier_posts(monkeypatch):
    sent = {}

    def fake_post(url, **kwargs):
        sent["url"] = url
        sent["json"] = kwargs.get("json")

        class R:
            def raise_for_status(self):
                pass

        return R()

    import git_auto_sync.notifiers.telegram as tg

    monkeypatch.setattr(tg.requests, "post", fake_post)
    notifiers = build_notifiers({"telegram": {"enabled": True, "bot_token": "T", "chat_id": "42"}})
    notifiers[0].send("hi")
    assert "T" in sent["url"]
    assert sent["json"]["chat_id"] == "42"
    assert sent["json"]["text"] == "hi"


def test_disabled_notifier_skipped():
    notifiers = build_notifiers({"telegram": {"enabled": False, "bot_token": "T"}})
    assert notifiers == []
