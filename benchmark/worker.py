"""Only this explicitly launched worker imports the optional model adapter."""
import json
from pathlib import Path
import sys
from .mini_adapter import run_agent


def main():
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = run_agent(payload["task"], payload["container_id"],
                       Path(payload["output_dir"]), payload["config"])
    Path(payload["result_path"]).write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
