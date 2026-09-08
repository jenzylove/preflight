"""Researching a destination must not invent authority.

Runtime research is the first path where a destination Preflight has never
seen can create binding requirements. Everything protecting that rests on one
decision: which host actually belongs to the destination. Get it wrong and a
blog post becomes a mandatory rule that blocks somebody's delivery, or worse,
passes one that should have failed.

The existing trust model does the rest - tier comes from the URL, tier D
cannot create a mandatory rule - but it can only work if the destination's own
domain is identified honestly, and if "we could not identify one" is an answer
the code is willing to give.
"""

from __future__ import annotations

from dataclasses import dataclass

from preflight_api.destinations.research import (
    AGGREGATORS,
    guess_official_domain,
    slugify,
)


@dataclass
class FakeSource:
    url: str


def sources(*urls: str) -> list[FakeSource]:
    return [FakeSource(url=u) for u in urls]


class TestIdentifyingTheDestinationsOwnDomain:
    def test_the_festivals_own_site_is_found(self):
        found = guess_official_domain(
            "Sundance Film Festival",
            sources(
                "https://www.sundance.org/wp-content/uploads/specs.pdf",
                "https://filmmakermagazine.com/how-to-deliver",
                "https://www.sundance.org/festivals/",
            ),
        )
        assert found == "sundance.org"

    def test_an_aggregator_is_never_taken_for_the_destination(self):
        """FilmFreeway lists thousands of festivals and speaks for none."""
        found = guess_official_domain(
            "Some Small Festival",
            sources(
                "https://filmfreeway.com/somesmallfestival",
                "https://filmfreeway.com/somesmallfestival/details",
            ),
        )
        assert found is None

    def test_nothing_recognisable_yields_nothing(self):
        """The honest answer when no result looks like the destination."""
        found = guess_official_domain(
            "Cannes Film Festival",
            sources(
                "https://randomblog.example/cannes-tips",
                "https://anotherblog.example/how-to-submit",
            ),
        )
        assert found is None

    def test_generic_words_alone_cannot_match(self):
        """'Film' and 'festival' match half the web and identify nobody."""
        found = guess_official_domain(
            "Film Festival",
            sources("https://festival.example/specs", "https://film.example/x"),
        )
        assert found is None

    def test_the_most_corroborated_host_wins(self):
        found = guess_official_domain(
            "Berlinale",
            sources(
                "https://www.berlinale.de/en/specs.html",
                "https://www.berlinale.de/en/entry.html",
                "https://berlinale-fan.example/guide",
            ),
        )
        assert found == "berlinale.de"

    def test_a_www_prefix_is_not_a_different_host(self):
        assert guess_official_domain(
            "Artdocfest", sources("https://www.artdocfest.com/en/tech")
        ) == "artdocfest.com"

    def test_known_aggregators_are_listed_not_guessed_at(self):
        for host in ("filmfreeway.com", "wikipedia.org", "imdb.com"):
            assert host in AGGREGATORS


class TestSlugs:
    def test_a_name_becomes_a_usable_slug(self):
        assert slugify("Sundance Film Festival") == "sundance-film-festival"

    def test_punctuation_and_case_do_not_survive(self):
        assert slugify("  Cannes/Film  Festival! ") == "cannes-film-festival"

    def test_a_slug_is_never_empty(self):
        """An empty slug would collide with every other empty slug."""
        assert slugify("!!!") == "destination"

    def test_a_slug_is_bounded(self):
        assert len(slugify("x" * 500)) <= 60
