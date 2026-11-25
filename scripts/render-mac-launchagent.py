"""Generate the per-user launchd job for the Mac Mini test server."""
from __future__ import annotations

import argparse
import plistlib
from pathlib import Path

LABEL = "pro.netcraze.chuzhoe-mesto.test"


def render(project: Path, home: Path) -> bytes:
    project = project.resolve()
    home = home.resolve()
    logs = project / "runtime-data" / "logs"
    return plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": ["/bin/bash", str(project / "scripts" / "start-site-mac.sh")],
            "WorkingDirectory": str(project),
            "EnvironmentVariables": {
                "HOME": str(home),
                "PATH": f"{home}/tools/node-v22.23.5-darwin-x64/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                "CHUZHOE_LAUNCHD": "1",
                "PYTHONUNBUFFERED": "1",
            },
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 30,
            "StandardOutPath": str(logs / "site.out.log"),
            "StandardErrorPath": str(logs / "site.err.log"),
        },
        sort_keys=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_bytes(render(args.project, args.home))
