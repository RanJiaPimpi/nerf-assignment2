"""Run tools/sfm_pipeline.py for every object dataset with progress heartbeats."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("data/nerf_synthetic"))
    parser.add_argument("--output-root", type=Path, default=Path("outputs/sfm"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pipeline = Path(__file__).with_name("sfm_pipeline.py")
    datasets = sorted(path.name for path in args.data_root.glob("object_*") if path.is_dir())
    results: dict[str, dict[str, object]] = {}

    for index, dataset in enumerate(datasets, start=1):
        statistics_path = args.output_root / dataset / "statistics.json"
        if statistics_path.exists() and not args.force:
            statistics = json.loads(statistics_path.read_text(encoding="utf-8"))
            results[dataset] = {"status": "skipped_complete", **statistics}
            print(f"[{index}/{len(datasets)}] {dataset}: already complete", flush=True)
            continue

        output_dir = args.output_root / dataset
        log_dir = args.output_root / "_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{dataset}.log"
        command = [
            sys.executable,
            str(pipeline),
            "--dataset",
            dataset,
            "--data-root",
            str(args.data_root),
            "--output-root",
            str(args.output_root),
        ]
        if output_dir.exists():
            command.append("--force")
        print(f"[{index}/{len(datasets)}] {dataset}: starting", flush=True)
        started = time.monotonic()
        with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
            process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
            while process.poll() is None:
                time.sleep(5)
                elapsed = time.monotonic() - started
                if int(elapsed) % 20 < 5:
                    print(f"[{index}/{len(datasets)}] {dataset}: {elapsed:.0f}s elapsed", flush=True)
        elapsed = time.monotonic() - started
        if process.returncode == 0 and statistics_path.exists():
            statistics = json.loads(statistics_path.read_text(encoding="utf-8"))
            results[dataset] = {"status": "complete", **statistics}
            print(
                f"[{index}/{len(datasets)}] {dataset}: complete in {elapsed:.1f}s, "
                f"registered {statistics['registered_images']}/{statistics['input_images']}",
                flush=True,
            )
        else:
            results[dataset] = {
                "status": "failed",
                "returncode": process.returncode,
                "log": str(log_path),
            }
            print(f"[{index}/{len(datasets)}] {dataset}: failed; see {log_path}", flush=True)

    args.output_root.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    completed = sum(result["status"] in {"complete", "skipped_complete"} for result in results.values())
    print(f"SfM complete for {completed}/{len(datasets)} datasets. Summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
