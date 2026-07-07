from git_auto_sync.models import FileChange, PathPolicyConfig
from git_auto_sync.path_policy import apply_path_policy, status_pathspecs


def test_allowlist_stages_only_matching_paths_and_reports_ignored(tmp_path):
    include = tmp_path / "include"
    include.write_text(".zshrc\n.config/starship.toml\n.claude/hooks/*.sh\n")
    policy = PathPolicyConfig(mode="allowlist", include_file=str(include), builtin_deny=True)
    changes = [
        FileChange("M", ".zshrc"),
        FileChange("M", ".config/starship.toml"),
        FileChange("M", ".claude/hooks/security.sh"),
        FileChange("M", ".ssh/config"),
    ]

    result = apply_path_policy(changes, policy)

    assert [c.path for c in result.stage] == [
        ".zshrc",
        ".config/starship.toml",
        ".claude/hooks/security.sh",
    ]
    assert result.ignored == [".ssh/config"]


def test_builtin_deny_blocks_secrets_even_when_included(tmp_path):
    include = tmp_path / "include"
    include.write_text(".npmrc\n*.pem\n")
    policy = PathPolicyConfig(mode="allowlist", include_file=str(include), builtin_deny=True)

    result = apply_path_policy(
        [FileChange("M", ".npmrc"), FileChange("A", "cert.pem")],
        policy,
    )

    assert result.stage == []
    assert result.blocked == [".npmrc", "cert.pem"]


def test_dot_prefixed_paths_keep_their_dot_when_matching(tmp_path):
    include = tmp_path / "include"
    include.write_text("config/**\n")
    policy = PathPolicyConfig(mode="allowlist", include_file=str(include), builtin_deny=False)

    result = apply_path_policy([FileChange("M", ".config/starship.toml")], policy)

    assert result.stage == []
    assert result.ignored == [".config/starship.toml"]


def test_status_pathspecs_uses_positive_allowlist_rules_only(tmp_path):
    include = tmp_path / "include"
    include.write_text(".zshrc\n!secret\n.claude/hooks/*.sh\n")
    policy = PathPolicyConfig(
        mode="allowlist",
        include=[".gitconfig", "!ignored"],
        include_file=str(include),
    )

    assert status_pathspecs(policy) == [
        ".gitconfig",
        ".zshrc",
        ".claude/hooks/*.sh",
    ]
