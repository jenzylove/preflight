"""Regressions for bugs that only appeared in the deployed system.

Every one of these passed its unit tests and failed in production, because
each was a property of how the pieces are wired rather than of any piece. They
are pinned here so the wiring cannot quietly come apart again.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from preflight_contracts.normalise import collapse_alternatives, deduplicate_conflicts
from preflight_contracts.plan import _subtitle_target
from preflight_contracts.rules import (
    AssetType,
    Confidence,
    Operator,
    Rule,
    Severity,
)

ROOT = Path(__file__).resolve().parents[3]


def rule(field_name, operator, value, rid="r", asset=AssetType.VIDEO,
         severity=Severity.REQUIRED) -> Rule:
    return Rule(rid, asset, field_name, operator, value, severity, "ev", Confidence.HIGH)


class TestMediaStaysOutOfTheApi:
    """The API must never grow a media toolchain.

    It measured nothing in production because its image has no ffmpeg — which
    was the architecture working. The fix moved measurement to the worker; the
    risk is someone later "fixing" it by adding ffmpeg to the lean container,
    which would put a media decoder in the service that holds auth and routing.
    """

    @staticmethod
    def _instructions(path: Path) -> str:
        """The Dockerfile with comments stripped.

        The comment on the API image explains why it has no ffmpeg, so a naive
        substring search finds the word and fails on the documentation.
        """
        return chr(10).join(
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        ).lower()

    def test_api_image_installs_no_media_toolchain(self):
        instructions = self._instructions(ROOT / "apps" / "api" / "Dockerfile")
        assert "ffmpeg" not in instructions
        assert "apt-get install" not in instructions

    def test_worker_image_carries_ffmpeg(self):
        assert "ffmpeg" in self._instructions(ROOT / "apps" / "worker" / "Dockerfile")

    def test_api_does_not_import_the_media_inspector(self):
        """Measurement is requested from the worker, never performed in-process."""
        api = ROOT / "apps" / "api" / "preflight_api"
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in api.rglob("*.py")
            if "inspect_media" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], offenders


class TestWorkerDoesNotDependOnTheApi:
    """The worker needs the schema, not the API's routers, auth or providers.

    It crashed on every job because the ORM lived inside the API package, which
    the worker image does not carry. Copying the API in would have fixed the
    import and put auth code inside the one container that opens customer media.
    """

    def test_worker_imports_nothing_from_the_api(self):
        worker = ROOT / "apps" / "worker" / "preflight_worker"
        offenders = []
        for path in worker.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                    "preflight_api"
                ):
                    offenders.append(f"{path.name}:{node.lineno}")
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("preflight_api"):
                            offenders.append(f"{path.name}:{node.lineno}")
        assert offenders == [], offenders

    def test_the_schema_lives_in_the_shared_package(self):
        from preflight_contracts.models import Base, Package, Project

        assert Project.__tablename__ == "projects"
        assert Package.__tablename__ == "packages"
        assert len(Base.metadata.tables) >= 20


class TestApprovalStaysBoundToTheDigest:
    """Approval was unbindable because clients sent step ids without a digest.

    The digest is the whole consent mechanism: it is what changes when the plan
    changes. A client that omits it is asking to approve anything.
    """

    def test_the_browser_client_sends_the_plan_digest(self):
        client = (ROOT / "apps" / "web" / "lib" / "api.ts").read_text(encoding="utf-8")
        assert "plan_digest: planDigest" in client
        assert "approved_step_ids: stepIds" in client

    def test_the_endpoint_still_compares_digests(self):
        router = (
            ROOT / "apps" / "api" / "preflight_api" / "preflight" / "router.py"
        ).read_text(encoding="utf-8")
        assert "payload.plan_digest != plan_row.digest" in router

    def test_a_changed_plan_produces_a_different_digest(self):
        from preflight_contracts.plan import Plan, Safety, Step

        def plan_with(target: float) -> Plan:
            return Plan(steps=[Step(
                step_id="s01", operation="normalise_loudness", safety=Safety.GREEN,
                destination_id="d", input_role="master", output_role="out",
                parameters={"targetLufs": target}, resolves=("r1",),
            )])

        assert plan_with(-19.5).digest() != plan_with(-23.0).digest()


class TestSubtitleTargetIsNeverInferredFromAProhibition:
    """The worker was asked to write "xml, png, mxf" as a subtitle format.

    The planner derived the target by stripping a prefix off a human-readable
    requirement. Against "not one of srt, sub, xml" that reads the forbidden
    list as a destination.
    """

    @pytest.mark.parametrize("expected", [
        "not one of srt, sub, xml",
        "not one of sub, srt, xml, png, mxf",
        "neq srt",
    ])
    def test_a_negative_requirement_names_no_target(self, expected):
        assert _subtitle_target(expected) is None

    @pytest.mark.parametrize("expected", [
        "one of xml, png, mxf",
        "eq xml",
        "eq dfxp",
    ])
    def test_an_unwritable_format_is_not_a_target(self, expected):
        assert _subtitle_target(expected) is None

    @pytest.mark.parametrize("expected,want", [
        ("eq srt", "srt"),
        ("eq vtt", "vtt"),
        ("one of srt, vtt", "srt"),
        ("one of xml, vtt", "vtt"),
    ])
    def test_a_positive_requirement_names_its_target(self, expected, want):
        assert _subtitle_target(expected) == want

    def test_no_conversion_step_is_planned_without_a_target(self):
        from preflight_contracts.compare import Assertion, Result
        from preflight_contracts.plan import build_plan

        assertion = Assertion(
            rule_id="r1", destination_id="berlinale",
            asset_type=AssetType.SUBTITLE, field_name="format",
            expected="not one of srt, sub, xml", measured="srt",
            result=Result.REPAIRABLE, severity=Severity.REQUIRED,
            source_evidence_id="ev", repair_operation="convert_subtitles",
        )
        plan = build_plan({"berlinale": [assertion]})

        assert plan.steps == []
        assert len(plan.unresolved) == 1
        assert "will not guess" in plan.unresolved[0]["reason"]


class TestAlternativesAreNotContradictions:
    """Flattened delivery tiers blocked every package.

    Extraction reads a specification table row by row, so a menu of resolutions
    became a demand that a file be 1280 and 2048 and 4096 wide at once.
    """

    def test_exclusive_same_field_requirements_become_one_choice(self):
        group = [
            rule("widthPx", Operator.EQ, 1280, "a"),
            rule("widthPx", Operator.EQ, 1920, "b"),
            rule("widthPx", Operator.EQ, 4096, "c"),
        ]
        collapsed, notes = collapse_alternatives(group)

        assert len(collapsed) == 1
        assert collapsed[0].operator is Operator.IN
        assert set(collapsed[0].value) == {1280, 1920, 4096}
        assert notes[0]["collapsedFrom"] == 3

    def test_disjoint_windows_become_alternative_ranges(self):
        group = [
            rule("bitrateBps", Operator.BETWEEN, [20e6, 30e6], "a"),
            rule("bitrateBps", Operator.BETWEEN, [90e6, 120e6], "b"),
        ]
        collapsed, _ = collapse_alternatives(group)
        assert collapsed[0].operator is Operator.ANY_OF_RANGES
        assert len(collapsed[0].value) == 2

    def test_overlapping_windows_are_left_as_constraint(self):
        """Overlapping ranges can both hold, so they narrow rather than offer.

        A file at 22 Mbps satisfies both 15-25 and 20-30. Merging them into
        15-30 would widen what is acceptable and admit files neither source
        allows.
        """
        group = [
            rule("bitrateBps", Operator.BETWEEN, [15e6, 25e6], "a"),
            rule("bitrateBps", Operator.BETWEEN, [20e6, 30e6], "b"),
        ]
        collapsed, notes = collapse_alternatives(group)
        assert len(collapsed) == 2
        assert notes == []

    def test_compatible_requirements_are_left_alone(self):
        """Rules that can all hold are constraint, not choice."""
        group = [
            rule("frameRate", Operator.IN, [24, 25, 30], "a"),
            rule("frameRate", Operator.IN, [24, 25], "b"),
        ]
        collapsed, notes = collapse_alternatives(group)
        assert len(collapsed) == 2
        assert notes == []

    def test_recommendations_are_never_collapsed(self):
        group = [
            rule("widthPx", Operator.EQ, 1280, "a", severity=Severity.RECOMMENDED),
            rule("widthPx", Operator.EQ, 1920, "b", severity=Severity.RECOMMENDED),
        ]
        collapsed, _ = collapse_alternatives(group)
        assert len(collapsed) == 2

    def test_an_alternative_range_accepts_any_of_its_windows(self):
        from preflight_contracts.compare import Result, evaluate

        alternatives = rule(
            "bitrateBps", Operator.ANY_OF_RANGES, [[20e6, 30e6], [90e6, 120e6]]
        )
        assert evaluate(alternatives, {"bitrateBps": 25e6}, "d").result is Result.PASS
        assert evaluate(alternatives, {"bitrateBps": 100e6}, "d").result is Result.PASS
        assert evaluate(alternatives, {"bitrateBps": 8e6}, "d").result is not Result.PASS


class TestConflictNoise:
    def test_the_same_disagreement_is_reported_once(self):
        same = [
            {"assetType": "subtitle", "field": "format", "strength": "hard",
             "destinations": ["a", "b"], "requirements": ["x", "y"]},
            {"assetType": "subtitle", "field": "format", "strength": "hard",
             "destinations": ["a", "b"], "requirements": ["p", "q"]},
        ]
        out = deduplicate_conflicts(same)
        assert len(out) == 1
        assert out[0]["occurrences"] == 2

    def test_distinct_disagreements_all_survive(self):
        distinct = [
            {"assetType": "subtitle", "field": "format", "strength": "hard",
             "destinations": ["a", "b"], "requirements": ["x", "y"]},
            {"assetType": "video", "field": "codec", "strength": "hard",
             "destinations": ["a", "b"], "requirements": ["x", "y"]},
        ]
        assert len(deduplicate_conflicts(distinct)) == 2

    def test_hard_conflicts_are_reported_before_soft_ones(self):
        mixed = [
            {"assetType": "video", "field": "bitrateBps", "strength": "soft",
             "destinations": ["a", "b"], "requirements": ["x", "y"]},
            {"assetType": "subtitle", "field": "burnedIn", "strength": "hard",
             "destinations": ["a", "b"], "requirements": ["x", "y"]},
        ]
        assert deduplicate_conflicts(mixed)[0]["strength"] == "hard"
