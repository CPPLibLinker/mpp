# mpp — C++ Module/Package Linker

`mpp` is a lightweight dependency/linking helper for C++ projects.

The first goal is intentionally narrow:

- C++ projects only
- CMake generation only
- Git-based dependency recipes
- Local vendoring first
- Simple commands: `add`, `build`, `run`, `clean`

`mpp` is **not** initially a full replacement for CMake, Conan, vcpkg, or Make. It is a small tool that makes adding and linking common C++ libraries easier by using curated vendor recipes.

---

## Current Implementation

This repository now contains the first Python-based CLI implementation.

Run from source inside the `mpp` repository:

```sh
PYTHONPATH=src python3 -m mpp --version
PYTHONPATH=src python3 -m mpp init --name demo --ide vscode
PYTHONPATH=src python3 -m mpp build
PYTHONPATH=src python3 -m mpp run
```

Or use the local wrapper:

```sh
./bin/mpp --version
```

Install locally in editable mode:

```sh
python3 -m pip install -e .
mpp --version
```

Implemented commands:

- `mpp init [--ide vscode|none]`
- `mpp add <package>`
- `mpp add <git-repo>`
- `mpp sync`
- `mpp build`
- `mpp run [target]`
- `mpp clean [--vendor]`

Current limitations:

- Python 3.11+ required.
- CMake only.
- Recipe lookup uses the sibling `../vendor` repo during local development.
- If no sibling `../vendor` repo exists, recipe lookup clones `https://github.com/CPPLibLinker/vendor.git` into `~/.cache/mpp/vendor`.
- You can override recipe lookup with `MPP_VENDOR_REPO=/path/to/vendor`.
- Raw Git dependencies are only safely usable if they expose a normal CMake target.
- Recipe metadata support is intentionally minimal: `git`, `default_version`, `[cmake].target`, and `[profiles.<profile>].libs`.

---

## Repository Architecture

The project is split into two repositories under the `CPPLibLinker` GitHub organization.

```txt
github.com/CPPLibLinker/mpp
```

Main source repository for the `mpp` command-line tool.

```txt
github.com/CPPLibLinker/vendor
```

Recipe repository containing known build/link instructions for supported third-party libraries.

Important naming distinction:

```txt
CPPLibLinker/mpp     = source code for the module/package linker
CPPLibLinker/vendor  = Git repository of dependency recipes
```

---

## Local Project Layout

A user project using `mpp` may look like this:

```txt
my-cpp-app/
  src/
    main.cpp

  mpp.toml
  mpp.lock

  CMakeLists.txt

  mpp/
    generated/
      mpp.cmake

    vendor/
      raylib/
        .mpp/
          REVISION
        CMakeLists.txt
        src/
        examples/
        ...
```

### Files

#### `mpp.toml`

Project dependency and target configuration.

#### `mpp.lock`

Resolved dependency versions, Git commits, build profile, and selected recipe revisions.

#### `mpp/generated/mpp.cmake`

Generated CMake integration file. This file is produced by `mpp` and should not be manually edited.

#### `mpp/vendor/`

Local vendored dependency sources and/or built artifacts for the project.

This is different from `github.com/CPPLibLinker/vendor`, which is the central recipe repository.

---

## Command Goals

### `mpp init`

Initializes a C++ project for use with `mpp`.

It asks which IDE/editor config to generate. Currently supported:

- `vscode`
- `none`

You can skip the prompt:

```sh
mpp init --ide vscode
mpp init --ide none
```

VS Code generation creates:

```txt
.vscode/c_cpp_properties.json
.vscode/settings.json
```

and enables CMake compile commands:

```txt
build/compile_commands.json
```

Creates:

```txt
mpp.toml
mpp.lock
mpp/generated/
mpp/vendor/
```

Optionally creates a minimal `CMakeLists.txt` if one does not exist.

Example:

```sh
mpp init
```

---

### `mpp add <package>`

Adds a dependency using a known recipe from `github.com/CPPLibLinker/vendor`.

Examples:

```sh
mpp add raylib        # default recipe version
mpp add raylib-6.0    # explicit version/tag from recipe
mpp add raylib-master # explicit branch from recipe
```

Expected behavior:

1. Find `raylib` in the vendor recipe repository.
2. Resolve version and platform profile.
3. Clone/download the dependency into local `mpp/vendor/raylib`.
4. Update `mpp.toml`.
5. Update `mpp.lock`.
6. Regenerate `mpp/generated/mpp.cmake`.

