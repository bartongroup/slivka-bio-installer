import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path, PosixPath

from ruamel.yaml import YAML

from slivka_bio_installer.context_maps import Context, SimpleContextMap, ChainContextMap
from slivka_bio_installer.directory_utils import CopyConflictHandler, find_and_copy_data_dirs, DataDirsMapping
from slivka_bio_installer.installer import Installer
from slivka_bio_installer.template_resolver import resolve_map

yaml = YAML()
AUTODETECT = object()

log = logging.getLogger(__name__)


class DockerInstaller(Installer):
    def __init__(
            self,
            docker_exe: str | os.PathLike[str],
            project_path: Path,
            copy_conflict_handler: CopyConflictHandler,
    ):
        if docker_exe == AUTODETECT:
            log.debug("Autodetecting docker exe")
            self._docker_exe = autodetect_docker_exe()
        else:
            self._docker_exe = docker_exe
        log.debug("Docker exe: %s", docker_exe)
        if self._docker_exe is None:
            raise FileNotFoundError(
                docker_exe if docker_exe is not AUTODETECT else "docker"
            )
        self._project_path = project_path
        self._copy_conflict_handler = copy_conflict_handler

    @property
    def docker_exe(self):
        return self._docker_exe

    def install(
            self,
            config: dict,
            service_template_file: Path
    ):
        service_name = service_template_file.name[:-len(".service.yaml")]
        image_name = self._ensure_image(config, service_template_file.parent)

        data_dirs: list[DataDirsMapping] = find_and_copy_data_dirs(
            src_root=service_template_file.parent,
            dst_root=self._project_path / "data" / service_name,
            rules=config.get("files", []),
            on_conflict=self._copy_conflict_handler
        )
        data_dirs_context = SimpleContextMap(
            ((os.fspath(rel), os.fspath(dst)) for rel, _src, dst in data_dirs),
            prefix="local-path"
        )
        container_data_path = PosixPath("/data")
        runtime_data_dirs_context = SimpleContextMap(
            (
                (os.fspath(rel), os.fspath(container_data_path / rel))
                for rel, _src, _dst in data_dirs
            ),
            prefix="runtime-path"
        )
        docker_context = DockerContext(self._docker_exe, image_name)

        context = ChainContextMap(
            docker_context, data_dirs_context, runtime_data_dirs_context
        )
        service_vars = resolve_map(config.get("vars", {}), context)
        vars_context = SimpleContextMap(
            service_vars.items(), prefix="var"
        )
        context.append(vars_context)
        self.write_service_file(service_template_file, context, data_dirs)

    def write_service_file(
            self,
            service_template_file: Path,
            context: Context,
            data_paths: Iterable[DataDirsMapping]
    ):
        mount_args = []
        for dir_map in data_paths:
            dest_path = context[f"runtime-path:{os.fspath(dir_map.rel)}"]
            # instruct docker to bind directory from where it was copied to,
            # to the runtime-path inside the image
            mount_args.extend((
                "--mount",
                f"type=bind,src={dir_map.dst},dst={dest_path},ro"
            ))
        wrapper_script = os.path.join("${SLIVKA_HOME}", "scripts", "run_with_docker.sh")

        service_config = yaml.load(service_template_file)
        service_config = resolve_map(service_config, context)
        service_config["command"] = [
            shutil.which("bash"),
            wrapper_script,
            *mount_args,
            *service_config["command"]
        ]
        docker_env_vars = {
            key: val for key, val in os.environ.items() if key.startswith("DOCKER_")
        }
        service_config["env"] = {**docker_env_vars, **service_config.get("env", {})}

        (self._project_path / "services").mkdir(exist_ok=True)
        destination_path = self._project_path / "services" /service_template_file.name
        yaml.dump(service_config, destination_path)
        return destination_path


    def _ensure_image(self, config: dict, directory: str | os.PathLike[str]) -> str:
        """
        Ensures the docker image exists by pulling or building it.
        Returns full image tag <name>:<tag>.
        """
        if "pull" in config:
            if isinstance(config["pull"], str):
                return pull_docker_image(self._docker_exe, config["pull"])
            else:
                return pull_docker_image(
                    self._docker_exe,
                    image_name=config["pull"]["image"],
                    image_tag=config["pull"].get("tag"),
                    platform=config["pull"].get("platform"),
                )
        if "build" in config:
            directory = Path(directory).resolve()
            return build_docker_image(
                self._docker_exe,
                directory / config["build"]["dockerfile"],
                image_name=config["build"]["image"],
                image_tag=config["build"].get("tag"),
                platform=config["build"].get("platform"),
            )
        raise ValueError("Neither 'pull' nor 'build' specified in the config.")


