"""Script for calculating which packages installed with pacman result in the most dependencies"""
import argparse
import asyncio
from functools import cache


async def run(cmd: str) -> list[str]:
    """
    Runs a shell command async

    Args:
        cmd: command to run

    Returns: list of lines returned by the shell command

    """
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    return stdout.decode().split("\n")


async def packages_names(pacman_args: str = "e") -> set[str]:
    """
    Query all installed packages with `pacman -Q[e]`
    Args:
        pacman_args: additional args to pass to pacman (default: `pacman -Qe`)

    Returns: set of strings representing all manually installed packages

    """
    package_names = await run(f"pacman -Q{pacman_args}")
    return set(
        package_name.split(" ")[0]
        for package_name in package_names
        if package_name.strip()
    )


async def package_dependencies(package: str) -> set[str]:
    """
    Query all dependencies for a package, using output of `pacman -Qi`
    Args:
        package: package to query

    Returns: set of all dependencies of the given package

    """
    pacman_info = await run(f"pacman -Qi {package}")
    info_pairs = (
        info_line.split(":", 1) for info_line in pacman_info if ":" in info_line
    )
    info_dict = {key.strip().lower(): value.strip() for key, value in info_pairs}
    return info_dict.get("depends on", "").split("  ")


async def packages_and_dependencies() -> dict[str, set[str]]:
    """
    Construct a mapping of packages -> dependencies, running the pacman calls concurrently with async
    Returns: dict mapping installed packages to sets of their dependencies

    """
    packages_set = await packages_names()

    async def collect_dependencies(package: str) -> tuple[str, set[str]]:
        return package, await package_dependencies(package)

    return dict(
        await asyncio.gather(
            *(collect_dependencies(package) for package in packages_set)
        )
    )


class DependencyCalculator:
    def __init__(self, dependency_dict: [str, set[str]]):
        """

        Args:
            dependency_dict: dictionary mapping package names to their set of direct dependencies
        """
        self._dependency_dict = dependency_dict

    @cache
    def calculate_all_dependencies(self, package: str) -> set[str]:
        """
        recursively calculates the number of dependencies of this package, and its children
        Args:
            package: package to calculate dependencies
        """
        dependencies = self._dependency_dict.get(package, set())
        additional_dependencies = set().union(
            *(
                self.calculate_all_dependencies(dependency)
                for dependency in dependencies
            )
        )
        return {*dependencies, *additional_dependencies}


async def main(n: int = 10, recursive: bool = False):
    """
    List number of manually installed packages and show the top N packages with the most dependencies
    Args:
        recursive: whether to calculate package dependencies recursively
        n: number of worst offenders to show
    """
    packages = await packages_and_dependencies()
    print(f"total installed packages: {len(packages)}")

    if recursive:
        dependency_calcualator = DependencyCalculator(packages)
        recursive_dependencies = {
            package: dependency_calcualator.calculate_all_dependencies(package)
            for package in packages
        }
    else:
        recursive_dependencies = packages

    packages_sorted = sorted(
        packages.keys(), key=lambda package: -len(recursive_dependencies[package])
    )
    print(f"top {n} packages:")
    print(
        "\n".join(
            f"  {package}: {len(recursive_dependencies[package])}"
            + (f" ({len(packages[package])})" if recursive else "")
            for package in packages_sorted[: min(n, len(packages_sorted))]
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Count number of installed packages and their dependencies"
    )
    parser.add_argument(
        "-n", type=int, help="max number of most bloated packages to show", default=10
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="whether to recursively calculate number of dependencies",
    )
    args = parser.parse_args()
    asyncio.run(main(n=args.n, recursive=args.recursive))
