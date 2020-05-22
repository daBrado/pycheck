from argparse import ArgumentParser
from asyncio import run

from .pycheck import amain

parser = ArgumentParser(description="Check the project.")
parser.add_argument("--watch", action="store_true")
parser.add_argument(
    "--watch-delay", type=int, default=100, help="watch debounce delay (ms)"
)
parser.add_argument(
    "--cache-dir", type=str, default="/tmp/pycheck", help="cache results"
)

if __name__ == "__main__":
    run(amain(parser.parse_args()))
