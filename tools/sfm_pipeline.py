"""Run a reproducible image-to-pose SfM pipeline for the synthetic object datasets.

The GLB-derived camera poses are never provided to SfM. They are used only after
reconstruction to resolve SfM's similarity-transform gauge and report pose error.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import pycolmap
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset folder name, e.g. object_000f88bb")
    parser.add_argument("--data-root", type=Path, default=Path("data/nerf_synthetic"))
    parser.add_argument("--output-root", type=Path, default=Path("outputs/sfm"))
    parser.add_argument("--max-images", type=int, default=0, help="Optional debugging limit")
    parser.add_argument("--force", action="store_true", help="Replace this pipeline's existing output")
    parser.add_argument(
        "--pairing",
        choices=("exhaustive", "turntable"),
        default="exhaustive",
        help="Pair all images, or only nearby views in the known turntable capture order",
    )
    parser.add_argument("--num-match-visualizations", type=int, default=6)
    return parser.parse_args()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def prepare_masks(image_paths: list[Path], mask_root: Path) -> None:
    mask_root.mkdir(parents=True, exist_ok=True)
    kernel = np.ones((3, 3), np.uint8)
    for image_path in image_paths:
        rgba = np.asarray(Image.open(image_path).convert("RGBA"))
        mask = np.where(rgba[..., 3] >= 32, 255, 0).astype(np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        # COLMAP appends .png to the complete source filename.
        cv2.imwrite(str(mask_root / f"{image_path.name}.png"), mask)


def write_turntable_pairs(image_paths: list[Path], output_path: Path, views_per_ring: int = 24) -> None:
    """Write local image pairs without using camera poses.

    The renderer stores one 24-view azimuth ring after another. Restricting matching
    to nearby capture positions avoids false loop closures on repetitive objects.
    """
    pairs: list[str] = []
    for first_index, first_path in enumerate(image_paths):
        first_ring, first_azimuth = divmod(first_index, views_per_ring)
        for second_index in range(first_index + 1, len(image_paths)):
            second_ring, second_azimuth = divmod(second_index, views_per_ring)
            ring_delta = abs(first_ring - second_ring)
            raw_azimuth_delta = abs(first_azimuth - second_azimuth)
            azimuth_delta = min(raw_azimuth_delta, views_per_ring - raw_azimuth_delta)
            is_local = (
                (ring_delta == 0 and azimuth_delta <= 3)
                or (ring_delta == 1 and azimuth_delta <= 2)
                or (ring_delta == 2 and azimuth_delta <= 1)
            )
            if is_local:
                pairs.append(f"{first_path.name} {image_paths[second_index].name}")
    output_path.write_text("\n".join(pairs) + "\n", encoding="utf-8")


def umeyama_similarity(source: np.ndarray, target: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Return scale, rotation, translation mapping source points to target points."""
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("Expected two N x 3 point arrays")
    source_mean = source.mean(axis=0)
    target_mean = target.mean(axis=0)
    source_centered = source - source_mean
    target_centered = target - target_mean
    covariance = target_centered.T @ source_centered / source.shape[0]
    u, singular_values, vt = np.linalg.svd(covariance)
    sign = np.ones(3)
    if np.linalg.det(u @ vt) < 0:
        sign[-1] = -1
    rotation = u @ np.diag(sign) @ vt
    variance = np.sum(source_centered**2) / source.shape[0]
    scale = float(np.sum(singular_values * sign) / variance)
    translation = target_mean - scale * (rotation @ source_mean)
    return scale, rotation, translation


def rotation_error_degrees(reference: np.ndarray, estimate: np.ndarray) -> float:
    cosine = (np.trace(reference.T @ estimate) - 1.0) * 0.5
    return math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))


def alpha_composite_for_display(path: Path, background: int = 28) -> np.ndarray:
    rgba = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32)
    alpha = rgba[..., 3:4] / 255.0
    rgb = rgba[..., :3] * alpha + background * (1.0 - alpha)
    return cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)


