"""Read shacl-py's Git commit from its installed Python package metadata."""

import json
from importlib.metadata import PackageNotFoundError, distribution


def installed_commit():
    try:
        origin = distribution("shacl-py").read_text("direct_url.json")
    except PackageNotFoundError:
        return ""
    vcs = json.loads(origin or "{}").get("vcs_info", {})
    return vcs.get("commit_id", "") if vcs.get("vcs") == "git" else ""


if __name__ == "__main__":
    print(installed_commit())
