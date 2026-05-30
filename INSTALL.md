# Installing mpp

`mpp` is currently a Python-based command-line tool.

It is not a native compiled binary yet. It runs anywhere the required Python/runtime tools are available.

## Requirements

Required:

- Python 3.11+
- Git
- CMake
- A C++ compiler

Recommended:

- Ninja or Make
- VS Code, clangd, CLion, Visual Studio, or another C++ editor

## Run from source

Clone the repo:

```sh
git clone https://github.com/CPPLibLinker/mpp.git
cd mpp
```

Run with the local wrapper:

```sh
./bin/mpp --version
./bin/mpp init --ide vscode
```

The wrapper runs:

```sh
PYTHONPATH=src python3 -m mpp "$@"
```

## Editable install

For development, install in editable mode:

```sh
cd mpp
python3 -m pip install -e .
```

Then run:

```sh
mpp --version
mpp init
mpp add raylib
mpp build
mpp run
```

## How the command works

`pyproject.toml` defines this CLI entry point:

```toml
[project.scripts]
mpp = "mpp.cli:main"
```

When installed with `pip`, Python creates an executable command named:

```txt
mpp
```

That command imports and runs:

```py
mpp.cli:main
```

## Does mpp run anywhere Python runs?

Mostly yes.

The Python CLI should run on:

- Linux
- macOS
- Windows

as long as Python 3.11+ is installed.

However, building C++ dependencies also requires platform-specific tools and libraries.

For example, a package may require:

- Linux: X11/OpenGL/pthread/dl/m
- Windows: MSVC or MinGW, winmm/gdi32/opengl32
- macOS: Clang and Apple frameworks

So the `mpp` command is portable, but each dependency recipe must support the user's OS/compiler/profile.

## Global recipe lookup

By default, `mpp` looks for recipes in this order:

1. `MPP_VENDOR_REPO=/path/to/vendor`
2. a sibling local repo beside `mpp/`:

```txt
workspace/
  mpp/
  vendor/
```

3. the remote recipe repo cloned into:

```txt
~/.cache/mpp/vendor
```

Remote recipe repo:

```txt
https://github.com/CPPLibLinker/vendor.git
```

## Dependency source cache

When adding a package, `mpp` uses Git internally to fetch source into:

```txt
~/.cache/mpp/sources/
```

Then it copies plain source files into the user project:

```txt
my-project/
  mpp/
    vendor/
      raylib/
```

The project-local vendor copy should not contain any `.git` directory.

## Typical project setup

```sh
mkdir game
cd game
mpp init --ide vscode
mpp add raylib
mpp build
mpp run
```

## Install with pipx

If publishing to PyPI later, users should be able to install with:

```sh
pipx install cppliblinker-mpp
```

For now, local install is:

```sh
python3 -m pip install -e /path/to/mpp
```

## Uninstall

If installed with pip:

```sh
python3 -m pip uninstall cppliblinker-mpp
```

## Troubleshooting

### `mpp: command not found`

Use the local wrapper:

```sh
/path/to/mpp/bin/mpp --version
```

or install it:

```sh
cd /path/to/mpp
python3 -m pip install -e .
```

### `mpp requires Python 3.11+`

Install Python 3.11 or newer.

Check version:

```sh
python3 --version
```

### CMake cannot find compiler

Install a C++ compiler.

Linux examples:

```sh
sudo apt install build-essential cmake git
```

Windows:

- Install Visual Studio Build Tools, or
- Install MinGW-w64

macOS:

```sh
xcode-select --install
```

### IntelliSense cannot find headers

Run:

```sh
mpp sync
mpp build
```

Then reload your editor.

For VS Code, open the generated `.code-workspace` file or open the project folder directly.
