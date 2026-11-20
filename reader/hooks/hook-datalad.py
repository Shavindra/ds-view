# DataLad constructs its public API by importing command suites at runtime.
from PyInstaller.utils.hooks import collect_submodules


def runtime_module(name):
    return not any(
        part in {"test", "tests", "benchmarks"} or part.startswith("test_")
        for part in name.split(".")
    )


hiddenimports = [
    module
    for package in (
        "datalad",
        "datalad_metalad",
        "datalad_deprecated",
        "dataladmetadatamodel",
    )
    for module in collect_submodules(package, filter=runtime_module)
]
