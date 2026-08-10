"""Passports.

A passport's value is entirely in its honesty. These tests exist to stop a
future change producing a passport that looks clean by omitting what went
wrong.
"""

from __future__ import annotations

from preflight_contracts.passport import (
    STANDING_LIMITATION,
    AssetLineage,
    DestinationRecord,
    build_passport,
)


def asset(role="master", transformations=None) -> AssetLineage:
    return AssetLineage(
        role=role,
        original_filename=f"{role}.mp4",
        original_sha256="a" * 64,
        derived_sha256="b" * 64 if transformations else None,
        picture_sha="c" * 32,
        picture_preserved=True if transformations else None,
        transformations=transformations or [],
    )


def destination(dest_id="artdocfest", verified=True, refusals=None) -> DestinationRecord:
    return DestinationRecord(
        destination_id=dest_id,
        rule_pack_version=1,
        rule_pack_digest="pack123",
        sources=[{"url": "https://artdocfest.com/spec", "retrievedAt": "2026-08-10"}],
        package_sha256="d" * 64,
        manifest_digest="e" * 16,
        verified=verified,
        assertions_passed=13 if verified else 11,
        assertions_total=13,
        refusals=refusals or [],
    )


def build(**overrides):
    base = dict(
        project_id="p1", project_title="A Quiet Field", version=1,
        assets=[asset(transformations=[{"operation": "normalise_loudness",
                                        "parameters": {"targetLufs": -19.5}}])],
        destinations=[destination()],
        repair_plan_digest="plan123",
        approved_at="2026-08-10T12:00:00+00:00",
    )
    base.update(overrides)
    return build_passport(**base)


class TestLimitations:
    def test_the_standing_limitation_is_always_present(self):
        """AC-11. Preflight never claims a destination will accept a delivery."""
        assert STANDING_LIMITATION in build().limitations

    def test_an_unverified_destination_is_named_in_the_limitations(self):
        passport = build(destinations=[
            destination(verified=False, refusals=["a required rule is ambiguous"])
        ])
        text = " ".join(passport.limitations)
        assert "NOT verified" in text
        assert "ambiguous" in text

    def test_assets_delivered_unchanged_are_disclosed(self):
        passport = build(assets=[asset("master"), asset("poster")])
        assert any("unchanged" in limitation for limitation in passport.limitations)

    def test_caller_supplied_limitations_are_kept(self):
        passport = build(extra_limitations=["No audio description was produced."])
        assert "No audio description was produced." in passport.limitations

    def test_limitations_survive_into_the_written_report(self):
        report = build(destinations=[destination(verified=False)]).to_report()
        assert "LIMITATIONS" in report
        assert STANDING_LIMITATION in report


class TestLineage:
    def test_a_transformed_asset_is_marked_modified(self):
        passport = build()
        assert passport.assets[0].was_modified

    def test_an_untouched_asset_is_not_marked_modified(self):
        assert not asset("poster").was_modified

    def test_the_report_shows_the_original_hash(self):
        assert "a" * 64 in build().to_report()

    def test_the_report_states_when_the_picture_was_preserved(self):
        assert "picture unchanged" in build().to_report()

    def test_the_report_names_every_transformation(self):
        assert "normalise_loudness" in build().to_report()

    def test_the_report_cites_the_destination_source(self):
        assert "https://artdocfest.com/spec" in build().to_report()


class TestDigest:
    def test_the_same_facts_produce_the_same_digest(self):
        # issued_at is excluded, so two passports over identical facts agree.
        assert build().digest() == build().digest()

    def test_changing_a_hash_changes_the_digest(self):
        changed = asset(transformations=[{"operation": "normalise_loudness"}])
        changed.original_sha256 = "f" * 64
        assert build().digest() != build(assets=[changed]).digest()

    def test_changing_verification_status_changes_the_digest(self):
        assert build().digest() != build(destinations=[destination(verified=False)]).digest()

    def test_the_digest_appears_in_the_serialised_passport(self):
        passport = build()
        assert passport.to_dict()["digest"] == passport.digest()


class TestReportReadability:
    def test_an_unverified_destination_says_so_plainly(self):
        report = build(destinations=[
            destination(verified=False, refusals=["manifest verification did not pass"])
        ]).to_report()
        assert "NOT VERIFIED" in report
        assert "manifest verification did not pass" in report

    def test_a_verified_destination_avoids_claiming_acceptance(self):
        report = build().to_report()
        assert "meets published requirements" in report
        for overclaim in ("accepted", "guaranteed", "approved by"):
            assert overclaim not in report.lower()