def autodetect_docker_exe():
    return next(filter(None, _docker_exe_candidates()), None)


def _docker_exe_candidates():
    yield shutil.which("docker")
    yield shutil.which("podman")


def pull_docker_image(
        docker_exe: str | os.PathLike,
        image_name: str,
        image_tag: str | None = None,
        platform: str | None = None,
):
    full_tag = f"{image_name}:{image_tag}" if image_tag else image_name
    if test_image_exists(docker_exe, full_tag):
        log.info("Image '%s' already exists", full_tag)
    options = []
    if platform:
        options.extend(["--platform", platform])
    subprocess.run(
        [docker_exe, "image", "pull", *options, "--quiet", full_tag],
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
        check=True,
    )
    return full_tag


def build_docker_image(
        docker_exe: str | os.PathLike[str],
        dockerfile: str | os.PathLike[str],
        image_name: str,
        image_tag: str | None = None,
        platform: str | None = None,
        rebuild: bool = False
):
    if not os.path.isfile(dockerfile):
        raise FileNotFoundError(dockerfile)
    full_tag = f"{image_name}:{image_tag}" if image_tag else image_name
    if not rebuild and test_image_exists(docker_exe, full_tag):
        log.info("Image '%s' already exists. Skipping build.", full_tag)
        return full_tag
    options = []
    if platform:
        options.extend(["--platform", platform])
    subprocess.run(
        [
            docker_exe,
            "buildx",
            "build",
            "--tag", full_tag,
            "--file", dockerfile,
            *options,
            os.path.dirname(dockerfile)
        ],
        cwd=os.path.dirname(dockerfile),
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
        check=True,
    )
    return full_tag


def test_image_exists(
        docker_exe: str | os.PathLike,
        image_tag: str
):
    return bool(subprocess.check_output([docker_exe, "image", "ls", "-q", image_tag]))



class DockerContext(Context):
    def __init__(self, docker_exe, image_name):
        self._docker_exe = docker_exe
        self._image_name = image_name
        self._env_vars = None
        self._which_cache = {}

    def __getitem__(self, item: str):
        key, name = item.split(":", 1)
        if key == "env":
            if self._env_vars is None:
                self._env_vars = get_image_env(self._docker_exe, self._image_name)
            value = self._env_vars[name]
        elif key == "which":
            if name in self._which_cache:
                value = self._which_cache[name]
            else:
                executable_path = which_in_image(self._docker_exe, self._image_name, name)
                self._which_cache[name] = executable_path
                value = executable_path
        else:
            log.debug("DockerContext[%s] = <missing>", item)
            raise KeyError(item)
        log.debug("DockerContext[%s] = %r", item, value)
        return value


def get_image_env(docker_exe, image_name):
    log.debug("Reading env vars for image: %s", image_name)
    output = subprocess.check_output(
        [docker_exe, "run", "--rm", "--entrypoint", "env", image_name],
        text=True,
    )
    log.debug("Env output:\n%s", output)
    env_vars = dict(line.split("=", 1) for line in output.splitlines())
    log.debug("Parsed env vars: %s", env_vars)
    return env_vars


def which_in_image(docker_exe, image_name, prog_name):
    log.debug("Finding executable '%s' in image: %s", prog_name, image_name)
    try:
        # FIXME: some images such as micromamba require special script to be an entry point
        output = subprocess.check_output(
            [
                docker_exe,
                "run",
                "--rm",
                "--entrypoint",
                "which",
                image_name,
                prog_name
            ],
            text=True
        )
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            log.error("Executable '%s' not found in image '%s'", prog_name, image_name)
            raise FileNotFoundError(f"Executable not found: {prog_name}")
        log.exception("'which' failed to run in image '%s'", image_name)
        raise
    executable_path = output.strip()
    log.debug("Executable '%s' found: %s", prog_name, executable_path)
    return executable_path
