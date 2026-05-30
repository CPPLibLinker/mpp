from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    print("mpp requires Python 3.11+", file=sys.stderr)
    sys.exit(1)

VERSION = "0.1.0-dev"


class MppError(Exception):
    pass


@dataclass
class Project:
    root: Path
    config_path: Path
    lock_path: Path
    config: dict[str, Any]


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, text=True, check=check)


def git_head(cwd: Path, fallback: str = "uncommitted") -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return fallback


def load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def quote_toml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(quote_toml(x) for x in value) + "]"
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def write_project_toml(path: Path, data: dict[str, Any]) -> None:
    lines: list[str] = []
    for section in ("project", "build", "ide"):
        values = data.get(section, {})
        if values:
            lines.append(f"[{section}]")
            for k, v in values.items():
                lines.append(f"{k} = {quote_toml(v)}")
            lines.append("")

    deps = data.get("dependencies", {})
    for name, values in deps.items():
        lines.append(f"[dependencies.{name}]")
        for k, v in values.items():
            lines.append(f"{k} = {quote_toml(v)}")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n")


def write_lock_toml(path: Path, packages: dict[str, dict[str, Any]]) -> None:
    lines: list[str] = []
    for name, values in packages.items():
        lines.append(f"[package.{name}]")
        for k, v in values.items():
            lines.append(f"{k} = {quote_toml(v)}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n")


def find_project_root(start: Path) -> Path:
    cur = start.resolve()
    while True:
        if (cur / "mpp.toml").exists():
            return cur
        if cur.parent == cur:
            raise MppError("not inside an mpp project; run `mpp init` first")
        cur = cur.parent


def load_project() -> Project:
    root = find_project_root(Path.cwd())
    config_path = root / "mpp.toml"
    return Project(root, config_path, root / "mpp.lock", load_toml(config_path))


def detect_base_profile() -> str:
    import os

    machine = platform.machine().lower()
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}.get(machine, machine)
    sysname = platform.system().lower()
    osname = {"linux": "linux", "windows": "windows", "darwin": "macos"}.get(sysname, sysname)
    compiler = os.environ.get("CXX", "g++")
    if "clang" in compiler:
        comp = "clang"
    elif "cl" == compiler or compiler.endswith("cl.exe"):
        comp = "msvc"
    elif "mingw" in compiler:
        comp = "mingw"
    else:
        comp = "gcc"
    return f"{arch}-{osname}-{comp}"


def detect_profile(build_type: str = "Debug", linkage: str = "static") -> str:
    return f"{detect_base_profile()}-{build_type.lower()}-{linkage}"


def ensure_dirs(root: Path) -> None:
    for p in [root / "mpp" / "generated", root / "mpp" / "vendor"]:
        p.mkdir(parents=True, exist_ok=True)