---

### `mpp add <git-repo>`

Adds a raw Git dependency.

Example:

```sh
mpp add https://github.com/raysan5/raylib
```

For raw Git repos, `mpp` can either:

- infer a basic CMake project, or
- require the user to provide metadata manually.

Initial support should be conservative. If no known recipe exists, `mpp` should not pretend to know how to link the dependency safely.

---

### `mpp build`

Configures and builds the CMake project.

Example:

```sh
mpp build
```

Expected behavior:

```sh
cmake -S . -B build
cmake --build build
```

`mpp build` should also ensure generated files are up to date before invoking CMake.

---

### `mpp run`

Builds and runs the configured executable target.

Example:

```sh
mpp run
```

Expected behavior:

1. Run `mpp build`.
2. Locate the configured executable target.
3. Execute it.

If multiple executable targets exist, the user should specify one:

```sh
mpp run app
```

---

### `mpp clean`

Removes generated build output.

Example:

```sh
mpp clean
```

Expected behavior:

```txt
remove build/
remove mpp/generated/
```

It should not delete `mpp/vendor/` by default.

Optional future command:

```sh
mpp clean --vendor
```

would remove vendored dependencies too.

---

## Example User Workflow

```sh
mkdir game
cd game

mpp init
mpp add raylib
mpp build
mpp run
```

User `CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.20)
project(game LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(mpp/generated/mpp.cmake)

add_executable(game src/main.cpp)
mpp_link(game raylib)
```

Generated `mpp/generated/mpp.cmake` may contain:

```cmake
function(mpp_link target package)
  if(package STREQUAL "raylib")
    target_include_directories(${target} PRIVATE
      "${CMAKE_SOURCE_DIR}/mpp/vendor/raylib/include"
    )

    target_link_libraries(${target} PRIVATE
      "${CMAKE_SOURCE_DIR}/mpp/vendor/raylib/lib/x86_64-linux-gcc/libraylib.a"
      m pthread dl rt X11
    )
  else()
    message(FATAL_ERROR "Unknown mpp package: ${package}")
  endif()
endfunction()
```

---

## `mpp.toml` Design

Example:

```toml
[project]
name = "game"
version = "0.1.0"
cpp_standard = 20

[build]
generator = "cmake"
build_dir = "build"
default_target = "game"
build_type = "Debug"

[dependencies.raylib]
version = "5.5"
source = "recipe"
```

A raw Git dependency could look like:

```toml
[dependencies.raylib]
git = "https://github.com/raysan5/raylib"
tag = "5.5"
source = "git"
```

---

## `mpp.lock` Design

Example:

```toml
[package.raylib]
version = "5.5"
git = "https://github.com/raysan5/raylib"
commit = "abc123..."
recipe_repo = "https://github.com/CPPLibLinker/vendor"
recipe_commit = "def456..."
profile = "x86_64-linux-gcc-debug-static"
```

The lockfile should make builds reproducible.

---

## Vendor Recipe Repository Layout

Repository:

```txt
github.com/CPPLibLinker/vendor
```

Suggested structure:

```txt
vendor/
  packages/
    raylib/
      recipe.toml
      patches/
        fix-linux.patch

    glfw/
      recipe.toml

    fmt/
      recipe.toml
```

Example recipe:

```toml
name = "raylib"
description = "Simple and easy-to-use library to enjoy videogames programming"
homepage = "https://www.raylib.com"
git = "https://github.com/raysan5/raylib"
default_version = "5.5"

[versions."5.5"]
tag = "5.5"

[build]
system = "cmake"

[cmake]
options = [
  "BUILD_EXAMPLES=OFF",
  "BUILD_GAMES=OFF"
]

[profiles.x86_64-linux-gcc]
linkage = "static"
include_dirs = ["include"]
libs = ["raylib", "m", "pthread", "dl", "rt", "X11"]
artifact = "lib/libraylib.a"

[profiles.x86_64-windows-msvc]
linkage = "static"
include_dirs = ["include"]
libs = ["raylib", "winmm", "gdi32", "opengl32"]
artifact = "lib/raylib.lib"

[profiles.x86_64-windows-mingw]
linkage = "static"
include_dirs = ["include"]
libs = ["raylib", "winmm", "gdi32", "opengl32"]
artifact = "lib/libraylib.a"
```

---

## Platform Profiles

`mpp` should identify dependencies by a build profile.

Recommended profile format:

