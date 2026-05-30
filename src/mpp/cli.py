#!/usr/bin/env python3
"""mpp — lightweight C++ library linker / CMake helper."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    print("mpp requires Python 3.11+", file=sys.stderr)
    sys.exit(1)

VERSION = "0.1.0-dev"
RECIPE_REPO_URL = "https://github.com/CPPLibLinker/vendor.git"
RECIPE_CACHE = Path.home() / ".cache" / "mpp" / "vendor"
RECIPE_REPO_ENV = "MPP_VENDOR_REPO"


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


def ask_ide(default: str = "vscode") -> str:
    if not sys.stdin.isatty():
        return default
    print("Select IDE/editor config:")
    print("  1) vscode")
    print("  2) none")
    choice = input(f"IDE/editor [{default}]: ").strip().lower()
    if choice in ("", "1", "vscode", "vs-code", "code"):
        return "vscode"
    if choice in ("2", "none", "no"):
        return "none"
    return choice


def init_cmd(args: argparse.Namespace) -> None:
    root = Path.cwd()
    ensure_dirs(root)
    ide = args.ide or ask_ide()
    config_path = root / "mpp.toml"
    if not config_path.exists():
        name = args.name or root.name.replace(" ", "-")
        write_project_toml(config_path, {
            "project": {"name": name, "version": "0.1.0", "cpp_standard": 20},
            "build": {"generator": "cmake", "build_dir": "build", "default_target": name, "build_type": "Debug", "export_compile_commands": True},
            "ide": {"name": ide},
            "dependencies": {},
        })
    lock = root / "mpp.lock"
    if not lock.exists():
        lock.write_text("# generated by mpp\n")
    cmake = root / "CMakeLists.txt"
    if args.cmake and not cmake.exists():
        name = args.name or root.name.replace(" ", "-")
        cmake.write_text(f"""cmake_minimum_required(VERSION 3.20)
