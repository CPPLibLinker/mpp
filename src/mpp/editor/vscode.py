from __future__ import annotations

import json
from typing import Any

from mpp.core import Project


def write_vscode_config(project: Project, ctx: dict[str, Any]) -> None:
    vscode = project.root / ".vscode"
    vscode.mkdir(exist_ok=True)
    config = {
        "name": "mpp",
        "compilerPath": ctx["compiler"],
        "cppStandard": f"c++{ctx['cpp_standard']}",
        "intelliSenseMode": "linux-gcc-x64",
        "includePath": ctx["include_paths"],
        "browse": {"path": ctx["include_paths"]},
    }
    if ctx["compile_commands"].exists():
        config["compileCommands"] = ctx["compile_commands_s"]

    (vscode / "c_cpp_properties.json").write_text(json.dumps({"configurations": [config], "version": 4}, indent=2) + "\n")

    settings = {
        "C_Cpp.default.includePath": ctx["include_paths"],
        "C_Cpp.default.cppStandard": f"c++{ctx['cpp_standard']}",
        "C_Cpp.default.compilerPath": ctx["compiler"],
        "cmake.buildDirectory": ctx["build_path_s"],
    }
    if ctx["compile_commands"].exists():
        settings["C_Cpp.default.compileCommands"] = ctx["compile_commands_s"]
    (vscode / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")

    workspace = {"folders": [{"path": "."}], "settings": settings}
    (project.root / f"{ctx['project_name']}.code-workspace").write_text(json.dumps(workspace, indent=2) + "\n")
