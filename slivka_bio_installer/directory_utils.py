import enum
import logging
import os
import shutil

from collections import namedtuple
from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Callable


class CopyConflictAction(enum.Enum):
    RAISE = 'raise'
    SKIP = 'skip'
    OVERWRITE = 'overwrite'
    ABORT = 'abort'


def conflict_handler_raise(src: str | os.PathLike, dst: str | os.PathLike) -> 'CopyConflictAction':
    return CopyConflictAction.RAISE


def conflict_handler_skip(src: str | os.PathLike, dst: str | os.PathLike) -> 'CopyConflictAction':
    return CopyConflictAction.SKIP


def conflict_handler_overwrite(src: str | os.PathLike, dst: str | os.PathLike) -> 'CopyConflictAction':
    return CopyConflictAction.OVERWRITE


def conflict_handler_abort(src: str | os.PathLike, dst: str | os.PathLike) -> 'CopyConflictAction':
    return CopyConflictAction.ABORT


CopyConflictHandler = Callable[[str | os.PathLike, str | os.PathLike], CopyConflictAction]

DataDirsMapping = namedtuple("DataDirsMapping", ("rel", "src", "dst"))


def find_data_dirs(
        src_root: Path,
        rules: list[dict]
) -> Collection[Path]:
    """
    Find data directories under the given path matching the given rules.
    If no rule is specified, all directories are included.
    If the first rule is not 'include', {include: *} is prepended.

    :return: Set of relative paths matching the patterns
    """
    logging.debug(f"Finding data dirs in {src_root}")

    if not rules:
        rules = [{"include": "*"}]
    if "include" not in rules[0]:
        rules = [{"include": "*"}, *rules]
    matched = set()
    operation_map = {
        "include": matched.add,
        "exclude": matched.discard
    }
    for rule in rules:
        logging.debug("Processing rule: %s", rule)
        if len(rule) > 1:
            raise ValueError(f"Rule contains multiple keys: {rule}")
        try:
            key, val = next(iter(rule.items()))
            operation = operation_map[key]
        except (StopIteration, KeyError):
            raise KeyError(f"Invalid or empty rule: {rule}") from None
        if "**" in val:
            raise ValueError(f"Recursive globbing is not supported: {val}")
        for path in src_root.glob(val):
            logging.debug("Matched path: %s", path)
            if not path.is_dir():
                logging.info("Skipping non-directory path: %s", path)
                continue
            relative_path = path.relative_to(src_root)
            logging.debug("Performing %s of %s", key, relative_path)
            operation(relative_path)
    logging.debug("Matched data dirs: %s", matched)
    return matched


def copy_data_dirs(
        copy_list: Iterable[tuple[Path, Path]],
        on_conflict: CopyConflictHandler = conflict_handler_raise
):
    """
    Copy data directories between two locations.

    :param copy_list:
        Tuples of source and target absolute paths.
    :param on_conflict:
        A callable (strategy) that takes (src, dst) and returns
        a CopyConflictAction. Defaults to raising an error.
    """
    for src, dst in copy_list:
        logging.info("Copying data from %s to %s", src, dst)
        if not dst.exists():
            shutil.copytree(src, dst)
            continue

        logging.info("Destination already exists: %s", dst)
        action = on_conflict(src, dst)
        logging.debug("Action: %s", action)
        if action == CopyConflictAction.RAISE:
            raise FileExistsError(f"Destination already exists: {dst}")
        elif action == CopyConflictAction.SKIP:
            logging.info("Skipping directory: %s", src)
            continue
        elif action == CopyConflictAction.OVERWRITE:
            logging.info("Overwriting destination: %s", dst)
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
            shutil.copytree(src, dst)
        elif action == CopyConflictAction.ABORT:
            logging.info("Aborting")
            break
        else:
            raise ValueError(f"Unknown conflict action: {action}")


def copy_files(
        src_dir: str | os.PathLike[str],
        dest_dir: str | os.PathLike[str],
        on_conflict: CopyConflictHandler = conflict_handler_raise
):
    src_dir = os.path.realpath(src_dir)
    dest_dir = os.path.realpath(dest_dir)
    logging.info("Copying files from '%s' to '%s'", src_dir, dest_dir)
    for base, dirs, files in os.walk(src_dir):
        relative_base = os.path.relpath(base, src_dir)
        for dirname in dirs:
            target_path = os.path.join(dest_dir, relative_base, dirname)
            try:
                os.mkdir(target_path)
            except FileExistsError:
                pass
        for filename in files:
            source_path = os.path.join(base, filename)
            target_path = os.path.join(dest_dir, relative_base, filename)
            if not os.path.exists(target_path):
                shutil.copy2(source_path, target_path)
                continue

            logging.info("Destination already exists: %s", target_path)
            action = on_conflict(source_path, target_path)
            logging.debug("Action: %s", action)
            if action == CopyConflictAction.RAISE:
                raise FileExistsError(f"Destination already exists: {target_path}")
            elif action == CopyConflictAction.SKIP:
                logging.info("Skipping file: %s", target_path)
                continue
            elif action == CopyConflictAction.OVERWRITE:
                logging.info("Overwriting destination: %s", target_path)
                if os.path.isdir(target_path):
                    shutil.rmtree(target_path)
                else:
                    os.unlink(target_path)
                shutil.copy2(source_path, target_path)
            elif action == CopyConflictAction.ABORT:
                logging.info("Copying aborted")
                return
            else:
                raise ValueError(f"Unknown conflict action: {action}")


def find_and_copy_data_dirs(
        src_root: Path,
        dst_root: Path,
        rules: list[dict],
        on_conflict: CopyConflictHandler = conflict_handler_raise
) -> list[DataDirsMapping]:
    """
    Finds data directories under the *src_root* that match the *rules*
    and copies them to the *dst_root*.

    :return: list of relative path, source path and destination paths tuples
    """
    found_paths = find_data_dirs(src_root, rules)
    copy_data_dirs(
        [
            (src_root / path, dst_root / path)
            for path in found_paths
        ],
        on_conflict=on_conflict
    )
    return [DataDirsMapping(path, src_root / path, dst_root / path) for path in found_paths]
