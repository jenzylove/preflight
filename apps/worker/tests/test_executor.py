"""Worker guarantees.

These tests run against real files produced by ffmpeg, not mocks, because the
claims being tested are claims about media. A mocked ffmpeg would let every one
of them pass while the product silently corrupted people's films.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from preflight_contracts import repairs
from preflight_worker.executor import (
    assemble_package,
    execute_step,
    output_name,
    run_job,
)
from preflight_worker.validate import verify_manifest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required to test media operations honestly",
)

PLAN = "d" * 32


@pytest.fixture(scope="module")
def master(tmp_path_factory) -> Path:
    """A short, deliberately hot and mis-flagged master."""
    path = tmp_path_factory.mktemp("fixtures") / "master.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
            "-filter_complex", "[1:a]loudnorm=I=-12:TP=-1:LRA=7[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-aspect", "4:3", "-c:a", "aac", "-ar", "48000",
            str(path),
        ],
        check=True, capture_output=True,
    )
    return path


def step(operation, step_id="s01", input_role="master", output_role="out", **parameters):
    return {
        "step_id": step_id, "operation": operation, "input_role": input_role,
        "output_role": output_role, "parameters": parameters, "depends_on": (),
    }


class TestApprovalEnforcement:
    def test_a_step_is_refused_when_the_plan_digest_does_not_match(self, master, tmp_path):
        outcome = execute_step(
            step("rewrite_container_metadata"),
            inputs={"master": master}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest="a" * 32,
        )
        assert outcome.status == "REFUSED"
        assert "approved" in outcome.error

    def test_a_step_is_refused_when_nothing_was_approved(self, master, tmp_path):
        outcome = execute_step(
            step("rewrite_container_metadata"),
            inputs={"master": master}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest="",
        )
        assert outcome.status == "REFUSED"

    def test_a_yellow_operation_is_never_executed(self, master, tmp_path):
        """Even approved, re-encoding the picture does not run automatically."""
        outcome = execute_step(
            step("reencode_video"),
            inputs={"master": master}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest=PLAN,
        )
        assert outcome.status == "REFUSED"
        assert "yellow" in outcome.error

    def test_an_uncatalogued_operation_is_refused(self, master, tmp_path):
        outcome = execute_step(
            step("delete_everything"),
            inputs={"master": master}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest=PLAN,
        )
        assert outcome.status == "REFUSED"
        assert "catalogue" in outcome.error


class TestIdempotency:
    def test_the_output_name_is_derived_from_the_plan_and_step(self):
        first = output_name(PLAN, "s01", "resize_poster", ".jpg")
        second = output_name(PLAN, "s01", "resize_poster", ".jpg")
        assert first == second

    def test_different_steps_write_to_different_names(self):
        assert output_name(PLAN, "s01", "resize_poster", ".jpg") != output_name(
            PLAN, "s02", "resize_poster", ".jpg"
        )

    def test_rerunning_a_step_produces_an_identical_output(self, master, tmp_path):
        """AC-9 at the file level: a retry overwrites, it does not accumulate."""
        args = dict(
            inputs={"master": master}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest=PLAN,
        )
        first = execute_step(step("rewrite_container_metadata"), **args)
        second = execute_step(step("rewrite_container_metadata"), **args)

        assert first.status == second.status == "SUCCEEDED"
        assert first.output_path == second.output_path
        assert first.output_sha256 == second.output_sha256
        produced = list(tmp_path.glob("*rewrite_container_metadata*"))
        assert len(produced) == 1


class TestPicturePreservation:
    def test_a_metadata_rewrite_leaves_the_picture_bit_identical(self, master, tmp_path):
        outcome = execute_step(
            step("rewrite_container_metadata", displayAspectRatio="16:9"),
            inputs={"master": master}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest=PLAN,
        )
        assert outcome.status == "SUCCEEDED"
        assert outcome.picture_preserved is True

    def test_the_original_is_never_modified(self, master, tmp_path):
        """AC-4."""
        before = repairs.sha256_file(master)
        execute_step(
            step("normalise_loudness", targetLufs=-19.5),
            inputs={"master": master}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest=PLAN,
        )
        assert repairs.sha256_file(master) == before

    def test_loudness_normalisation_moves_the_measurement_into_range(
        self, master, tmp_path
    ):
        from preflight_contracts.inspect_media import measure_loudness

        before = measure_loudness(master)["integratedLoudnessLufs"]
        outcome = execute_step(
            step("normalise_loudness", targetLufs=-19.5),
            inputs={"master": master}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest=PLAN,
        )
        assert outcome.status == "SUCCEEDED"
        after = measure_loudness(outcome.output_path)["integratedLoudnessLufs"]
        assert before > -15                      # the fixture really was hot
        assert -21.5 <= after <= -17.5           # and landed in the window


class TestDependencyHandling:
    def test_a_step_whose_dependency_failed_is_not_attempted(self, tmp_path):
        steps = [
            step("normalise_loudness", step_id="s01"),
            {**step("rewrite_container_metadata", step_id="s02"), "depends_on": ("s01",)},
        ]
        result = run_job(
            steps, inputs={}, work_dir=tmp_path,
            plan_digest=PLAN, approved_digest=PLAN,
        )
        assert result.outcomes[0].status == "FAILED"
        assert result.outcomes[1].status == "FAILED"
        assert "depends on" in result.outcomes[1].error
        assert not result.succeeded


class TestPackagingAndValidation:
    def test_a_manifest_covers_every_file_and_verifies(self, master, tmp_path):
        package = tmp_path / "package"
        assemble_package(
            outputs={}, originals={"master": master},
            destination_id="artdocfest", rule_pack_digest="abc123",
            package_dir=package,
        )
        ok, problems = verify_manifest(package)
        assert ok, problems

    def test_a_tampered_file_fails_manifest_verification(self, master, tmp_path):
        package = tmp_path / "package"
        assemble_package(
            outputs={}, originals={"master": master},
            destination_id="artdocfest", rule_pack_digest="abc123",
            package_dir=package,
        )
        target = next(p for p in package.iterdir() if p.name != "manifest.json")
        target.write_bytes(target.read_bytes() + b"tampered")

        ok, problems = verify_manifest(package)
        assert not ok
        assert any("hash" in p for p in problems)

    def test_a_file_added_after_the_manifest_is_detected(self, master, tmp_path):
        package = tmp_path / "package"
        assemble_package(
            outputs={}, originals={"master": master},
            destination_id="artdocfest", rule_pack_digest="abc123",
            package_dir=package,
        )
        (package / "smuggled.txt").write_text("not in the manifest")

        ok, problems = verify_manifest(package)
        assert not ok
        assert any("not recorded" in p for p in problems)

    def test_a_package_with_no_manifest_cannot_verify(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        ok, problems = verify_manifest(empty)
        assert not ok
        assert "no manifest" in problems[0]


class TestArchiveSafety:
    @pytest.mark.parametrize("hostile", [
        "../../etc/passwd",
        "/absolute/path",
        "C:\\Windows\\System32\\evil",
        "nested/../../escape",
    ])
    def test_traversal_names_are_rejected_not_sanitised(self, hostile):
        """A filename containing '..' is a signal, not a typo."""
        with pytest.raises(repairs.RepairError):
            repairs.safe_package_name(hostile)

    def test_a_null_byte_is_rejected(self):
        with pytest.raises(repairs.RepairError):
            repairs.safe_package_name("poster\x00.jpg")

    def test_an_ordinary_name_survives(self):
        assert repairs.safe_package_name("artdocfest_master.mp4") == "artdocfest_master.mp4"
