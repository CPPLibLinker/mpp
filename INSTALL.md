# Installing mpp

`mpp` is currently a Python-based command-line tool.

It is not a native compiled binary yet. It runs anywhere the required Python/runtime tools are available.

## Install policy

`mpp` should be available as a global user command:

```sh
mpp --version
```

Do **not** install into system Python.

Use one of these methods:

1. Source symlink install: recommended while developing from this repo.
2. `pipx`: recommended later for packaged/global installs.
3. Virtual environment: useful for isolated development/testing.

Avoid:

```sh
python3 -m pip install -e .
```

unless a virtual environment is active.

Do not use `--break-system-packages` unless you intentionally want to modify your OS-managed Python environment.

## Requirements

Required:

- Python 3.11+
- Git
- CMake
- A C++ compiler

Recommended:

- Ninja or Make
- VS Code, clangd, CLion, Visual Studio, or another C++ editor

## Recommended global source install

Clone the repo:

```sh
git clone https://github.com/CPPLibLinker/mpp.git
cd mpp
```

Install the global user command:

```sh
./install.sh
```

This creates a symlink:

```txt
~/.local/bin/mpp -> /path/to/mpp/bin/mpp
```

Then run from anywhere:

```sh
mpp --version
mpp init raylib --example
mpp build
mpp run
```

Make sure `~/.local/bin` is in `PATH`:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to your shell profile if needed:

```sh
# bash
~/.bashrc

# zsh
~/.zshrc
```

## Run from source without global install

You can always run the local wrapper directly:

```sh
/path/to/mpp/bin/mpp --version
/path/to/mpp/bin/mpp init --ide vscode
```

The wrapper runs:

```sh
PYTHONPATH=src python3 -m mpp "$@"
```

## Install with pipx

For a global CLI install without touching system Python:

```sh
pipx install -e /path/to/mpp
```

If already installed:

```sh
pipx reinstall -e /path/to/mpp
```

If publishing to PyPI later, users should be able to install with:

```sh
pipx install cppliblinker-mpp
```

## Virtual environment install

Use this when you specifically want an isolated Python dev environment:

```sh
cd mpp
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Then run while the venv is active:

```sh
mpp --version
```

After opening a new shell, activate again:

```sh
cd mpp
source .venv/bin/activate
```

Or run without activation:

```sh
./.venv/bin/mpp --version
```

## How the command works

`pyproject.toml` defines this CLI entry point:

```toml
[project.scripts]
mpp = "mpp.cli:main"
```

When installed inside a venv or by `pipx`, Python creates an executable command named:

```txt
mpp
```

For the source symlink install, `~/.local/bin/mpp` points to:

```txt
/path/to/mpp/bin/mpp
```

That wrapper runs:

```sh
PYTHONPATH=/path/to/mpp/src python3 -m mpp "$@"
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

After global install:

```sh
mkdir game
cd game
mpp init --ide vscode
mpp add raylib
mpp build
mpp run
```

Or initialize with an example:

```sh
mkdir game
cd game
mpp init raylib --example
mpp run
```

## Uninstall

If installed with `install.sh`:

```sh
rm -f ~/.local/bin/mpp
```

If installed inside a venv, remove the venv:

```sh
rm -rf .venv
```

If installed with pip inside an active venv:

```sh
python3 -m pip uninstall cppliblinker-mpp
```

If installed with pipx:

```sh
pipx uninstall cppliblinker-mpp
```

## Troubleshooting

### `mpp: command not found`

Check whether `~/.local/bin` is in `PATH`:

```sh
echo "$PATH"
```

Temporarily add it:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Then retry:

```sh
mpp --version
```

Or run the wrapper directly:

```sh
/path/to/mpp/bin/mpp --version
```

### `externally-managed-environment`

Your OS prevents installing packages into system Python.

Use the source symlink install:

```sh
cd /path/to/mpp
./install.sh
```

or use a virtual environment:

```sh
cd /path/to/mpp
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

or use pipx:

```sh
pipx install -e /path/to/mpp
```

Avoid `--break-system-packages`.

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
