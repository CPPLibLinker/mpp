from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .core import MppError, git_head, load_toml, run

RECIPE_REPO_URL = "https://github.com/CPPLibLinker/vendor.git"
RECIPE_CACHE = Path.home() / ".cache" / "mpp" / "vendor"
RECIPE_REPO_ENV = "MPP_VENDOR_REPO"


def has_recipes(path: Path) -> bool:
    return (path / "packages").is_dir()


def workspace_vendor_repo() -> Path | None:
    # Source checkout layout:
    #   <workspace>/mpp/src/mpp/recipes.py
    #   <workspace>/vendor/packages/...
    mpp_repo = Path(__file__).resolve().parents[2]
    candidate = mpp_repo.parent / "vendor"
    if has_recipes(candidate):
        return candidate
    return None


def ensure_recipe_repo() -> Path:
    env_repo = os.environ.get(RECIPE_REPO_ENV)
    if env_repo:
        path = Path(env_repo).expanduser().resolve()
        if not has_recipes(path):
            raise MppError(f"{RECIPE_REPO_ENV} does not point to a vendor recipe repo: {path}")
        return path

    local_repo = workspace_vendor_repo()
    if local_repo:
        return local_repo

    if RECIPE_CACHE.exists() and (RECIPE_CACHE / ".git").exists():
        run(["git", "pull", "--ff-only"], cwd=RECIPE_CACHE, check=False)
    else:
        RECIPE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        if RECIPE_CACHE.exists():
            shutil.rmtree(RECIPE_CACHE)
        run(["git", "clone", RECIPE_REPO_URL, str(RECIPE_CACHE)])

    if not has_recipes(RECIPE_CACHE):
        raise MppError(
            "vendor recipe repository has no packages. "
            "During local development, keep sibling repos `mpp/` and `vendor/`, "
            f"or set {RECIPE_REPO_ENV}=/path/to/vendor."
        )
    return RECIPE_CACHE


def recipe_for(name: str) -> tuple[Path, dict[str, Any]]:
    repo = ensure_recipe_repo()
    path = repo / "packages" / name / "recipe.toml"
    if not path.exists():
        raise MppError(f"recipe not found: {name} ({path})")
    return path, load_toml(path)


def find_recipe_and_version(spec: str, requested_version: str | None) -> tuple[str, str | None, Path, dict[str, Any]]:
    """Resolve `raylib`, `raylib-6.0`, or `raylib-master` into recipe + version."""
    try:
        path, recipe = recipe_for(spec)
        return spec, requested_version, path, recipe
    except MppError as original_error:
        if "-" not in spec:
            raise original_error

    base, suffix = spec.rsplit("-", 1)
    path, recipe = recipe_for(base)
    return base, requested_version or suffix, path, recipe


def resolve_recipe_ref(recipe: dict[str, Any], version: str) -> tuple[str, str | None]:
    versions = recipe.get("versions", {})
    meta = versions.get(version, {})
    if "branch" in meta:
        return meta["branch"], meta["branch"]
    if "tag" in meta:
        return meta["tag"], None
    if "commit" in meta:
        return meta["commit"], None
    return version, None


def select_recipe_profile(recipe: dict[str, Any], full_profile: str) -> dict[str, Any]:
    profiles = recipe.get("profiles", {})
    if full_profile in profiles:
        return profiles[full_profile]
    base = "-".join(full_profile.split("-")[:3])
    return profiles.get(base, {})


def select_recipe_platform(recipe: dict[str, Any], selected_platform: str | None) -> dict[str, Any]:
    if not selected_platform:
        return {}
    platforms = recipe.get("platforms", {})
    # Backward compatible for old local recipes, but new recipes should use [platforms.*].
    if not platforms:
        platforms = recipe.get("backends", {})
    if selected_platform not in platforms:
        available = ", ".join(sorted(platforms.keys())) or "none"
        raise MppError(f"platform '{selected_platform}' not available for {recipe.get('name', 'package')}; available: {available}")
    return platforms[selected_platform]


def recipe_commit(recipe_path: Path) -> str:
    return git_head(recipe_path.parents[2], "local-uncommitted")
