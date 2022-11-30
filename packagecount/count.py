"""Script for calculating which packages installed with pacman result in the most dependencies"""
import argparse
import asyncio


async def run(cmd: str) -> list[str]:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().split("\n")


async def packages_names(pacman_args: str = "e") -> set[str]:
    package_names = await run(f"pacman -Q{pacman_args}")
    return set(package_name.split(' ')[0] for package_name in package_names if package_name.strip())


async def package_dependencies(package: str) -> set[str]:
    pacman_info = await run(f"pacman -Qi {package}")
    info_pairs = (info_line.split(":", 1) for info_line in pacman_info if ":" in info_line)
    info_dict = {key.strip().lower(): value.strip() for key, value in info_pairs}
    return info_dict.get("depends on", "").split("  ")


async def packages_and_dependencies() -> dict[str, set[str]]:
    packages_set = await packages_names()

    async def collect_dependencies(package: str) -> tuple[str, set[str]]:
        return package, await package_dependencies(package)

    return dict(await asyncio.gather(*(collect_dependencies(package) for package in packages_set)))


async def main(n=10):
    packages = await packages_and_dependencies()
    print(f"total installed packages: {len(packages)}")

    packages_sorted = sorted(packages.keys(), key=lambda package: -len(packages[package]))
    print(f"top {n} packages:")
    print("\n".join(f"  {package}: {len(packages[package])}" for package in packages_sorted[:min(n, len(packages_sorted))]))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Count number of installed packages and their dependencies")
    parser.add_argument("-n", type=int, help="max number of most bloated packages to show", default=10)
    args = parser.parse_args()
    asyncio.run(main(n=args.n))

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
