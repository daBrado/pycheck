from asyncio import FIRST_COMPLETED, create_subprocess_exec, create_task, wait
from asyncio.subprocess import PIPE
from collections.abc import MutableMapping
from os import walk
from os.path import dirname, exists, join
from shlex import split
from typing import List, NamedTuple, Tuple, Union, cast

from inotify_simple import INotify, flags, masks  # type: ignore
from tomlkit.api import dumps, parse, table
from tomlkit.container import Container


class SubprocessError(RuntimeError):
    pass


def p(s: str) -> None:
    print(s, flush=True)


async def run_subprocess(*cmds: Union[str, Tuple[str, str]]) -> None:
    tasks = {
        create_task(proc.communicate()): (name, proc)
        for name, proc in [
            (name, await create_subprocess_exec(*split(cmd), stdout=PIPE, stderr=PIPE))
            for name, cmd in [
                (split(item)[0], item) if isinstance(item, str) else item
                for item in cmds
            ]
        ]
    }
    failed = False
    while tasks:
        done, pending = await wait(tasks.keys(), return_when=FIRST_COMPLETED)
        for task in done:
            stdout, stderr = task.result()
            name, proc = tasks.pop(task)
            if proc.returncode != 0:
                failed = True
            border = "*" if proc.returncode == 0 else "!"
            output = "\n".join(
                [
                    f"{border} {line}"
                    for line in (
                        (
                            stdout.decode().strip() + "\n" + stderr.decode().strip()
                        ).strip()
                    ).splitlines()
                ]
            )
            p(
                f"{border*3} {name}"
                + (f"\n{output}\n{border} " if output else " ")
                + f"=> {proc.returncode}"
            )
        if not pending:
            break
    if failed:
        raise SubprocessError()


async def run_formatters(check_only: bool = False) -> None:
    await run_subprocess(f"isort {'--check' if check_only else ''} .")
    await run_subprocess(f"black {'--check' if check_only else ''} .")


async def run_checks(has_slow_tests: bool, cache_dir: str) -> None:
    PYTEST = f"pytest -o cache_dir={cache_dir}/pytest -vv"
    await run_subprocess(
        "flake8 .",
        f"mypy --cache-dir {cache_dir}/mypy",
        PYTEST + (" -m 'not slow'" if has_slow_tests else ""),
    )
    if has_slow_tests:
        await run_subprocess(("pytest [slow]", f"{PYTEST} -x -m slow"))


async def run_once(has_slow_tests: bool, check_only: bool, cache_dir: str) -> bool:
    try:
        await run_formatters(check_only)
        await run_checks(has_slow_tests=has_slow_tests, cache_dir=cache_dir)
    except SubprocessError:
        p("!!! Problems found.")
        return False
    else:
        p("*** All good.")
        return True


async def run_watch(has_slow_tests: bool, watch_delay: int, cache_dir: str) -> None:
    inotify = INotify()
    watch_flags = (
        masks.MOVE | flags.CREATE | flags.DELETE | flags.MODIFY | flags.DELETE_SELF
    )
    watchers = {}
    for root, dirs, _ in walk("."):
        for d in [".git", "__pycache__"]:
            if d in dirs:
                dirs.remove(d)
        wd = inotify.add_watch(root, watch_flags)
        watchers[wd] = root
    paths: List[str] = []
    finalize = False
    while True:
        events = inotify.read(
            timeout=(watch_delay if (paths or finalize) else None), read_delay=None
        )
        for event in events:
            if event.name.endswith(".isorted"):
                continue
            path = join(watchers[event.wd], event.name)
            if event.mask & flags.ISDIR and event.mask & (
                flags.CREATE | flags.MOVED_TO
            ):
                wd = inotify.add_watch(path, watch_flags)
                watchers[wd] = path
            elif event.mask & flags.IGNORED:
                del watchers[event.wd]
            else:
                paths.append(path)
        if not events:
            if paths:
                if not finalize:
                    p("\n")
                try:
                    await run_formatters()
                except SubprocessError:
                    p("!!! Problems found.")
                else:
                    finalize = True
                paths.clear()
            elif finalize:
                try:
                    await run_checks(has_slow_tests=has_slow_tests, cache_dir=cache_dir)
                except SubprocessError:
                    p("!!! Problems found.")
                else:
                    p("*** All good.")
                finalize = False


class PycheckConfig(NamedTuple):
    has_slow_tests: bool


def _cget(c: Container, *keys: str) -> Container:
    for k in keys:
        c = cast(Container, c[k])
    return c


def handle_config() -> PycheckConfig:
    """Add configurations if they are missing."""
    data_dir = join(dirname(__file__), "data")
    base_pyproj = parse(open(join(data_dir, "pyproject.toml")).read())
    pyproj = parse(open("pyproject.toml").read())
    base_tools = base_pyproj["tool"]
    assert isinstance(base_tools, MutableMapping)
    pyproj_changed = False
    if "tool" not in pyproj:
        pyproj["tool"] = table()
        pyproj_changed = True
    tools = pyproj["tool"]
    assert isinstance(tools, MutableMapping)
    for k, v in base_tools.items():
        if k not in tools:
            tools[k] = v
            pyproj_changed = True
    if pyproj_changed:
        open("pyproject.toml", "w").write(dumps(pyproj))
    if not exists(".flake8"):
        open(".flake8", "w").write(open(join(data_dir, "flake8")).read())
    return PycheckConfig(
        has_slow_tests=any(
            m.startswith("slow:")
            for m in _cget(pyproj, "tool", "pytest", "ini_options", "markers")
        )
    )


async def amain(
    *, watch: bool, watch_delay: int, check_only: bool, cache_dir: str
) -> int:
    config = handle_config()
    if watch:
        try:
            await run_once(
                has_slow_tests=config.has_slow_tests,
                check_only=False,
                cache_dir=cache_dir,
            )
            await run_watch(
                has_slow_tests=config.has_slow_tests,
                watch_delay=watch_delay,
                cache_dir=cache_dir,
            )
        except KeyboardInterrupt:
            p("Exiting.")
        return 0
    else:
        return (
            0
            if await run_once(
                has_slow_tests=config.has_slow_tests,
                check_only=check_only,
                cache_dir=cache_dir,
            )
            else 1
        )
