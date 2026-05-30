# mpp

A small C++ dependency linker that vendors libraries into your project and generates CMake glue.

```sh
mpp init --name game --vendor raylib --example --ide vscode
cd game
mpp run
```

`mpp` is intentionally simple:

- C++ focused
- CMake focused
- Git recipe based
- local vendoring into `mpp/vendor/<package>`
- generated integration in `mpp/generated/mpp.cmake`

It is not trying to replace Conan/vcpkg/CMake. It is a fast path for adding common C++ libraries with sane recipes.

---

## Key map

| Go to | Section |
|---|---|
| Install | [Install](#install) |
| Create project | [Quick start](#quick-start) |
| Add dependencies | [Add packages](#add-packages) |
| Examples | [Recipe examples](#recipe-examples) |
| Build/run/clean | [Build commands](#build-commands) |
| IDE support | [Editor support](#editor-support) |
| Project files | [Generated layout](#generated-layout) |
| Dev architecture | [Source layout](#source-layout) |
| Recipe repo | [Vendor recipes](#vendor-recipes) |

---

## Install

For local source installs, use the global user symlink:

```sh
git clone https://github.com/CPPLibLinker/mpp.git
cd mpp
./install.sh
mpp --version
```

This creates:

```txt
~/.local/bin/mpp -> /path/to/mpp/bin/mpp
```

Make sure this is in your shell path:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

More install details: [INSTALL.md](INSTALL.md)

---

## Quick start

Create a project with a vendored library and starter example:

```sh
mpp init --name game --vendor raylib --example --ide vscode
cd game
mpp run
```

Create in the current directory instead:

```sh
mpp init --here --name game --vendor raylib --example
```

Create a blank project:

```sh
mpp init --name game --ide vscode
cd game
mpp add raylib
mpp run
```

---

## Add packages

```sh
mpp add raylib
mpp add raylib-6.0
mpp add raylib-master
mpp add fmt
mpp add sokol
```

Use recipe platform presets:

```sh
mpp add raylib --platform sdl
mpp add raylib --platform wayland
```

Pass CMake options:

```sh
mpp add raylib -D USE_AUDIO=OFF
mpp add fmt -D FMT_HEADER_ONLY=ON
```

Inspect package options:

```sh
mpp options raylib
mpp options sokol
```

---

## Recipe examples

Recipes can provide starter `src/main.cpp` files.

```sh
mpp init --name ray --vendor raylib --example
mpp init --name ray --vendor raylib --example shapes
mpp init --name sokol-demo --vendor sokol --example window
mpp init --name test-fmt --vendor fmt --example
```

Available examples are listed by:

```sh
mpp options <package>
```

---

## Build commands

```sh
mpp build          # configure and build with CMake
mpp run            # build, then run default target
mpp run <target>   # run a specific target
mpp sync           # regenerate mpp/generated/mpp.cmake and editor files
mpp clean          # remove build output and generated files
mpp clean --vendor # also remove vendored packages
```

---

## Editor support

During `init`, choose an editor preset:

```sh
mpp init --ide vscode
mpp init --ide clangd
mpp init --ide clion
mpp init --ide visualstudio
mpp init --ide all
mpp init --ide none
```

Generated files may include:

```txt
.vscode/settings.json
.vscode/c_cpp_properties.json
<project>.code-workspace
.clangd
compile_flags.txt
CMakePresets.json
```

Aliases:

```txt
nvim, neovim, vim, zed, sublime, kate -> clangd
```

---

## Generated layout

A project using `mpp` looks like:

```txt
game/
  CMakeLists.txt
  mpp.toml
  mpp.lock
  src/main.cpp
  mpp/
    generated/mpp.cmake
    vendor/
      raylib/
        CMakeLists.txt
        src/
        ...
```

Important files:

| File | Purpose |
|---|---|
| `mpp.toml` | project dependencies/settings |
| `mpp.lock` | resolved commits, profile, recipe revision |
| `mpp/generated/mpp.cmake` | generated CMake integration |
| `mpp/vendor/<package>` | plain copied dependency source, no `.git` |

---

## Vendor recipes

Recipes live in the separate repo:

```txt
https://github.com/CPPLibLinker/vendor
```

Local dev layout:

```txt
workspace/
  mpp/
  vendor/
```

Recipe lookup order:

1. `MPP_VENDOR_REPO=/path/to/vendor`
2. sibling `../vendor`
3. cached clone at `~/.cache/mpp/vendor`

Dependency source cache:

```txt
~/.cache/mpp/sources/
```

Project vendor copies never include `.git` directories.

---

## Source layout

```txt
src/mpp/
  cli.py              # CLI parser and command orchestration
  core.py             # shared config/project/process helpers
  recipes.py          # recipe lookup/version/profile/platform logic
  vendor.py           # fetch/cache/copy dependency source
  build/cmake.py      # CMake generation and CMakeLists integration
  editor/common.py    # editor dispatch
  editor/vscode.py    # VS Code config
  editor/clangd.py    # clangd-compatible config
```

---

## Current scope

Supported now:

- C++ projects
- CMake builds
- local vendoring
- recipe options/platform presets
- recipe examples
- Linux x86_64 GCC tested on current machine

Planned/possible later:

- more tested OS/compiler profiles
- binary artifacts/cache
- richer transitive dependency handling
- more build-system integrations
