import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ruamel.yaml import YAML

from slivka_bio_installer.context_maps import Context, SimpleContextMap, ChainContextMap
from slivka_bio_installer.directory_utils import find_and_copy_data_dirs, CopyConflictHandler
from slivka_bio_installer.installer import Installer
from slivka_bio_installer.template_resolver import resolve_map

yaml = YAML()
AUTODETECT = object()

log = logging.getLogger(__name__)


class CondaInstaller(Installer):
    def __init__(
            self,
            conda_exe: str | os.PathLike[str],
            env_root: Path,
            project_path: Path,
            copy_conflict_handler: CopyConflictHandler,
    ):
        if conda_exe == AUTODETECT:
            log.debug("Autodetecting conda exe")
            self._conda_exe = autodetect_conda_exe()
        else:
            self._conda_exe = conda_exe
        log.debug("Conda exe: %s", self._conda_exe)
        if self._conda_exe is None:
            raise FileNotFoundError(
                conda_exe if conda_exe is not AUTODETECT else "conda"
            )
        self._env_root = env_root
        self._project_path = project_path
        self._copy_conflict_handler = copy_conflict_handler

    @property
    def conda_exe(self):
        return self._conda_exe

    def install(
            self,
            config: dict,
            service_template_file: Path,
    ):
        log.debug("Installing service from file '%s'", service_template_file.name)
        log.debug("Using CondaInstaller with config: %s", config)
        service_name = service_template_file.name[:-len(".service.yaml")]
        env_prefix = os.path.join(self._env_root, service_name)

        if "environment" in config:
            with tempfile.NamedTemporaryFile(suffix=".yaml") as env_file:
                yaml.dump(config["environment"], env_file)
                env_file.flush()
                create_conda_env(
                    self._conda_exe,
                    env_prefix,
                    env_file.name
                )
        else:
            # find env file in the same directory as service file
            env_file = config.get("environment-file", "environment.yaml")
            env_file = service_template_file.with_name(env_file)
            create_conda_env(self._conda_exe, env_prefix, env_file)

        data_dirs = find_and_copy_data_dirs(
            src_root=service_template_file.parent,
            dst_root=self._project_path / "data" / service_name,
            rules=config.get("files", []),
            on_conflict=self._copy_conflict_handler
        )
        data_dirs_context = SimpleContextMap(
            ((os.fspath(rel), os.fspath(dst)) for rel, src, dst in data_dirs),
            prefix="local-path"
        )
        runtime_data_dirs_context = SimpleContextMap(
            ((os.fspath(rel), os.fspath(dst)) for rel, src, dst in data_dirs),
            prefix="runtime-path"
        )
        conda_context = CondaContext(self._conda_exe, env_prefix)

        # first context is used to interpolate *vars* in the config
        context = ChainContextMap(
            conda_context, data_dirs_context, runtime_data_dirs_context
        )
        service_vars = resolve_map(config.get("vars", {}), context)
        vars_context = SimpleContextMap(
            service_vars.items(), prefix="var"
        )
        context.append(vars_context)
        self.write_service_file(service_template_file, context, env_prefix)

    def write_service_file(
            self,
            service_template_file: Path,
            context: Context,
            env_prefix: str | os.PathLike[str],
    ):
        service_config = yaml.load(service_template_file)
        service_config = resolve_map(service_config, context)
        service_config["command"] = [
            self._conda_exe,
            "run",
            "-p", os.fspath(env_prefix),
            *service_config["command"]
        ]

        (self._project_path / "services").mkdir(exist_ok=True)
        destination_path = self._project_path / "services" / service_template_file.name
        yaml.dump(service_config, destination_path)
        return destination_path


def autodetect_conda_exe():
    return next(filter(None, _conda_exe_candidates()), None)


def _conda_exe_candidates():
    yield os.environ.get("MAMBA_EXE")
    yield os.environ.get("CONDA_EXE")
    yield shutil.which("micromamba")
    yield shutil.which("mamba")
    yield shutil.which("conda")


def create_conda_env(
        conda_exe: str,
        env_prefix: os.PathLike | str,
        env_file_path: os.PathLike | str
) -> Path:
    env_file_path = os.path.realpath(env_file_path)
    if not os.path.isfile(env_file_path):
        log.error("Environment file not found: %s", env_file_path)
        raise FileNotFoundError(f"Environment file not found: {env_file_path}")
    if os.path.isdir(env_prefix):
        log.warning("Environment already exists: %s", env_prefix)
        return Path(env_prefix)
    if os.path.exists(env_prefix):
        log.error("Unable to create conda env - file exists: %s", env_prefix)
        raise FileExistsError(env_prefix)
    subprocess.run(
        [
            conda_exe,
            "env",
            "create",
            "--prefix", str(env_prefix),
            "--file", env_file_path,
            "--yes",
            "--quiet"
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
        check=True
    )
    return Path(env_prefix)


class CondaContext(Context):
    def __init__(self, conda_exe, env_path):
        self._conda_exe = conda_exe
        self._env_path = env_path

    def __getitem__(self, item: str):
        key, name = item.split(":", 1)
        path = f"{self._env_path}/bin{os.pathsep}{os.environ['PATH']}"
        if key == "env":
            return path if name == "PATH" else os.environ[name]
        if key == "which":
            exe = shutil.which(name, path=path)
            if not exe:
                raise FileNotFoundError(name)
            return exe
        raise KeyError(item)
