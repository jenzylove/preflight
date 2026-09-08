"""Every explanation must describe the thing it is actually about.

Production told a filmmaker that correcting the number of audio channels would
re-encode the picture. It said the same about the audio codec, the sample rate
and the audio bitrate, because one sentence was hardcoded for every requirement
Preflight declines to fix on its own.

That is not a harmless simplification. The explanation is the whole argument
for why Preflight refuses to act, and an explanation that is obviously wrong
about audio invites the reader to disbelieve the ones about picture too.

These tests pin the property: an explanation may only talk about the picture
when the picture is what would change.
"""

from __future__ import annotations

import pytest
from preflight_contracts.compare import (
    GREEN_REASONS,
    GREEN_REPAIRABLE,
    YELLOW_REASONS,
    Result,
    evaluate,
)
from preflight_contracts.rules import (
    AssetType,
    Confidence,
    Operator,
    Rule,
    Severity,
)

#: Wording that is only ever true of the image.
PICTURE_WORDS = ("picture", "image", "frame", "visual")

#: Fields where the picture genuinely is what changes.
PICTURE_FIELDS = {
    (AssetType.VIDEO, "bitrateBps"),
    (AssetType.VIDEO, "widthPx"),
    (AssetType.VIDEO, "heightPx"),
    (AssetType.VIDEO, "codec"),
    (AssetType.VIDEO, "profile"),
}


def _rule(asset_type: AssetType, field: str, value="x") -> Rule:
    return Rule(
        rule_id=f"r_{asset_type.value}_{field}",
        asset_type=asset_type,
        field_name=field,
        operator=Operator.EQ,
        value=value,
        severity=Severity.REQUIRED,
        confidence=Confidence.HIGH,
        source_evidence_id="ev",
    )


class TestNothingClaimsThePictureChangesWhenItDoesNot:
    @pytest.mark.parametrize(
        "field",
        ["channels", "codec", "sampleRateHz", "bitrateBps"],
    )
    def test_an_audio_requirement_never_blames_the_picture(self, field):
        """The exact regression a real user reported on audio channels."""
        reason = YELLOW_REASONS[(AssetType.AUDIO, field)]
        lowered = reason.lower()
        for word in PICTURE_WORDS:
            assert word not in lowered, (
                f"audio.{field} is explained with {word!r}: {reason!r}"
            )

    def test_audio_channels_explains_what_actually_happens(self):
        reason = YELLOW_REASONS[(AssetType.AUDIO, "channels")].lower()
        assert "mix" in reason

    def test_a_picture_requirement_may_say_so(self):
        """The rule is accuracy, not squeamishness about the word."""
        for key in PICTURE_FIELDS:
            reason = YELLOW_REASONS[key].lower()
            assert any(w in reason for w in PICTURE_WORDS), key

    def test_every_declined_field_has_its_own_explanation(self):
        """One shared sentence is how this went wrong in the first place."""
        reasons = list(YELLOW_REASONS.values())
        audio = [YELLOW_REASONS[k] for k in YELLOW_REASONS if k[0] is AssetType.AUDIO]
        video = [YELLOW_REASONS[k] for k in YELLOW_REASONS if k[0] is AssetType.VIDEO]
        assert reasons, "no declined fields are explained"
        # Audio and video must not share a single sentence between them.
        assert not (set(audio) & set(video))

    def test_every_declined_field_says_something(self):
        for key, reason in YELLOW_REASONS.items():
            assert len(reason.strip()) > 30, key


class TestSafeRepairsExplainTheRightThing:
    def test_a_subtitle_repair_does_not_reassure_about_the_picture(self):
        """It never touched the picture, so saying so is noise, not comfort."""
        reason = GREEN_REASONS["convert_subtitles"].lower()
        assert "picture" not in reason
        assert "subtitle" in reason

    def test_a_metadata_repair_does_not_reassure_about_the_picture(self):
        assert "picture" not in GREEN_REASONS["normalise_metadata"].lower()

    def test_a_package_naming_repair_does_not_reassure_about_the_picture(self):
        assert "picture" not in GREEN_REASONS["rename_and_layout"].lower()

    def test_repairs_that_do_touch_the_file_still_reassure(self):
        """Where the picture is copied rather than re-encoded, say it."""
        for operation in ("normalise_loudness", "rewrite_container_metadata"):
            assert "picture" in GREEN_REASONS[operation].lower()

    def test_every_green_operation_is_explained(self):
        for operation in set(GREEN_REPAIRABLE.values()):
            assert operation in GREEN_REASONS, f"{operation} has no explanation"


class TestTheExplanationReachesTheAssertion:
    def test_an_audio_channel_mismatch_is_explained_in_audio_terms(self):
        assertion = evaluate(
            _rule(AssetType.AUDIO, "channels", 6),
            {"channels": 2},
            "sundance",
        )
        assert assertion.result is Result.REVIEW_REQUIRED
        assert "picture" not in assertion.explanation.lower()
        assert "mix" in assertion.explanation.lower()

    def test_a_video_codec_mismatch_may_mention_the_picture(self):
        assertion = evaluate(
            _rule(AssetType.VIDEO, "codec", "prores"),
            {"codec": "h264"},
            "sundance",
        )
        assert assertion.result is Result.REVIEW_REQUIRED
        assert "picture" in assertion.explanation.lower()

    def test_a_subtitle_conversion_is_explained_in_subtitle_terms(self):
        assertion = evaluate(
            _rule(AssetType.SUBTITLE, "format", "srt"),
            {"format": "vtt"},
            "sundance",
        )
        assert assertion.result is Result.REPAIRABLE
        assert "picture" not in assertion.explanation.lower()
