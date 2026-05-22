# Slivka Bio Installer

## Cloning the repository

This repository uses other repositories which are included as git submodules.
By default `git clone` does not clone submodules recursively.
Use `--recurse-submodules` to clone the repo with all included submodules, e.g.

```bash
git clone --recurse-submodules https://github.com/proteinverse/slivka-bio-installer.git
```

If you have already cloned the repository without submodules then run

```bash
git submodule init && git submodule update
```

## Prerequisites

As a bare minimum, the installer requires Python, click, ruamel.yaml and Slivka.
You can install these dependencies with the conda package manager:

```bash
conda create -n slivka-installer -c conda-forge python=3.10 click ruamel.yaml slivka::slivka
```

If you prefer the latest beta version of slivka then install slivka from the _beta_ subdirectory

```bash
conda create -n slivka-installer -c conda-forge python=3.10 click ruamel.yaml slivka/label/beta::slivka
```

The installer can use _conda_ and/or _docker_ backends. At least one of these must be available and passed to the CLI with `--conda-exe` or `--docker-exe`.

A running MongoDB server is required by Slivka at runtime to store job state. Slivka must be able to connect to one when the server, scheduler, and queue are started.

## Installing tools

Move to the directory where you cloned the installer repository and run:

```bash
python install_cli.py --conda-exe autodetect <PATH>
```

substituting the project destination for _&lt;PATH&gt;_. Use `--docker-exe autodetect` instead, or as well, when using Docker-backed installers.
The installer will display the list of tools that will be installed and prompt for the installation method for each one of them.
If the installation fails, you will be prompted to retry, skip the installation of that service, abort and stop the installer or ignore the error and proceed with the installation.
