"""Opt-in integration: real Docker, zero model calls, no optional dependencies."""
import os
from pathlib import Path
import shlex
import tempfile
import unittest
import uuid

from benchmark import core, environment
from benchmark.mini_adapter import ExistingDockerEnvironment


@unittest.skipUnless(os.environ.get("BENCHMARK_DOCKER_TESTS") == "1", "Set BENCHMARK_DOCKER_TESTS=1 with the task image built")
class DockerRuntimeTests(unittest.TestCase):
    def test_real_task_copy_permissions_isolation_export_and_grading(self):
        task = core.task_list()[0]
        image = core.docker_image()["id"]
        name = "swe-smoke-" + uuid.uuid4().hex[:16]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            try:
                container = environment.provision(task, folder, name, image)
                env = ExistingDockerEnvironment(container)
                def command(text):
                    return env.execute({"command": text})
                self.assertEqual(command("id -u")["output"].strip(), "65534")
                self.assertEqual(command("test -z \"${DEEPSEEK_API_KEY+x}\" && test ! -e /eval && test ! -e /var/run/docker.sock")["returncode"], 0)
                self.assertEqual(command("touch /workspace/editable && rm /workspace/editable")["returncode"], 0)
                self.assertNotEqual(command("touch /rootfs-must-stay-readonly")["returncode"], 0)
                self.assertEqual(command("grep '^CapEff:' /proc/self/status")["output"].split()[-1], "0000000000000000")
                import json
                data = json.loads(core.check_process(core.execute(["docker", "inspect", container]), "inspect"))[0]
                self.assertEqual(data["HostConfig"]["NetworkMode"], "none")
                self.assertTrue(data["HostConfig"]["ReadonlyRootfs"])
                for relative in task["allowed_paths"]:
                    source = (core.TASKS / task["id"] / "gold" / relative).read_text(encoding="utf-8")
                    script = f"from pathlib import Path; Path({relative!r}).write_text({source!r},encoding='utf-8')"
                    self.assertEqual(command("python -c " + shlex.quote(script))["returncode"], 0)
                self.assertEqual(command("python -m unittest discover -s tests -v")["returncode"], 0)
                exported = folder / "submission"
                environment.export_submission(container, exported)
                result = core.grade(task, exported, docker=True, image=image)
                self.assertTrue(result["resolved"], result)
            finally:
                core.execute(["docker", "rm", "-f", "-v", name], timeout=30)


if __name__ == "__main__":
    unittest.main()
