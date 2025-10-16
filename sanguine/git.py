import subprocess


def run_command(command: list[str]) -> str:
    return subprocess.run(
        command, capture_output=True, text=True, check=True
    ).stdout.rstrip("\n")


def last_commit() -> str:
    return run_command(["git", "rev-parse", "HEAD"])


def changed_files(commit_id: str) -> list[str]:
    result = run_command(
        [
            "git",
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit_id,
        ]
    )
    return [f.strip() for f in result.split("\n") if f.strip()]


def get_commit_file_changes(commit_id: str, file: str) -> str:
    return run_command(["git", "show", commit_id, "--", file])


def commit_diff(commit_id: str) -> dict[str, tuple[str, str]]:
    files = changed_files(commit_id)
    diff = [get_commit_file_changes(commit_id, file) for file in files]
    file_diff = {}

    for file, diff in zip(files, diff):
        diff_lines = diff.split("\n")
        added_lines = []
        removed_lines = []

        for line in diff_lines:
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line[1:])
        file_diff[file] = ("\n".join(added_lines), "\n".join(removed_lines))

    return file_diff
