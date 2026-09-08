"""A web build must not be able to succeed without its Firebase configuration.

The NEXT_PUBLIC_* values are compiled into the browser bundle, so a missing one
is not a runtime error anybody sees. The build succeeds, the deploy succeeds,
the page loads, and the only symptom is that signing in silently does not
exist. That is exactly what happened: the Cloud Build config defaulted the two
Firebase substitutions to the empty string, a build was invoked without them,
and a working-looking app went live that nobody could log into.

There are two gates now, and this pins both. Cloud Build refuses a build whose
substitutions are absent, because there is no default to fall back on; and the
Dockerfile refuses one whose build arguments are empty, which covers every
other way of producing the image.

Neither gate can be checked by running the app, so they are checked by reading
the files that define them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CLOUDBUILD = ROOT / "infra" / "cloudbuild-web.yaml"
DOCKERFILE = ROOT / "apps" / "web" / "Dockerfile"

#: Every value that must be present for the bundle to be able to authenticate.
REQUIRED = [
    "NEXT_PUBLIC_API_BASE_URL",
    "NEXT_PUBLIC_FIREBASE_API_KEY",
    "NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN",
    "NEXT_PUBLIC_FIREBASE_PROJECT_ID",
]

#: The substitutions with no safe default. _API_BASE_URL and _TAG legitimately
#: have one; these two do not, because an empty key is worse than no build.
MUST_NOT_DEFAULT = ["_FIREBASE_API_KEY", "_FIREBASE_AUTH_DOMAIN"]


@pytest.fixture(scope="module")
def cloudbuild() -> str:
    return CLOUDBUILD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


class TestCloudBuildHasNoEmptyDefaults:
    def test_the_firebase_substitutions_have_no_default(self, cloudbuild):
        """The exact regression. These defaulted to "" and shipped a broken app."""
        for key in MUST_NOT_DEFAULT:
            assert f'{key}: ""' not in cloudbuild, (
                f"{key} defaults to an empty string, so a build that omits it "
                f"succeeds and produces an app nobody can sign in to"
            )
            assert f"{key}: ''" not in cloudbuild

    def test_the_substitutions_are_still_referenced(self, cloudbuild):
        """Removing the default must not mean removing the value."""
        for key in MUST_NOT_DEFAULT:
            assert f"${{{key}}}" in cloudbuild

    def test_no_firebase_value_is_committed(self, cloudbuild):
        """Making it required must not become making it hardcoded."""
        assert "AIza" not in cloudbuild
        assert ".firebaseapp.com" not in cloudbuild


class TestTheDockerfileRefusesAnEmptyConfiguration:
    def test_every_required_value_is_declared_as_a_build_argument(self, dockerfile):
        for name in REQUIRED:
            assert f"ARG {name}" in dockerfile

    def test_the_build_checks_them_before_compiling(self, dockerfile):
        """A guard placed after `pnpm build` would prove nothing."""
        assert "Refusing to build" in dockerfile
        guard = dockerfile.index("Refusing to build")
        compile_step = dockerfile.index("RUN pnpm build")
        assert guard < compile_step, "the guard must run before the bundle is built"

    def test_the_guard_covers_every_required_value(self, dockerfile):
        guard = dockerfile[dockerfile.index("missing=\"\""):dockerfile.index("RUN pnpm build")]
        for name in REQUIRED:
            assert name in guard, f"{name} is not checked before the build"

    def test_the_guard_actually_fails_the_build(self, dockerfile):
        assert "exit 1" in dockerfile

    def test_the_guard_says_how_to_fix_it(self, dockerfile):
        """An error that does not say what to pass costs the next person an hour."""
        assert "--substitutions" in dockerfile

    def test_no_firebase_value_is_baked_into_the_image(self, dockerfile):
        assert "AIza" not in dockerfile
