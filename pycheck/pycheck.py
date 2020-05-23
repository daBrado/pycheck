from asyncio import FIRST_COMPLETED, create_subprocess_exec, create_task, wait
from asyncio.subprocess import PIPE
from os import walk
from os.path import join

from inotify_simple import INotify, flags, masks  # type: ignore


class SubprocessError(RuntimeError):
    pass


async def run_cmds(*cmds):
    tasks = {
        create_task(proc.communicate()): (cmd, proc)
        for cmd, proc in [
            (cmd, await create_subprocess_exec(*cmd.split(), stdout=PIPE, stderr=PIPE))
            for cmd in cmds
        ]
    }
    failed = False
    while tasks:
        done, pending = await wait(tasks.keys(), return_when=FIRST_COMPLETED)
        for task in done:
            stdout, stderr = task.result()
            cmd, proc = tasks.pop(task)
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
            print(
                f"{border*3} "
                + cmd
                + (f"\n{output}\n{border} " if output else " ")
                + f"=> {proc.returncode}"
            )
        if not pending:
            break
    if failed:
        raise SubprocessError()


async def check_all(cache_dir):
    # isort configuration from:
    #   https://black.readthedocs.io/en/stable/the_black_code_style.html#how-black-wraps-lines  # noqa: B950
    await run_cmds(
        "isort "
        "--multi-line=3 "
        "--trailing-comma "
        "--force-grid-wrap=0 "
        "--use-parentheses "
        "--line-width=88 "
        "-rc "
        "."
    )
    await run_cmds("black .")
    await run_cmds(
        # Based on:
        #   https://black.readthedocs.io/en/stable/the_black_code_style.html#line-length  # noqa: B950
        (
            "flake8 "
            "--max-line-length=80 "
            "--max-complexity=18 "
            "--select=B,C,E,F,W,B9 "
            "--ignore=E203,E501,W503,B008 "
            "."
        ),
        (
            "mypy "
            "--disallow-any-generics "
            "--warn-redundant-casts "
            f"--warn-unused-ignores --cache-dir {join(cache_dir, 'mypy')} ."
        ),
        f"pytest -o cache_dir={join(cache_dir, 'pytest')}",
    )


async def check(cache_dir):
    try:
        await check_all(cache_dir=cache_dir)
    except SubprocessError:
        print("!!! Problems found.")
        return False
    print("*** All good.")
    return True


async def amain(args):
    success = await check(cache_dir=args.cache_dir)
    if not args.watch:
        exit(0 if success else 1)

    inotify = INotify()
    watch_flags = (
        masks.MOVE | flags.CREATE | flags.DELETE | flags.MODIFY | flags.DELETE_SELF
    )
    watchers = {}
    for root, _, _ in walk("."):
        wd = inotify.add_watch(root, watch_flags)
        watchers[wd] = root
    paths = []
    while True:
        events = inotify.read(
            timeout=(args.watch_delay if paths else None), read_delay=None,
        )
        for event in events:
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
        if not events and paths:
            print("\n")
            await check(cache_dir=args.cache_dir)
            paths = []