```txt
<arch>-<os>-<compiler>-<build_type>-<linkage>
```

Examples:

```txt
x86_64-linux-gcc-debug-static
x86_64-linux-clang-release-static
x86_64-windows-msvc-debug-static
x86_64-windows-mingw-release-static
```

Initial supported profiles should be minimal:

```txt
x86_64-linux-gcc-debug-static
x86_64-linux-gcc-release-static
```

Then expand later.

---

## CMake Generation Strategy

For the first version, `mpp` should only auto-populate one file:

```txt
mpp/generated/mpp.cmake
```

The user includes it manually:

```cmake
include(mpp/generated/mpp.cmake)
```

Then links packages with:

```cmake
mpp_link(my_target raylib)
```

This avoids rewriting the user’s full `CMakeLists.txt` and keeps `mpp` safer.

Future versions may support automatic CMake file editing, but it should not be required for the MVP.

---

## MVP Scope

Version 0.1 should support:

- C++ only
- CMake only
- Linux x86_64 GCC first
- local `mpp/vendor/` directory
- recipe lookup from `github.com/CPPLibLinker/vendor`
- static linking
- commands:
  - `mpp init`
  - `mpp add <package>`
  - `mpp build`
  - `mpp run [target]`
  - `mpp clean`
- generated `mpp/generated/mpp.cmake`
- `mpp.toml`
- `mpp.lock`

Out of scope for MVP:

- Makefile generation
- Ninja generation directly
- Zig integration
- C projects
- global binary cache
- package publishing
- dynamic/shared linking
- cross-compilation
- complex transitive dependency resolution

---

## Implementation Plan

### Phase 1 — Project Core

- Create CLI executable `mpp`.
- Implement argument parsing.
- Implement config loading/writing for `mpp.toml`.
- Implement lockfile loading/writing for `mpp.lock`.
- Implement platform profile detection.

Commands:

```sh
mpp init
mpp clean
```

---

### Phase 2 — Recipe Support

- Clone or update recipe repository from `github.com/CPPLibLinker/vendor`.
- Search `packages/<name>/recipe.toml`.
- Parse recipe metadata.
- Select matching profile.

Command:

```sh
mpp add raylib
```

At this phase, `add` can update config and lockfile without fully building dependency artifacts yet.

---

### Phase 3 — Vendoring Dependencies

- Copy dependency source into local project `mpp/vendor/<package>/` without any `.git` directory.
- Checkout locked tag/commit.
- Configure dependency with CMake.
- Build dependency artifact.
- Copy/export include and lib files into predictable local paths.

Output example:

```txt
mpp/vendor/raylib/include/
mpp/vendor/raylib/lib/x86_64-linux-gcc-debug-static/libraylib.a
```

---

### Phase 4 — CMake Generation

Generate:

```txt
mpp/generated/mpp.cmake
```

For each dependency, emit an imported target or helper link function.

Preferred CMake style:

```cmake
add_library(mpp::raylib STATIC IMPORTED)

set_target_properties(mpp::raylib PROPERTIES
  IMPORTED_LOCATION ".../libraylib.a"
  INTERFACE_INCLUDE_DIRECTORIES ".../include"
)

target_link_libraries(mpp::raylib INTERFACE m pthread dl rt X11)

function(mpp_link target package)
  if(package STREQUAL "raylib")
    target_link_libraries(${target} PRIVATE mpp::raylib)
  else()
    message(FATAL_ERROR "Unknown mpp package: ${package}")
  endif()
endfunction()
```

---

### Phase 5 — Build and Run

Implement:

```sh
mpp build
mpp run [target]
```

`mpp build`:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=<type>
cmake --build build
```

`mpp run`:

- call `mpp build`
- find configured target executable
- run it

---

## Long-Term Direction

After the C++/CMake MVP is stable, possible expansions include:

- Windows MSVC support
- Windows MinGW support
- Clang support
- macOS support
- shared linking
- debug/release artifact separation
- global cache
- transitive dependencies
- binary package downloads
- raw Git dependency inference
- package publishing workflow
- C support
- Zig/Make/Ninja integrations

---

## Design Principle

`mpp` should be boring, predictable, and explicit.

It should not guess too much. If a library needs special link flags or build options, that knowledge belongs in `github.com/CPPLibLinker/vendor` as a recipe.

The core tool should focus on:

1. Resolving recipes.
2. Vendoring dependency source/artifacts.
3. Generating CMake integration.
4. Running common build commands.