def draw_match_visualization(
    image1_path: Path,
    image2_path: Path,
    keypoints1: np.ndarray,
    keypoints2: np.ndarray,
    matches: np.ndarray,
    output_path: Path,
    max_lines: int = 160,
) -> None:
    left = alpha_composite_for_display(image1_path)
    right = alpha_composite_for_display(image2_path)
    height = max(left.shape[0], right.shape[0])
    canvas = np.full((height, left.shape[1] + right.shape[1], 3), 24, np.uint8)
    canvas[: left.shape[0], : left.shape[1]] = left
    canvas[: right.shape[0], left.shape[1] :] = right

    if len(matches) > max_lines:
        indices = np.linspace(0, len(matches) - 1, max_lines).astype(int)
        matches = matches[indices]
    rng = np.random.default_rng(2026)
    for index1, index2 in matches:
        p1 = tuple(np.rint(keypoints1[int(index1), :2]).astype(int))
        p2_raw = np.rint(keypoints2[int(index2), :2]).astype(int)
        p2 = (int(p2_raw[0] + left.shape[1]), int(p2_raw[1]))
        color = tuple(int(value) for value in rng.integers(64, 256, size=3))
        cv2.line(canvas, p1, p2, color, 1, cv2.LINE_AA)
        cv2.circle(canvas, p1, 2, color, -1, cv2.LINE_AA)
        cv2.circle(canvas, p2, 2, color, -1, cv2.LINE_AA)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)


def export_match_results(
    database_path: Path,
    image_root: Path,
    output_dir: Path,
    num_visualizations: int,
) -> tuple[dict[str, int], list[dict[str, object]]]:
    visualizations: list[dict[str, object]] = []
    with pycolmap.Database.open(database_path) as database:
        images = {int(image.image_id): image for image in database.read_all_images()}
        pair_ids, geometries = database.read_two_view_geometries()
        ranked = sorted(
            zip(pair_ids, geometries),
            key=lambda item: len(item[1].inlier_matches),
            reverse=True,
        )
        verified = [(pair_id, geometry) for pair_id, geometry in ranked if len(geometry.inlier_matches) > 0]
        if verified:
            chosen_indices = np.linspace(0, min(len(verified) - 1, max(num_visualizations * 10, 1)), num_visualizations).astype(int)
            chosen = [verified[int(index)] for index in sorted(set(chosen_indices))]
        else:
            chosen = []

        for output_index, (pair_id, geometry) in enumerate(chosen):
            image_id1, image_id2 = pycolmap.pair_id_to_image_pair(int(pair_id))
            image1 = images[int(image_id1)]
            image2 = images[int(image_id2)]
            keypoints1 = database.read_keypoints(int(image_id1))
            keypoints2 = database.read_keypoints(int(image_id2))
            filename = f"match_{output_index:02d}_{Path(image1.name).stem}_{Path(image2.name).stem}.png"
            draw_match_visualization(
                image_root / image1.name,
                image_root / image2.name,
                keypoints1,
                keypoints2,
                np.asarray(geometry.inlier_matches),
                output_dir / filename,
            )
            visualizations.append(
                {
                    "file": filename,
                    "image1": image1.name,
                    "image2": image2.name,
                    "inliers": int(len(geometry.inlier_matches)),
                }
            )

        counts = {
            "database_images": int(database.num_images()),
            "keypoints": int(database.num_keypoints()),
            "raw_matches": int(database.num_matches()),
            "matched_pairs": int(database.num_matched_image_pairs()),
            "verified_pairs": int(database.num_verified_image_pairs()),
            "verified_inlier_matches": int(database.num_inlier_matches()),
        }
    return counts, visualizations


