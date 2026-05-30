from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from .core import MppError, git_head, quote_toml, run


def is_git_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "file://", "git@")) or value.endswith(".git")


def source_cache_dir(name: str, git_url: str, ref: str) -> Path:
    key = hashlib.sha1(f"{git_url}@{ref}".encode()).hexdigest()[:12]
    safe_ref = re.sub(r"[^A-Za-z0-9_.-]+", "-", ref or "HEAD")
    return Path.home() / ".cache" / "mpp" / "sources" / f"{name}-{safe_ref}-{key}"


def copy_source_tree(src: Path, dest: Path, export_paths: list[str] | None = None) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns(".git", ".github", "build", "cmake-build-*", "*.o", "*.a", "*.so", "*.dll", "*.exe")

    if export_paths:
        for rel in export_paths:
            source = src / rel
            target = dest / rel
            if not source.exists():
                raise MppError(f"export path not found in dependency: {rel}")
            if source.is_dir():
                shutil.copytree(source, target, ignore=ignore)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    else:
        shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=ignore)

    for git_dir in dest.rglob(".git"):
        if git_dir.is_dir():
            shutil.rmtree(git_dir)
        else:
            git_dir.unlink()


def export_dependency(root: Path, name: str, git_url: str, ref: str, branch: str | None, export_paths: list[str] | None = None) -> str:
    """Fetch dependency into a global git cache, then copy plain source files into the project."""
    checkout = branch or ref or "HEAD"
    cache = source_cache_dir(name, git_url, checkout)
    dest = root / "mpp" / "vendor" / name
    revision_file = dest / ".mpp" / "REVISION"

    if cache.exists() and (cache / ".git").exists():
        run(["git", "fetch", "--quiet", "--depth", "1", "origin", checkout], cwd=cache, check=False)
        run(["git", "-c", "advice.detachedHead=false", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=cache, check=False)
    else:
        cache.parent.mkdir(parents=True, exist_ok=True)
        if cache.exists():
            shutil.rmtree(cache)
        cmd = ["git", "-c", "advice.detachedHead=false", "clone", "--quiet", "--depth", "1", "--single-branch"]
        if checkout and checkout != "HEAD":
            cmd += ["--branch", checkout]
        cmd += [git_url, str(cache)]
        result = run(cmd, check=False)
        if result.returncode != 0:
            if cache.exists():
                shutil.rmtree(cache)
            cache.mkdir(parents=True)
            run(["git", "init", "--quiet"], cwd=cache)
            run(["git", "remote", "add", "origin", git_url], cwd=cache)
            run(["git", "fetch", "--quiet", "--depth", "1", "origin", checkout], cwd=cache)
            run(["git", "-c", "advice.detachedHead=false", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=cache)

    commit = git_head(cache)
    copy_source_tree(cache, dest, export_paths)
    revision_file.parent.mkdir(parents=True, exist_ok=True)
    revision_file.write_text(f"git = {quote_toml(git_url)}\nref = {quote_toml(checkout)}\ncommit = {quote_toml(commit)}\n")
    return commit
