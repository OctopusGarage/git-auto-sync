from __future__ import annotations

from pathlib import Path

from git_auto_sync.models import RepoConfig, RepoResult, RunSummary
from git_auto_sync.path_policy import apply_path_policy, status_pathspecs
from git_auto_sync.repo_runtime import build_repo_runtime


def append_gitignore(repo: str | Path, paths: list[str]) -> None:
    """Append paths to .gitignore, skipping ones already present."""
    if not paths:
        return
    gi = Path(repo) / ".gitignore"
    header = "# added by git-auto-sync"
    existing = set()
    if gi.exists():
        existing = {ln.strip() for ln in gi.read_text(encoding="utf-8").splitlines()}
    new = [p for p in paths if p not in existing]
    if not new:
        return
    with open(gi, "a", encoding="utf-8") as f:
        if header not in existing:  # avoid repeating the header across runs
            f.write(f"\n{header}\n")
        for p in new:
            f.write(f"{p}\n")


def should_notify(notify_on: str, summary: RunSummary) -> bool:
    if notify_on == "always":
        return True
    if notify_on == "fail_only":
        return summary.failed
    return summary.changed or summary.failed  # change_or_fail


def sync_repo(cfg: RepoConfig, provider, dry_run: bool = False) -> RepoResult:
    runtime = build_repo_runtime(cfg)
    repo = cfg.path
    pathspecs = status_pathspecs(cfg.path_policy)
    if not runtime.has_changes(pathspecs):
        return RepoResult(path=repo, status="skipped")

    changes = runtime.list_changes(pathspecs)
    policy_result = apply_path_policy(changes, cfg.path_policy)
    changes = policy_result.stage
    ignored: list[str] = []
    blocked: list[str] = policy_result.blocked

    if cfg.ai_staging:
        decision = provider.analyze_staging(changes)
        ignored = [*policy_result.ignored, *decision.ignore]
        if cfg.ai_gitignore_autowrite and not dry_run:
            append_gitignore(runtime.work_tree, [*decision.ignore, *blocked])
        stage_changes = [c for c in changes if c.path in set(decision.stage)]
    else:
        ignored = policy_result.ignored
        stage_changes = changes

    if not stage_changes:
        return RepoResult(path=repo, status="skipped", ignored_paths=ignored, blocked_paths=blocked)

    message = provider.generate_message(stage_changes, diff_text="")

    if dry_run:
        return RepoResult(
            path=repo,
            status="skipped",
            message=message,
            ignored_paths=ignored,
            blocked_paths=blocked,
        )

    ok, err = runtime.add_paths([c.path for c in stage_changes])
    if not ok:
        return RepoResult(
            path=repo,
            status="failed",
            error=f"add failed: {err}",
            ignored_paths=ignored,
            blocked_paths=blocked,
        )

    has_staged, err = runtime.has_staged_changes()
    if err:
        return RepoResult(
            path=repo,
            status="failed",
            error=f"staged changes check failed: {err}",
            ignored_paths=ignored,
            blocked_paths=blocked,
        )
    if not has_staged:
        return RepoResult(
            path=repo,
            status="failed",
            error="add produced no staged changes",
            ignored_paths=ignored,
            blocked_paths=blocked,
        )

    ok, err = runtime.commit(message)
    if not ok:
        return RepoResult(
            path=repo,
            status="failed",
            error=f"commit failed: {err}",
            ignored_paths=ignored,
            blocked_paths=blocked,
        )

    if not cfg.push:
        return RepoResult(
            path=repo,
            status="committed",
            message=message,
            ignored_paths=ignored,
            blocked_paths=blocked,
        )

    # A local commit already exists at this point; on rebase conflict or push
    # failure it stays local and push is retried on the next run.
    ok, err = runtime.pull_rebase()
    if not ok:
        return RepoResult(
            path=repo,
            status="failed",
            error=f"pull --rebase conflict: {err}",
            message=message,
            ignored_paths=ignored,
            blocked_paths=blocked,
        )

    ok, err = runtime.push()
    if not ok:
        return RepoResult(
            path=repo,
            status="failed",
            error=f"push failed: {err}",
            message=message,
            ignored_paths=ignored,
            blocked_paths=blocked,
        )

    return RepoResult(
        path=repo,
        status="committed_pushed",
        message=message,
        ignored_paths=ignored,
        blocked_paths=blocked,
    )


def run_sync(repos: list[RepoConfig], build_provider, dry_run: bool = False) -> RunSummary:
    """Process repos sequentially; one repo failing never blocks the others."""
    summary = RunSummary()
    for cfg in repos:
        try:
            provider = build_provider(cfg.ai_provider)
            result = sync_repo(cfg, provider, dry_run=dry_run)
        except Exception as exc:  # never let one repo abort the run
            result = RepoResult(path=cfg.path, status="failed", error=str(exc))
        summary.results.append(result)
    return summary
