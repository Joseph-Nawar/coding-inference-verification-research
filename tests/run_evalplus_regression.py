"""Launch the fixed synthetic parity image and retain bounded fixture evidence."""

import argparse
import json
from pathlib import Path
import re
import resource
import subprocess
import time
import uuid


REVISIONS = (
    "e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2",
    "6eb1e199c2e370518e7bf3e8eee6322c2b23c89c",
    "26d6d00bb1fd0fa37f39c99d5290da67891d1c5e",
)
DOCKER = ["docker", "--context", "desktop-linux"]
MEMORY_BYTES = 512 * 1024 * 1024
OUTPUT_BYTES = 64 * 1024
TMPFS = "rw,nosuid,nodev,noexec,size=64m,mode=1777"


def docker(*args):
    return subprocess.run(
        [*DOCKER, *args], text=True, capture_output=True, check=True, timeout=20,
    ).stdout.strip()


def check_profile(container, image):
    host = container["HostConfig"]
    expected = {
        "NetworkMode": "none",
        "ReadonlyRootfs": True,
        "Privileged": False,
        "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges"],
        "PidsLimit": 32,
        "Memory": MEMORY_BYTES,
        "MemorySwap": MEMORY_BYTES,
        "NanoCpus": 1_000_000_000,
        "Tmpfs": {"/tmp": TMPFS},
    }
    mismatches = {key: host.get(key) for key, wanted in expected.items() if host.get(key) != wanted}
    if (mismatches or container["Mounts"] or host["Binds"] or host["Devices"]
            or host["PidMode"] or host["IpcMode"] == "host"
            or container["Config"]["User"] != "65532:65532" or container["Image"] != image):
        raise ValueError(f"Container failed containment inspection: {mismatches}")


def limit_log_file():
    resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_BYTES, OUTPUT_BYTES))


def run_fixture(image, revision, evidence_dir):
    name = f"coding-research-regression-{uuid.uuid4().hex}"
    start = time.monotonic()
    container_id = name
    try:
        container_id = docker(
            "create", "--name", name, "--platform", "linux/arm64", "--pull", "never",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", "65532:65532",
            "--pids-limit", "32", "--memory", "512m", "--memory-swap", "512m",
            "--cpus", "1", "--tmpfs", f"/tmp:{TMPFS}", "--log-driver", "none",
            image, revision,
        )
        description = docker("inspect", container_id)
        (evidence_dir / f"{revision}.inspect.json").write_text(description + "\n")
        check_profile(json.loads(description)[0], image)
        with (evidence_dir / f"{revision}.log").open("xb") as log:
            status = subprocess.run(
                [*DOCKER, "start", "--attach", container_id],
                stdout=log, stderr=subprocess.STDOUT, timeout=30, preexec_fn=limit_log_file,
            ).returncode
        container_status = docker("inspect", "--format", "{{json .State}}", container_id)
        (evidence_dir / f"{revision}.state.json").write_text(container_status + "\n")
        state = json.loads(container_status)
        if status != 0 or state["ExitCode"] != 0 or state["OOMKilled"]:
            raise RuntimeError(f"Fixture exited unsuccessfully for {revision}: {state}")
        if (evidence_dir / f"{revision}.log").stat().st_size >= OUTPUT_BYTES:
            raise RuntimeError(f"Fixture output limit reached for {revision}")
    finally:
        docker("rm", "--force", container_id)
        remaining = docker("ps", "--all", "--quiet", "--filter", f"name=^{name}$")
        if remaining:
            raise RuntimeError(f"Container cleanup failed for {name}")
    print(f"{revision}: exit=0 cleanup=verified wall_seconds={time.monotonic()-start:.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Immutable local fixture image ID")
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", args.image):
        parser.error("supply an immutable local image ID")
    arch = docker("image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", args.image)
    if arch != "linux/arm64":
        parser.error(f"unexpected fixture platform {arch}")
    args.evidence_directory.mkdir(mode=0o700)
    for revision in REVISIONS:
        run_fixture(args.image, revision, args.evidence_directory)


if __name__ == "__main__":
    main()
