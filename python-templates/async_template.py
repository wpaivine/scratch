import argparse
import asyncio


async def main(args: argparse.Namespace):
    print(f"Called with: {args}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Default async python template",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print verbose output",
    )
    args = parser.parse_args()
    exit(asyncio.run(main(args)))
