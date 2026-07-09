from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(script: str, args: list[str]) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / script), *args]
    print("运行：", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="全量生成园区语音导览网站")
    parser.add_argument("--point", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    common = []
    if args.point:
        common.extend(["--point", args.point])
    force = ["--force"] if args.force else []
    run("01_scan_points.py", [])
    run("02_generate_ai_voice.py", common + force)
    run("03_optimize_images.py", common)
    run("04_build_site.py", common)
    run("05_generate_qrcodes.py", common)
    run("06_check_output.py", common)


if __name__ == "__main__":
    main()
