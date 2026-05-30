from __future__ import annotations

from typing import Any

from mpp.core import Project


def write_clangd_config(project: Project, ctx: dict[str, Any]) -> None:
    lines = [
        "CompileFlags:",
        f"  CompilationDatabase: {ctx['build_path_s']}",
        "  Add:",
        f"    - -std=c++{ctx['cpp_standard']}",
    ]
    for path in ctx["include_paths"]:
        if path.endswith("/**"):
            continue
        lines.append(f"    - -I{path}")
    (project.root / ".clangd").write_text("\n".join(lines) + "\n")

    flags = [f"-std=c++{ctx['cpp_standard']}"]
    flags += [f"-I{p}" for p in ctx["include_paths"] if not p.endswith("/**")]
    (project.root / "compile_flags.txt").write_text("\n".join(flags) + "\n")
