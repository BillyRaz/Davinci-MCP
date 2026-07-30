from pathlib import Path

from PIL import Image

from resolve.lut.analysis import CaptureThresholds, analyze_lut, compare_captures
from resolve.lut.generator import generate_artifacts
from resolve.lut.model import GradeProfile


def save(path: Path, pixels: list[tuple[int, int, int]]) -> None:
    image = Image.new("RGB", (2, 2))
    image.putdata(pixels)
    image.save(path)


def test_lut_analysis_standard_samples_and_ramps(tmp_path: Path) -> None:
    generated = generate_artifacts(
        GradeProfile(
            name="ANALYSIS_V1",
            description="Analysis",
            cube_size=17,
            exposure_stops=0.1,
            shoulder_strength=0.1,
        ),
        tmp_path,
    )
    report = analyze_lut(Path(generated["cube_path"]))
    assert report["neutral_monotonic"]
    assert "teal" in report["standard_samples"]
    assert report["identity_distance"] > 0


def test_identical_and_brightness_change(tmp_path: Path) -> None:
    before = tmp_path / "before.png"
    same = tmp_path / "same.png"
    bright = tmp_path / "bright.png"
    pixels = [(20, 40, 60)] * 4
    save(before, pixels)
    save(same, pixels)
    save(bright, [(40, 60, 80)] * 4)
    identical = compare_captures(before, same)
    assert identical["metrics"]["hashes_equal"]
    assert identical["hard_rejections"] == ["REJECTED_VISIBLE_NOOP"]
    changed = compare_captures(before, bright)
    assert changed["metrics"]["luma_change"] > 0
    assert changed["metrics"]["changed_pixel_percentage"] == 100


def test_saturation_clipping_shadow_and_channel_cast(tmp_path: Path) -> None:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    save(
        before,
        [(50, 50, 50), (100, 100, 100), (200, 180, 160), (100, 120, 140)],
    )
    save(after, [(0, 0, 0), (255, 255, 255), (255, 100, 50), (200, 50, 20)])
    report = compare_captures(
        before,
        after,
        CaptureThresholds(
            maximum_highlight_clipping_increase=0.1,
            maximum_shadow_crush_increase=0.1,
            maximum_channel_imbalance=1,
            reject_clipping=True,
        ),
    )
    metrics = report["metrics"]
    assert metrics["highlight_clipping_increase"] > 0
    assert metrics["shadow_crush_increase"] > 0
    assert metrics["mean_saturation_change"] > 0
    assert "REJECTED_TECHNICAL_SAFETY" in report["hard_rejections"]
    assert any("imbalance" in warning for warning in report["warnings"])
