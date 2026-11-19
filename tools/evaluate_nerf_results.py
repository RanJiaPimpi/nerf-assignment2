from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity


ROOT = Path(__file__).resolve().parents[1]
OBJECTS = [
    ("盆栽", "plant_360", "object_00184cc3"),
    ("草棚推车", "cart_360", "object_001cfadf"),
    ("风车", "windmill_360", "object_0046f208"),
    ("烤鸡", "roast_chicken_360", "object_004fb4d7"),
    ("红色车辆", "red_vehicle_360", "object_00c7005a"),
    ("鸭子", "duck_360", "object_00f980c0"),
    ("市场摊位", "market_stall_360", "object_05437330"),
    ("酒桶架", "barrel_rack_360", "object_0269ed15"),
    ("城堡", "castle_large_360", "object_04794e1a"),
    ("木屋", "cottage_360_retry", "object_06b9953a"),
]


def load_prediction(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def load_ground_truth(path: Path) -> np.ndarray:
    rgba = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255.0
    alpha = rgba[..., 3:4]
    return rgba[..., :3] * alpha + (1.0 - alpha)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results = []
    for name, experiment, dataset in OBJECTS:
        frame_mse = []
        frame_ssim = []
        for index in range(40):
            prediction = load_prediction(
                ROOT / "logs" / experiment / "testset_200000" / f"{index:03d}.png"
            )
            ground_truth = load_ground_truth(
                ROOT / "data" / "nerf_synthetic" / dataset / "test" / f"r_{index:03d}.png"
            )
            frame_mse.append(float(np.mean((prediction - ground_truth) ** 2)))
            frame_ssim.append(
                float(
                    structural_similarity(
                        ground_truth,
                        prediction,
                        data_range=1.0,
                        channel_axis=2,
                    )
                )
            )

        mse = float(np.mean(frame_mse))
        results.append(
            {
                "name": name,
                "experiment": experiment,
                "dataset": dataset,
                "checkpoint": 200000,
                "test_frames": 40,
                "psnr_db": float(-10.0 * np.log10(mse)),
                "ssim": float(np.mean(frame_ssim)),
                "lpips": None,
            }
        )

    summary = {
        "definition": {
            "psnr": "PSNR from the MSE over all pixels in the 40-frame test set",
            "ssim": "Mean of per-frame RGB SSIM values",
            "background": "RGBA ground truth composited on white",
            "lpips": "Not computed because the local evaluation environment has no PyTorch or LPIPS package",
        },
        "objects": results,
        "mean": {
            "psnr_db": float(np.mean([item["psnr_db"] for item in results])),
            "ssim": float(np.mean([item["ssim"] for item in results])),
            "lpips": None,
        },
    }

    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
