from pathlib import Path
from typing import Protocol


class Installer(Protocol):
    def install(self, config: dict, service_template_file: Path) -> None:
        ...
