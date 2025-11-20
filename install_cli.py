import enum
import logging
import os
import subprocess
from collections.abc import Collection
from pathlib import Path
from typing import Any, Callable

import click
from ruamel.yaml import YAML

from slivka_bio_installer import conda_installer, docker_installer
from slivka_bio_installer.directory_utils import CopyConflictAction, conflict_handler_skip, copy_files
from slivka_bio_installer.installer import Installer

log = logging.getLogger(__name__)
yaml = YAML()


@click.command()
@click.option("--conda-exe")
@click.option(
    "--conda-env-root",
    type=Path,
    default="./conda_envs",
    show_default="./conda_envs",
)
@click.option("--docker-exe")
@click.option(
    "--interactive/--non-interactive",
    "interactive",
    default=True,
)
@click.option(
    "--service",
    "-s",
    "services",
    multiple=True,
    default=[""],
    show_default="all services",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="WARNING",
)
@click.argument("project-path", type=Path)
def main(
        conda_exe: str,
        conda_env_root: Path,
        docker_exe: str,
        interactive: bool,
        services: list[str],
        log_level: str,
        project_path: Path,
):
    logging.basicConfig(
        level=log_level.upper(),
        format="%(levelname)s: %(message)s",
        force=True,
    )
    copy_conflict_handler = (
        copy_conflict_handler_interactive_click
        if interactive else conflict_handler_skip
    )
    installers: dict[str, Installer] = {}
    if conda_exe is not None:
        if conda_exe.lower() == "autodetect":
            conda_exe = conda_installer.AUTODETECT
        installer = conda_installer.CondaInstaller(
            conda_exe=conda_exe,
            env_root=project_path / conda_env_root,
            project_path=project_path,
            copy_conflict_handler=copy_conflict_handler,
        )
        click.echo(f"Initialized conda: {installer.conda_exe}")
        installers["conda"] = installer
    if docker_exe is not None:
        if docker_exe.lower() == "autodetect":
            docker_exe = docker_installer.AUTODETECT
        installer = docker_installer.DockerInstaller(
            docker_exe=docker_exe,
            project_path=project_path,
            copy_conflict_handler=copy_conflict_handler
        )
        click.echo(f"Initialized docker: {installer.docker_exe}")
        installers["docker"] = installer
    if not installers:
        raise click.UsageError("You must provide at least one of --docker-exe or --conda-exe.")

    service_files = [
        path
        for path in (Path.cwd() / "services").glob("**/*.service.yaml")
        for name in services
        if path.name.startswith(name)
    ]
    if not service_files:
        raise click.UsageError("No services to install.")
    click.echo("Services to install:")
    for service_file in sorted(service_files):
        yaml_data = yaml.load(service_file)
        click.echo(f" - {yaml_data['name']}:{yaml_data['version']}")
    if interactive:
        click.confirm("Confirm", default=True, abort=True)

    init_slivka_conflict_action = (
        SlivkaInitConflictAction.INTERACTIVE_ASK if interactive else
        SlivkaInitConflictAction.SKIP
    )
    init_slivka(project_path, on_conflict=init_slivka_conflict_action)
    copy_files(
        src_dir=Path.cwd() / "shared",
        dest_dir=project_path,
        on_conflict=copy_conflict_handler,
    )

    installer_selection_handler = (
        installer_selection_handler_interactive_click if interactive else
        installer_selection_handler_return_first
    )
    for service_file in service_files:
        install_service(
            service_file,
            installers,
            installer_selection_handler,
            InstallErrorAction.TRY_AGAIN if interactive else InstallErrorAction.SKIP
        )


def copy_conflict_handler_interactive_click(
        src: str | os.PathLike,
        dst: str | os.PathLike
) -> CopyConflictAction:
    click.echo(f"Copying '{src}' but the destination '{dst}' already exists")
    choice = click.prompt(
        "[s]kip, [o]verwrite, [a]bort, [r]aise error",
        type=click.Choice(
            ["s", "skip", "o", "overwrite", "a", "abort", "r", "raise"],
            case_sensitive=False
        ),
        default="skip",
        show_default=True,
        show_choices=False
    )
    choice = choice.lower()
    if choice in ("s", "skip"):
        return CopyConflictAction.SKIP
    if choice in ("o", "overwrite"):
        return CopyConflictAction.OVERWRITE
    if choice in ("a", "abort"):
        return CopyConflictAction.ABORT
    if choice in ("r", "raise"):
        return CopyConflictAction.RAISE
    raise ValueError(f"Invalid choice: {choice}")


