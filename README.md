# Slivka Bio Installer

This repository provides an installer for building Slivka projects from curated bioinformatics service definitions. It is intended for setting up custom Slivka-Bio installations where you want to choose which services to install. The installer can use conda-compatible and/or Docker-backed installation methods depending on the services you select.

## Cloning the repository

For most selected-service installs, start with a normal clone:

```bash
git clone https://github.com/proteinverse/slivka-bio-installer.git
cd slivka-bio-installer
```

The only current submodule is the ProteinMPNN source tree used by `mpnn_design_residues-1.0.1`. You do not need to initialise submodules unless you intend to install that service. To fetch all submodules, run:

```bash
git submodule update --init --recursive
```

Alternatively, clone the repository with all submodules up front:

```bash
git clone --recurse-submodules https://github.com/proteinverse/slivka-bio-installer.git
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

## Service configuration files

Service definitions live under `services/`, with each tool version keeping its own configuration files:

- `*.service.yaml` describes the Slivka service itself: metadata, parameters, command line arguments, outputs, tests, and execution runners.
- `*.conda.yaml` describes the conda-backed installation for that service, including files to copy and the conda channels and dependencies required to run it.
- `*.docker.yaml` describes the Docker-backed installation for that service, including files to copy and the Dockerfile, image name, and tag used to build the runtime image.

## Installing tools

Move to the directory where you cloned the installer repository and run:

```bash
python install_cli.py --conda-exe autodetect <PATH>
```

substituting the project destination for _&lt;PATH&gt;_. Use `--docker-exe autodetect` instead, or as well, when using Docker-backed installers.
The installer will display the list of tools that will be installed and prompt for the installation method for each one of them.
If the installation fails, you will be prompted to retry, skip the installation of that service, abort and stop the installer or ignore the error and proceed with the installation.
