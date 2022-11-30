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


async def packages_and_dependencies(
    only_explicitly_installed: bool = False,
) -> dict[str, set[str]]:
    """
    Construct a mapping of packages -> dependencies, running the pacman calls concurrently with async
    Returns: dict mapping installed packages to sets of their dependencies

    Args:
        only_explicitly_installed: whether to only include explictly installed packages

    """
    packages_set = await packages_names(
        "e" if only_explicitly_installed else ""
    )  # omit the `e` so we get all packages and dependencies for a full tree

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
        self._observed_packages = set()

    @cache
    def calculate_all_dependencies(self, package: str) -> set[str]:
        """
        recursively calculates the number of dependencies of this package, and its children
        Args:
            package: package to calculate dependencies
        """
        dependencies = self._dependency_dict.get(package, set())
        if package in self._observed_packages:
            # dependency cycle detected, don't continue recursing
            return dependencies
        self._observed_packages.add(package)

        additional_dependencies = set().union(
            *(
                self.calculate_all_dependencies(dependency)
                for dependency in dependencies
            )
        )
        return {*dependencies, *additional_dependencies}


async def main(
    n: int = 10,
    recursive: bool = False,
    ignore: set[str] = None,
    dependency_chain_length: int = 0,
):
    """
    List number of manually installed packages and show the top N packages with the most dependencies
    Args:
        dependency_chain: number of subdependencies to show in final output
        ignore: set of packages to ignore for the calculation
        recursive: whether to calculate package dependencies recursively
        n: number of worst offenders to show
    """
    (
        packages_unfiltered,
        explicitly_installed_packages_unfiltered,
    ) = await asyncio.gather(packages_and_dependencies(not recursive), packages_names())
    ignore_set = ignore or set()

    packages = {
        package: {
            dependency for dependency in dependencies if dependency not in ignore_set
        }
        for package, dependencies in packages_unfiltered.items()
        if package not in ignore_set
    }

    explicitly_installed_packages = {
        package
        for package in explicitly_installed_packages_unfiltered
        if package not in ignore_set
    }
    print(f"total installed packages: {len(explicitly_installed_packages)}")

    if recursive:
        dependency_calcualator = DependencyCalculator(packages)
        recursive_dependencies = {
            package: dependency_calcualator.calculate_all_dependencies(package)
            for package in packages
        }
    else:
        recursive_dependencies = {
            package: dependency
            for package, dependency in packages.items()
            if package in packages
        }

    packages_sorted_unfiltered = sorted(
        recursive_dependencies.keys(),
        key=lambda package: -len(recursive_dependencies[package]),
    )
    packages_sorted = [
        package
        for package in packages_sorted_unfiltered
        if package in explicitly_installed_packages
    ]

    def format_package(package: str) -> str:
        formatted = f"{package}: {len(recursive_dependencies[package])}"
        if recursive:
            formatted += f" ({len(packages[package])})"
        return formatted

    def dependency_chain(package: str, depth: int) -> str:
        dependencies = recursive_dependencies[package]
        heaviest_dependency = next(
            (
                package
                for package in packages_sorted_unfiltered
                if package in dependencies
            ),
            None,
        )

        out = f"({format_package(package)})"
        if heaviest_dependency and depth - 1 >= 0:
            out += " -> " + dependency_chain(heaviest_dependency, depth - 1)
        return out

    print(f"top {n} packages:")
    print(
        "\n".join(
            f"  {format_package(package)}"
            + (
                "\n" f"    {dependency_chain(package, dependency_chain_length)}"
                if dependency_chain_length
                else ""
            )
            for package in packages_sorted[: min(n, len(packages_sorted))]
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Count number of installed packages and their dependencies"
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        help="max number of most bloated packages to show",
        default=10,
    )
    parser.add_argument(
        "--dependency-chain",
        type=int,
        help="number of subdependencies to show in final result (default: 0)",
        default=0,
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="whether to recursively calculate number of dependencies",
    )
    parser.add_argument(
        "-i", "--ignore", nargs="+", help="packages to ignore in the calculation"
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            n=args.number,
            recursive=args.recursive,
            ignore=set(args.ignore or set()),
            dependency_chain_length=args.dependency_chain,
        )
    )