class SlivkaInitConflictAction(enum.Enum):
    INTERACTIVE_ASK = 'interactive'
    SKIP = 'skip'
    OVERWRITE = 'overwrite'


def init_slivka(
        project_path: Path,
        on_conflict: SlivkaInitConflictAction = SlivkaInitConflictAction.INTERACTIVE_ASK
):
    log.debug("Initializing slivka in: %s", os.fspath(project_path))
    command = ["slivka", "init", project_path]
    if not project_path.is_dir():
        log.info("Initializing slivka in a new directory.")
        subprocess.run(command, check=True)
        return
    # directory may exist but be empty
    project_exists = next(project_path.iterdir(), False)
    if not project_exists:
        log.info("Initializing slivka in an empty directory.")
    if on_conflict == SlivkaInitConflictAction.OVERWRITE or not project_exists:
        subprocess.run(command, text=True, input="y", check=True)
    elif on_conflict == SlivkaInitConflictAction.INTERACTIVE_ASK:
        subprocess.run(command, text=True)
    elif on_conflict == SlivkaInitConflictAction.SKIP:
        pass
    else:
        raise ValueError(f"Unknown conflict action: {on_conflict}")


class InstallErrorAction(enum.Enum):
    SKIP = enum.auto()
    RAISE = enum.auto()
    TRY_AGAIN = enum.auto()


def install_service(
        service_file: Path,
        available_installers: dict[str, Installer],
        installer_selection_handler: Callable[[str, Collection[str]], str],
        on_error: InstallErrorAction = InstallErrorAction.RAISE
):
    log.debug("Installing service file: %s", service_file)
    config_files = find_install_configs(service_file)
    log.debug("Located config files: %s", config_files.values())
    installer_names = config_files.keys() & available_installers.keys()
    yaml_data = yaml.load(service_file)
    service_name = f"{yaml_data['name']}:{yaml_data['version']}"
    while True:
        selection = installer_selection_handler(service_name, installer_names)
        if selection is None:
            log.info("Skipping %s.", service_name)
            return
        installer = available_installers[selection]
        config = yaml.load(config_files[selection])
        try:
            installer.install(config, service_file)
        except:
            log.exception("Failed to install %s.", service_name)
            if on_error == InstallErrorAction.SKIP:
                log.info("Skipping %s", service_name)
                break
            elif on_error == InstallErrorAction.RAISE:
                raise
            elif on_error == InstallErrorAction.TRY_AGAIN:
                continue
            else:
                raise ValueError("Unknown on-error action: %s", on_error)
        else:
            log.info("Installed %s.", service_name)
            break


def find_install_configs(service_file: Path):
    config_files = {}
    base_name = service_file.name[: -len(".service.yaml")]
    for installer_name, suffix in [
        ("conda", "conda.yaml"),
        ("docker", "docker.yaml"),
    ]:
        config_path = service_file.with_name(f"{base_name}.{suffix}")
        if config_path.is_file():
            config_files[installer_name] = config_path
    return config_files


def installer_selection_handler_return_first(service_name: str, options: Collection[str]) -> str | None:
    return next(iter(options), None)


def installer_selection_handler_interactive_click(service_name: str, options: Collection[str]) -> str | None:
    if not options:
        return None
    choices = ["s", "skip"]
    choice_names = ["[s]kip"]
    for option in options:
        if option == "conda":
            choices.extend(["c", "conda"])
            choice_names.append("[c]onda")
        elif option == "docker":
            choices.extend(["d", "docker"])
            choice_names.append("[d]ocker")
        else:
            log.warning("Unknown installer option: %s", option)
    answer = click.prompt(
        f"Choose installer for {service_name}: {', '.join(choice_names)}",
        type=click.Choice(choices, case_sensitive=False),
        show_choices=False,
    )
    if answer in ("s", "skip"): return None
    if answer in ("c", "conda"): return "conda"
    if answer in ("d", "docker"): return "docker"
    raise ValueError(f"Illegal answer: {answer}")


if __name__ == "__main__":
    main()
