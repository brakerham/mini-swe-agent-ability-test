"""Credential-free task provisioning, shared by paid runs and offline smoke tests."""
import tarfile

from .core import check_process, docker_base, prepare
from .process import execute


def provision(task, folder, name, image):
    candidate = folder / "candidate"
    prepare(task, candidate)
    container = check_process(execute(["docker", "create", "--name", name, *docker_base(), image], timeout=30), "Task container creation")
    check_process(execute(["docker", "start", container], timeout=30), "Task container start")
    # Extract as uid65534: no CAP_CHOWN is available or needed.
    archive = folder / "candidate.tar"
    with tarfile.open(archive, "w") as stream:
        stream.add(candidate, arcname=".")
    try:
        check_process(execute(["docker", "exec", "-i", container, "tar", "--no-same-owner",
                               "--no-same-permissions", "-xf", "-", "-C", "/workspace"],
                              timeout=30, input_file=archive), "Task copy")
    finally:
        archive.unlink(missing_ok=True)
    return container


def export_submission(container, destination):
    check_process(execute(["docker", "stop", "--time", "1", container], timeout=20), "Task stop")
    destination.mkdir()
    check_process(execute(["docker", "cp", container + ":/workspace/.", str(destination)], timeout=30), "Submission export")