project({name} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include(mpp/generated/mpp.cmake)

add_executable({name} src/main.cpp)
# mpp_link({name} package_name)
""")
        (root / "src").mkdir(exist_ok=True)
        main = root / "src" / "main.cpp"
        if not main.exists():
            main.write_text('#include <iostream>\n\nint main() {\n    std::cout << "hello from mpp\\n";\n}\n')
    project = Project(root, config_path, lock, load_toml(config_path))
    generate_cmake(project)
    generate_ide_config(project)
    print("initialized mpp project")


def has_recipes(path: Path) -> bool:
    return (path / "packages").is_dir()


def workspace_vendor_repo() -> Path | None:
    # Source checkout layout:
    #   <workspace>/mpp/src/mpp/cli.py
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


def is_git_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "file://", "git@")) or value.endswith(".git")


def print_recipe_options_cmd(args: argparse.Namespace) -> None:
    pkg, requested_version, recipe_path, recipe = find_recipe_and_version(args.package, args.version)
    version = requested_version or recipe.get("default_version", "HEAD")
    print(f"{pkg} {version}")
    print(f"recipe: {recipe_path}")

    versions = recipe.get("versions", {})
    if versions:
        print("\nversions:")
        for name in sorted(versions.keys()):
            print(f"  {name}")

    platforms = recipe.get("platforms", {}) or recipe.get("backends", {})
    if platforms:
        print("\nplatforms:")
        for name, meta in platforms.items():
            desc = meta.get("description", "")
            options = ", ".join(meta.get("options", []))
            suffix = f" - {desc}" if desc else ""
            print(f"  {name}{suffix}")
            if options:
                print(f"    options: {options}")

    options = recipe.get("options", {})
    if options:
        print("\noptions:")
        for name, meta in options.items():
            desc = meta.get("description", "")
            default = meta.get("default")
            values = meta.get("values", [])
            line = f"  {name}"
            if default is not None:
                line += f" (default: {default})"
            if desc:
                line += f" - {desc}"
            print(line)
            if values:
                print("    values: " + ", ".join(str(v) for v in values))

    if not platforms and not options:
        print("\nNo custom platform presets or options documented for this recipe.")


def add_cmd(args: argparse.Namespace) -> None:
    project = load_project()
    ensure_dirs(project.root)
    deps = project.config.setdefault("dependencies", {})

    if is_git_url(args.package):
        if args.platform or args.backend:
            raise MppError("--platform requires a named package recipe")
        pkg = args.package.rstrip("/").split("/")[-1].removesuffix(".git")
        git_url = args.package
        version = args.tag or args.branch or "HEAD"
        checkout_ref = args.tag or version
        checkout_branch = args.branch
        recipe = {"name": pkg, "git": git_url, "default_version": version, "versions": {version: {}}}
        source = "git"
        recipe_commit = ""
    else:
        pkg, requested_version, recipe_path, recipe = find_recipe_and_version(args.package, args.version)
        git_url = recipe.get("git")
        if not git_url:
            raise MppError(f"recipe {pkg} missing git url")
        version = requested_version or recipe.get("default_version", "HEAD")
        checkout_ref, checkout_branch = resolve_recipe_ref(recipe, version)
        source = "recipe"
        recipe_commit = git_head(recipe_path.parents[2], "local-uncommitted")

    user_options = (args.option or []) + (args.define or [])
    recipe_options = recipe.get("options", {})
    for opt in user_options:
        if "=" not in opt:
            raise MppError(f"option must be KEY=VALUE: {opt}")
        key, value = opt.split("=", 1)
        if key in recipe_options:
            values = [str(v) for v in recipe_options[key].get("values", [])]
            if values and value not in values:
                raise MppError(f"invalid value for {key}: {value}; valid: {', '.join(values)}")

    export_paths = recipe.get("export", {}).get("paths")
    commit = export_dependency(project.root, pkg, git_url, checkout_ref, checkout_branch, export_paths)
    deps[pkg] = {"version": version, "source": source}
    selected_platform = args.platform or args.backend
    if selected_platform:
        deps[pkg]["platform"] = selected_platform
    if user_options:
        deps[pkg]["options"] = user_options
    if source == "git":
        deps[pkg]["git"] = git_url
    write_project_toml(project.config_path, project.config)
    ensure_cmake_links_package(project.root, project.config, pkg)

    build_type = project.config.get("build", {}).get("build_type", "Debug")
    profile = detect_profile(build_type)
    lock_data = load_toml(project.lock_path).get("package", {})
    profile_meta = select_recipe_profile(recipe, profile)
    platform_meta = select_recipe_platform(recipe, selected_platform)
    cmake_meta = recipe.get("cmake", {})
    cmake_target = platform_meta.get("target") or cmake_meta.get("target") or recipe.get("target") or pkg
    cmake_source_dir = platform_meta.get("source_dir") or cmake_meta.get("source_dir", ".")
    cmake_options = cmake_meta.get("options", []) + platform_meta.get("options", []) + user_options
    include_dirs = profile_meta.get("include_dirs", ["include", "src"]) + platform_meta.get("include_dirs", [])
    system_libs = profile_meta.get("libs", []) + platform_meta.get("libs", [])
    lock_data[pkg] = {
        "version": version,
        "git": git_url,
        "commit": commit,
        "recipe_repo": RECIPE_REPO_URL,
        "recipe_commit": recipe_commit,
        "profile": profile,
        "cmake_target": cmake_target,
        "cmake_source_dir": cmake_source_dir,
        "cmake_options": cmake_options,
        "platform": selected_platform or "default",
        "include_dirs": list(dict.fromkeys(include_dirs)),
        "system_libs": list(dict.fromkeys(system_libs)),
    }
    write_lock_toml(project.lock_path, lock_data)
    updated_project = Project(project.root, project.config_path, project.lock_path, load_toml(project.config_path))
    generate_cmake(updated_project)
    generate_ide_config(updated_project)
    print(f"added {pkg}")


def ensure_cmake_links_package(root: Path, config: dict[str, Any], package: str) -> None:
    cmake = root / "CMakeLists.txt"
    if not cmake.exists():
        return

    target = config.get("build", {}).get("default_target") or config.get("project", {}).get("name")
    if not target:
        return

    text = cmake.read_text()
    link_line = f"mpp_link({target} {package})"
    if link_line in text:
        return

    if "include(mpp/generated/mpp.cmake)" not in text:
        project_match = re.search(r"^project\([^\n]+\)\s*$", text, flags=re.MULTILINE)
        if project_match:
            insert_at = project_match.end()
            text = text[:insert_at] + "\n\ninclude(mpp/generated/mpp.cmake)" + text[insert_at:]
        else:
            text = "include(mpp/generated/mpp.cmake)\n\n" + text

    exe_pattern = re.compile(rf"^(add_executable\(\s*{re.escape(str(target))}\b[^\n]*\)\s*)$", re.MULTILINE)
    match = exe_pattern.search(text)
    if match:
        insert_at = match.end()
        text = text[:insert_at] + f"\n{link_line}" + text[insert_at:]
    else:
        text = text.rstrip() + f"\n\n# Added by mpp. Move below your add_executable/add_library target if needed.\n{link_line}\n"

    cmake.write_text(text)


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
    """Fetch dependency into a global git cache, then copy plain source files into the project.

    User projects should not receive nested git repos or full git history. The cache may be
    a shallow clone, but `mpp/vendor/<name>` is plain copied source code.
    """
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
            # Some tags/commits are not single branch refs. Fall back to a shallow fetch.
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


def cmake_escape(path: Path) -> str:
    return str(path).replace("\\", "/")


def generate_ide_config(project: Project) -> None:
    ide = project.config.get("ide", {}).get("name", "none")
    if ide != "vscode":
        return

    vscode = project.root / ".vscode"
    vscode.mkdir(exist_ok=True)
    build_dir = project.config.get("build", {}).get("build_dir", "build")
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

    include_paths = [p.replace("\\", "/") for p in dict.fromkeys(include_paths)]
    compile_commands_s = str(compile_commands).replace("\\", "/")
    build_path_s = str(build_path).replace("\\", "/")

    config = {
        "name": "mpp",
        "compilerPath": compiler,
        "cppStandard": f"c++{cpp_standard}",
        "intelliSenseMode": "linux-gcc-x64",
        "includePath": include_paths,
        "browse": {"path": include_paths},
    }
    if compile_commands.exists():
        config["compileCommands"] = compile_commands_s

    c_cpp = {
        "configurations": [config],
        "version": 4,
    }
    (vscode / "c_cpp_properties.json").write_text(json.dumps(c_cpp, indent=2) + "\n")

    settings = {
        "C_Cpp.default.includePath": include_paths,
        "C_Cpp.default.cppStandard": f"c++{cpp_standard}",
        "C_Cpp.default.compilerPath": compiler,
        "cmake.buildDirectory": build_path_s,
    }
    if compile_commands.exists():
        settings["C_Cpp.default.compileCommands"] = compile_commands_s
    (vscode / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")

    workspace = {
        "folders": [{"path": "."}],
        "settings": settings,
    }
    workspace_name = project.config.get("project", {}).get("name", project.root.name)
    (project.root / f"{workspace_name}.code-workspace").write_text(json.dumps(workspace, indent=2) + "\n")


def generate_cmake(project: Project) -> None:
    ensure_dirs(project.root)
    deps = project.config.get("dependencies", {})
    locked = load_toml(project.lock_path).get("package", {})
    out = project.root / "mpp" / "generated" / "mpp.cmake"
    lines = [
        "# generated by mpp; do not edit",
        "",
        "function(mpp_link target package)",
    ]
    if not deps:
        lines += ["  message(FATAL_ERROR \"No mpp packages are configured\")"]
    first = True
    for name, meta in deps.items():
        keyword = "if" if first else "elseif"
        first = False
        src = f"${{CMAKE_SOURCE_DIR}}/mpp/vendor/{name}"
        info = locked.get(name, {})
        cmake_target = info.get("cmake_target", name)
        cmake_source_dir = info.get("cmake_source_dir", ".")
        cmake_src = src if cmake_source_dir in ("", ".") else f"{src}/{cmake_source_dir}"
        cmake_options = info.get("cmake_options", [])
        system_libs = info.get("system_libs", [])
        lines += [f"  {keyword}(package STREQUAL \"{name}\")"]
        lines += [f"    if(EXISTS \"{cmake_src}/CMakeLists.txt\")"]
        lines += [f"      if(NOT TARGET {cmake_target})"]
        for option in cmake_options:
            if isinstance(option, str) and "=" in option:
                opt_name, opt_value = option.split("=", 1)
                lines += [f"        set({opt_name} {opt_value} CACHE STRING \"mpp option for {name}\" FORCE)"]
        lines += [f"        add_subdirectory(\"{cmake_src}\" \"${{CMAKE_BINARY_DIR}}/mpp/{name}\")"]
        lines += ["      endif()"]
        lines += [f"      if(TARGET {cmake_target})"]
        lines += [f"        target_link_libraries(${{target}} PRIVATE {cmake_target})"]
        if system_libs:
            lines += ["        target_link_libraries(${target} PRIVATE " + " ".join(str(x) for x in system_libs) + ")"]
        lines += ["      else()"]
        lines += [f"        message(FATAL_ERROR \"mpp package '{name}' has CMake, but target '{cmake_target}' was not created. Check vendor recipe.\")"]
        lines += ["      endif()"]
        lines += ["    else()"]
        lines += [f"      target_include_directories(${{target}} PRIVATE \"{src}/include\")"]
        if system_libs:
            lines += ["      target_link_libraries(${target} PRIVATE " + " ".join(str(x) for x in system_libs) + ")"]
        lines += ["    endif()"]
    if deps:
        lines += ["  else()", "    message(FATAL_ERROR \"Unknown mpp package: ${package}\")", "  endif()"]
    lines += ["endfunction()", ""]
    out.write_text("\n".join(lines))


def build_cmd(args: argparse.Namespace) -> None:
    project = load_project()
    generate_cmake(project)
    build = project.config.get("build", {})
    build_dir = project.root / build.get("build_dir", "build")
    build_type = args.type or build.get("build_type", "Debug")
    generate_ide_config(project)
    run(["cmake", "-S", str(project.root), "-B", str(build_dir), f"-DCMAKE_BUILD_TYPE={build_type}", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"])
    generate_ide_config(project)
    cmd = ["cmake", "--build", str(build_dir)]
    if args.target:
        cmd += ["--target", args.target]
    run(cmd)


def run_cmd(args: argparse.Namespace) -> None:
    project = load_project()
    build_cmd(argparse.Namespace(type=args.type, target=args.target))
    build = project.config.get("build", {})
    target = args.target or build.get("default_target") or project.config.get("project", {}).get("name")
    if not target:
        raise MppError("no target configured; use `mpp run <target>`")
    exe = project.root / build.get("build_dir", "build") / target
    if platform.system().lower() == "windows":
        exe = exe.with_suffix(".exe")
    if not exe.exists():
        # common CMake multi-config path fallback
        candidates = list((project.root / build.get("build_dir", "build")).rglob(exe.name))
        if candidates:
            exe = candidates[0]
    if not exe.exists():
        raise MppError(f"built executable not found: {exe}")
    run([str(exe)] + args.args, cwd=project.root)


def clean_cmd(args: argparse.Namespace) -> None:
    project = load_project()
    build_dir = project.root / project.config.get("build", {}).get("build_dir", "build")
    for path in [build_dir, project.root / "mpp" / "generated"]:
        if path.exists():
            shutil.rmtree(path)
            print(f"removed {path}")
    if args.vendor:
        vend = project.root / "mpp" / "vendor"
        if vend.exists():
            shutil.rmtree(vend)
            print(f"removed {vend}")


def sync_cmd(args: argparse.Namespace) -> None:
    project = load_project()
    generate_cmake(project)
    generate_ide_config(project)
    print("generated mpp/generated/mpp.cmake")


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpp", description="C++ module/package linker")
    p.add_argument("--version", action="version", version=f"mpp {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="initialize project")
    i.add_argument("--name")
    i.add_argument("--ide", choices=["vscode", "none"], help="generate IDE/editor config")
    i.add_argument("--no-cmake", dest="cmake", action="store_false", help="do not create CMakeLists.txt")
    i.set_defaults(func=init_cmd, cmake=True)

    a = sub.add_parser("add", help="add package or git repo")
    a.add_argument("package")
    a.add_argument("--version")
    a.add_argument("--tag")
    a.add_argument("--branch")
    a.add_argument("--platform", help="select package platform preset, e.g. raylib --platform sdl")
    a.add_argument("--backend", help=argparse.SUPPRESS)  # deprecated alias for --platform
    a.add_argument("--option", action="append", metavar="KEY=VALUE", help="pass package CMake option; repeatable")
    a.add_argument("-D", "--define", action="append", metavar="KEY=VALUE", help="alias for --option; repeatable")
    a.set_defaults(func=add_cmd)

    o = sub.add_parser("options", help="show package versions, platforms, and options")
    o.add_argument("package")
    o.add_argument("--version")
    o.set_defaults(func=print_recipe_options_cmd)

    b = sub.add_parser("build", help="configure and build with CMake")
    b.add_argument("--type")
    b.add_argument("--target")
    b.set_defaults(func=build_cmd)

    r = sub.add_parser("run", help="build and run executable")
    r.add_argument("target", nargs="?")
    r.add_argument("--type")
    r.add_argument("args", nargs=argparse.REMAINDER)
    r.set_defaults(func=run_cmd)

    c = sub.add_parser("clean", help="remove build output")
    c.add_argument("--vendor", action="store_true")
    c.set_defaults(func=clean_cmd)

    s = sub.add_parser("sync", help="regenerate mpp files")
    s.set_defaults(func=sync_cmd)
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = make_parser().parse_args(argv)
        args.func(args)
        return 0
    except MppError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"error: command failed with exit code {e.returncode}", file=sys.stderr)
        return e.returncode


if __name__ == "__main__":
    raise SystemExit(main())
