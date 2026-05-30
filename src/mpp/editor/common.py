from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from mpp.core import Project, load_toml
from .clangd import write_clangd_config
from .vscode import write_vscode_config
from mpp.build.cmake import write_cmake_presets


def normalize_ide(value: str) -> str:
    aliases = {
        "code": "vscode",
        "vs-code": "vscode",
        "vs": "visualstudio",
        "visual-studio": "visualstudio",
        "visual studio": "visualstudio",
        "nvim": "clangd",
        "neovim": "clangd",
        "vim": "clangd",
        "zed": "clangd",
        "sublime": "clangd",
        "kate": "clangd",
    }
    return aliases.get(value.strip().lower(), value.strip().lower())


def ask_ide(default: str = "vscode") -> str:
    if not sys.stdin.isatty():
        return default
    print("Select IDE/editor config:")
    print("  1) vscode")
    print("  2) clangd-compatible (Neovim/Zed/Sublime/Kate)")
    print("  3) clion")
    print("  4) visualstudio")
    print("  5) generic")
    print("  6) all")
    print("  7) none")
    choice = input(f"IDE/editor [{default}]: ").strip().lower()
    if choice in ("", "1", "vscode", "vs-code", "code"):
        return "vscode"
    if choice in ("2", "clangd", "nvim", "neovim", "vim", "zed", "sublime", "kate"):
        return "clangd"
    if choice in ("3", "clion"):
        return "clion"
    if choice in ("4", "visualstudio", "visual-studio", "vs"):
        return "visualstudio"
    if choice in ("5", "generic"):
        return "generic"
    if choice in ("6", "all"):
        return "all"
    if choice in ("7", "none", "no"):
        return "none"
    return normalize_ide(choice)


def ide_context(project: Project) -> dict[str, Any]:
    build_dir = project.config.get("build", {}).get("build_dir", "build")
    build_type = project.config.get("build", {}).get("build_type", "Debug")
    cpp_standard = project.config.get("project", {}).get("cpp_standard", 20)
    compiler = shutil.which(os.environ.get("CXX", "g++")) or "/usr/bin/g++"
    root = project.root.resolve()
    build_path = root / build_dir
    compile_commands = build_path / "compile_commands.json"

    include_paths = [str(root / "src"), str(root / "mpp" / "vendor") + "/**"]
    locked = load_toml(project.lock_path).get("package", {})
    packages = set(project.config.get("dependencies", {}).keys()) | set(locked.keys())
    for package in sorted(packages):
        info = locked.get(package, {})
        include_paths.append(str(root / "mpp" / "vendor" / package))
        include_dirs = info.get("include_dirs") or ["include", "src"]
        for include_dir in include_dirs:
            include_paths.append(str(root / "mpp" / "vendor" / package / include_dir))

    return {
        "root": root,
        "build_path": build_path,
        "build_type": build_type,
        "compile_commands": compile_commands,
        "compile_commands_s": str(compile_commands).replace("\\", "/"),
        "build_path_s": str(build_path).replace("\\", "/"),
        "include_paths": [p.replace("\\", "/") for p in dict.fromkeys(include_paths)],
        "cpp_standard": cpp_standard,
        "compiler": compiler,
        "project_name": project.config.get("project", {}).get("name", project.root.name),
    }


def generate_ide_config(project: Project) -> None:
    ide = normalize_ide(project.config.get("ide", {}).get("name", "none"))
    if ide == "none":
        return

    ctx = ide_context(project)

    if ide in ("vscode", "all"):
        write_vscode_config(project, ctx)
        write_cmake_presets(project, ctx)
    elif ide in ("clangd", "generic"):
        write_clangd_config(project, ctx)
        write_cmake_presets(project, ctx)
    elif ide in ("clion", "visualstudio"):
        write_cmake_presets(project, ctx)
        write_clangd_config(project, ctx)
    else:
        write_clangd_config(project, ctx)
        write_cmake_presets(project, ctx)

    if ide == "all":
        write_vscode_config(project, ctx)
        write_clangd_config(project, ctx)
        write_cmake_presets(project, ctx)
