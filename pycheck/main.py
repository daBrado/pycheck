from argparse import ArgumentParser
from asyncio import run
from os import environ
from os.path import join

from .pycheck import amain

parser = ArgumentParser(description="Check the project.")
parser.add_argument("--watch", action="store_true")
parser.add_argument(
    "--watch-delay", type=int, default=100, help="watch debounce delay (ms)"
)
parser.add_argument(
    "--check-only", action="store_true", help="only check and make no changes"
)
parser.add_argument(
    "--cache-dir",
    type=str,
    default=environ.get("XDG_CACHE_HOME", join(environ["HOME"], ".cache")),
)


def main() -> None:
    exit(run(amain(**vars(parser.parse_args()))))