def align_and_export_poses(
    reconstruction: pycolmap.Reconstruction,
    gt_transforms_path: Path,
    output_path: Path,
) -> dict[str, object]:
    gt_document = json.loads(gt_transforms_path.read_text(encoding="utf-8"))
    gt_by_name = {
        Path(frame["file_path"]).name + ".png": np.asarray(frame["transform_matrix"], dtype=np.float64)
        for frame in gt_document["frames"]
    }

    correspondences: list[tuple[str, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
    camera_axis_conversion = np.diag([1.0, -1.0, -1.0])
    for image_id in reconstruction.reg_image_ids():
        image = reconstruction.image(image_id)
        if image.name not in gt_by_name:
            continue
        gt_c2w = gt_by_name[image.name]
        estimated_c2w = np.asarray(image.cam_from_world().inverse().matrix(), dtype=np.float64)
        estimated_rotation_blender = estimated_c2w[:3, :3] @ camera_axis_conversion
        correspondences.append(
            (
                image.name,
                estimated_c2w[:3, 3],
                gt_c2w[:3, 3],
                estimated_rotation_blender,
                gt_c2w[:3, :3],
            )
        )
    if len(correspondences) < 3:
        raise RuntimeError("Fewer than three reconstructed cameras overlap ground truth")

    estimated_centers = np.stack([item[1] for item in correspondences])
    gt_centers = np.stack([item[2] for item in correspondences])
    scale, world_rotation, translation = umeyama_similarity(estimated_centers, gt_centers)

    aligned_frames = []
    center_errors = []
    rotation_errors = []
    for name, estimated_center, gt_center, estimated_rotation, gt_rotation in correspondences:
        aligned_center = scale * (world_rotation @ estimated_center) + translation
        aligned_rotation = world_rotation @ estimated_rotation
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = aligned_rotation
        matrix[:3, 3] = aligned_center
        aligned_frames.append(
            {
                "file_path": f"./train/{Path(name).stem}",
                "rotation": 0.0,
                "transform_matrix": matrix.tolist(),
            }
        )
        center_errors.append(float(np.linalg.norm(aligned_center - gt_center)))
        rotation_errors.append(rotation_error_degrees(gt_rotation, aligned_rotation))

    camera = next(iter(reconstruction.cameras.values()))
    camera_angle_x = 2.0 * math.atan(camera.width / (2.0 * camera.focal_length_x))
    aligned_frames.sort(key=lambda frame: frame["file_path"])
    write_json(output_path, {"camera_angle_x": camera_angle_x, "frames": aligned_frames})

    center_errors_array = np.asarray(center_errors)
    rotation_errors_array = np.asarray(rotation_errors)
    return {
        "registered_with_ground_truth": len(correspondences),
        "similarity_scale": scale,
        "camera_center_rmse": float(np.sqrt(np.mean(center_errors_array**2))),
        "camera_center_median_error": float(np.median(center_errors_array)),
        "rotation_mean_error_degrees": float(np.mean(rotation_errors_array)),
        "rotation_median_error_degrees": float(np.median(rotation_errors_array)),
        "estimated_camera_angle_x": camera_angle_x,
        "estimated_focal_length_x": float(camera.focal_length_x),
        "estimated_focal_length_y": float(camera.focal_length_y),
    }


def run_pipeline(args: argparse.Namespace) -> None:
    dataset_root = args.data_root / args.dataset
    image_root = dataset_root / "train"
    gt_transforms_path = dataset_root / "transforms_train.json"
    output_root = args.output_root / args.dataset
    database_path = output_root / "database.db"
    masks_root = output_root / "masks"
    sparse_root = output_root / "sparse"
    matches_root = output_root / "matches"

    if not dataset_root.exists():
        raise FileNotFoundError(dataset_root)
    image_paths = sorted(image_root.glob("*.png"))
    if args.max_images > 0:
        image_paths = image_paths[: args.max_images]
    if len(image_paths) < 3:
        raise RuntimeError("SfM needs at least three images")

    if output_root.exists():
        if not args.force:
            raise FileExistsError(f"Output exists; pass --force to replace it: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    timings: dict[str, float] = {}
    start = time.perf_counter()
    prepare_masks(image_paths, masks_root)
    timings["prepare_masks_seconds"] = time.perf_counter() - start

    reader_options = pycolmap.ImageReaderOptions()
    reader_options.camera_model = "PINHOLE"
    reader_options.mask_path = masks_root
    reader_options.default_focal_length_factor = 1.1

    extraction_options = pycolmap.FeatureExtractionOptions()
    extraction_options.max_image_size = 512
    extraction_options.num_threads = -1
    extraction_options.use_gpu = False
    extraction_options.sift.max_num_features = 8192
    extraction_options.sift.peak_threshold = 0.003

    start = time.perf_counter()
    pycolmap.extract_features(
        database_path=database_path,
        image_path=image_root,
        image_names=[path.name for path in image_paths],
        camera_mode=pycolmap.CameraMode.SINGLE,
        reader_options=reader_options,
        extraction_options=extraction_options,
        device=pycolmap.Device.cpu,
    )
    timings["feature_extraction_seconds"] = time.perf_counter() - start

    matching_options = pycolmap.FeatureMatchingOptions()
    matching_options.num_threads = -1
    matching_options.use_gpu = False
    matching_options.guided_matching = True
    matching_options.sift.max_ratio = 0.85
    verification_options = pycolmap.TwoViewGeometryOptions()
    verification_options.min_num_inliers = 15
    verification_options.ransac.max_error = 3.0

    start = time.perf_counter()
    if args.pairing == "turntable":
        pairs_path = output_root / "turntable_pairs.txt"
        write_turntable_pairs(image_paths, pairs_path)
        pairing_options = pycolmap.ImportedPairingOptions()
        pairing_options.match_list_path = pairs_path
        pairing_options.block_size = 50
        pycolmap.match_image_pairs(
            database_path=database_path,
            matching_options=matching_options,
            pairing_options=pairing_options,
            verification_options=verification_options,
            device=pycolmap.Device.cpu,
        )
    else:
        pairing_options = pycolmap.ExhaustivePairingOptions()
        pairing_options.block_size = 50
        pycolmap.match_exhaustive(
            database_path=database_path,
            matching_options=matching_options,
            pairing_options=pairing_options,
            verification_options=verification_options,
            device=pycolmap.Device.cpu,
        )
    timings["matching_seconds"] = time.perf_counter() - start

    pipeline_options = pycolmap.IncrementalPipelineOptions()
    pipeline_options.multiple_models = False
    pipeline_options.min_model_size = 10
    pipeline_options.mapper.init_min_num_inliers = 50
    pipeline_options.mapper.init_min_tri_angle = 8.0
    pipeline_options.mapper.abs_pose_min_num_inliers = 20
    pipeline_options.mapper.abs_pose_min_inlier_ratio = 0.15
    pipeline_options.mapper.max_reg_trials = 5

    start = time.perf_counter()
    reconstructions = pycolmap.incremental_mapping(
        database_path=database_path,
        image_path=image_root,
        output_path=sparse_root,
        options=pipeline_options,
    )
    timings["incremental_mapping_seconds"] = time.perf_counter() - start
    if not reconstructions:
        raise RuntimeError("SfM produced no reconstruction")
    reconstruction = max(reconstructions.values(), key=lambda item: item.num_reg_images())
    model_path = sparse_root / "best"
    text_model_path = model_path / "text"
    model_path.mkdir(parents=True, exist_ok=True)
    text_model_path.mkdir(parents=True, exist_ok=True)
    reconstruction.write(model_path)
    reconstruction.write_text(text_model_path)
    reconstruction.export_PLY(output_root / "sparse_points.ply")

    database_counts, visualizations = export_match_results(
        database_path, image_root, matches_root, args.num_match_visualizations
    )
    pose_metrics = align_and_export_poses(
        reconstruction,
        gt_transforms_path,
        output_root / "transforms_sfm_train.json",
    )
    shutil.copy2(output_root / "transforms_sfm_train.json", dataset_root / "transforms_sfm_train.json")

    statistics = {
        "dataset": args.dataset,
        "pairing": args.pairing,
        "input_images": len(image_paths),
        **database_counts,
        "registered_images": int(reconstruction.num_reg_images()),
        "sparse_points": int(reconstruction.num_points3D()),
        "observations": int(reconstruction.compute_num_observations()),
        "mean_track_length": float(reconstruction.compute_mean_track_length()),
        "mean_observations_per_registered_image": float(reconstruction.compute_mean_observations_per_reg_image()),
        "mean_reprojection_error": float(reconstruction.compute_mean_reprojection_error()),
        "pose_metrics_after_similarity_alignment": pose_metrics,
        "match_visualizations": visualizations,
        "timings": timings,
        "software": {"pycolmap": pycolmap.__version__, "opencv": cv2.__version__},
    }
    write_json(output_root / "statistics.json", statistics)
    print(json.dumps(statistics, indent=2))


if __name__ == "__main__":
    run_pipeline(parse_args())
