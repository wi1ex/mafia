"""Regression tests for the agreed versions and obvious-colors rules.

The scenarios are deliberately data-driven: every row describes a real game
position that was agreed with the product owner.  When the algorithm changes,
these checks prevent an already clarified interpretation from silently
regressing.
"""

from __future__ import annotations
import unittest
from collections.abc import Iterable, Mapping

# noinspection PyProtectedMember
from ..app.services.game_scoring import (
    _night_opinion_obvious_colors,
    _normalize_action_versions,
    build_game_scoring_rules_snapshot,
    calculate_game_scoring_audit,
)


PLAYER_IDS = set(range(1, 11))


def version(claimant_id: int, *checks: tuple[int, str]) -> dict[str, object]:
    return {
        "claimant_id": claimant_id,
        "checks": [
            {"target_id": target_id, "verdict": verdict}
            for target_id, verdict in checks
        ],
    }


class VersionsObviousColorsTests(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def obvious_colors(
        *,
        actor_id: int,
        versions: list[dict[str, object]],
        black_ids: Iterable[int] = (),
        sheriff_id: int | None = None,
        sheriff_checks: Mapping[int, set[int]] | None = None,
        alive_states: Iterable[Iterable[int]] | None = None,
    ) -> dict[int, str]:
        roles = {user_id: "citizen" for user_id in PLAYER_IDS}
        for user_id in black_ids:
            roles[user_id] = "mafia"
        if sheriff_id is not None:
            roles[sheriff_id] = "sheriff"

        result = _night_opinion_obvious_colors(
            actor_id=actor_id,
            roles=roles,
            player_ids=PLAYER_IDS,
            active_versions=_normalize_action_versions(versions, PLAYER_IDS),
            sheriff_checks=sheriff_checks or {},
            alive_states=tuple(
                frozenset(state)
                for state in (alive_states or (PLAYER_IDS,))
            ),
        )
        return {user_id: color for user_id, color in result.items() if user_id != actor_id}

    def test_agreed_versions_scenarios(self) -> None:
        cases = [
            (
                "01_sheriff_private_checks",
                dict(
                    actor_id=1,
                    sheriff_id=1,
                    black_ids={6},
                    sheriff_checks={1: {4, 6}},
                    versions=[],
                ),
                {4: "red", 6: "black"},
            ),
            (
                "02_sheriff_counterclaims",
                dict(
                    actor_id=1,
                    sheriff_id=1,
                    versions=[version(2, (5, "red")), version(3, (6, "black"))],
                ),
                {2: "black", 3: "black"},
            ),
            (
                "03_checked_black_rejects_its_claim",
                dict(
                    actor_id=4,
                    versions=[version(1, (2, "red")), version(3, (4, "black"))],
                ),
                {1: "red", 2: "red", 3: "black"},
            ),
            (
                "04_outside_two_versions_has_no_certainty",
                dict(
                    actor_id=2,
                    versions=[version(1, (2, "red")), version(3, (4, "black"))],
                ),
                {},
            ),
            (
                "05_three_versions_with_a_checked_black",
                dict(
                    actor_id=4,
                    versions=[
                        version(1, (2, "red")),
                        version(3, (4, "black")),
                        version(5, (6, "black")),
                    ],
                ),
                {2: "red", 3: "black"},
            ),
            (
                "06_single_closed_version",
                dict(actor_id=7, versions=[version(1, (4, "black"), (5, "black"), (6, "black"))]),
                {1: "red", 2: "red", 3: "red", 4: "black", 5: "black", 6: "black", 8: "red", 9: "red", 10: "red"},
            ),
            (
                "07_two_closed_versions_make_outside_players_red",
                dict(
                    actor_id=7,
                    versions=[
                        version(1, (4, "black"), (5, "black"), (6, "black")),
                        version(4, (1, "black"), (2, "black"), (3, "black")),
                    ],
                ),
                {8: "red", 9: "red", 10: "red"},
            ),
            (
                "08_claim_with_four_blacks_is_false",
                dict(actor_id=6, versions=[version(1, (2, "black"), (3, "black"), (4, "black"), (5, "black"))]),
                {1: "black"},
            ),
            (
                "09_impossible_closed_version",
                dict(
                    actor_id=7,
                    versions=[
                        version(1, (4, "black"), (5, "black"), (6, "black")),
                        version(2, (3, "black")),
                    ],
                ),
                {1: "black", 2: "red", 3: "black"},
            ),
            (
                "10_two_claims_checked_actor_and_closed_third_version",
                dict(
                    actor_id=4,
                    versions=[version(1, (4, "black")), version(3, (4, "black")), version(5, (6, "black"))],
                ),
                {1: "black", 2: "red", 3: "black", 5: "red", 6: "black", 7: "red", 8: "red", 9: "red", 10: "red"},
            ),
            (
                "11_three_false_claims_close_the_black_team",
                dict(
                    actor_id=4,
                    versions=[version(1, (4, "black")), version(3, (4, "black")), version(5, (4, "black"))],
                ),
                {1: "black", 2: "red", 3: "black", 5: "black", 6: "red", 7: "red", 8: "red", 9: "red", 10: "red"},
            ),
            (
                "12_proxy_rejects_own_impossible_version",
                dict(
                    actor_id=1,
                    versions=[version(1, (2, "black"), (3, "black"), (4, "black")), version(5, (6, "black"))],
                ),
                {5: "red", 6: "black"},
            ),
            (
                "13_proxy_checked_black_uses_other_version",
                dict(actor_id=1, versions=[version(1, (2, "black")), version(3, (1, "black"))]),
                {2: "black", 3: "black"},
            ),
            (
                "14_alive_history_excludes_now_impossible_black_candidates",
                dict(
                    actor_id=8,
                    versions=[version(1, (2, "black"), (3, "black"))],
                    alive_states=[PLAYER_IDS, {1, 2, 3, 8, 9, 10}],
                ),
                {1: "red", 2: "black", 3: "black", 9: "red", 10: "red"},
            ),
            (
                "20_single_version_with_two_red_checks",
                dict(actor_id=10, versions=[version(1, (2, "red"), (3, "red"))]),
                {1: "red", 2: "red", 3: "red"},
            ),
            (
                "21_last_black_is_known_from_alive_state",
                dict(
                    actor_id=4,
                    versions=[version(1, (2, "black"))],
                    alive_states=[PLAYER_IDS, {1, 2, 3, 4}],
                ),
                {1: "red", 2: "black", 3: "red"},
            ),
            (
                "22_two_versions_with_only_red_checks",
                dict(actor_id=10, versions=[version(1, (2, "red")), version(3, (4, "red"))]),
                {},
            ),
            (
                "23_three_versions_with_only_red_checks",
                dict(
                    actor_id=10,
                    versions=[version(1, (2, "red")), version(3, (4, "red")), version(5, (6, "red"))],
                ),
                {},
            ),
            (
                "24_four_claims_make_non_claimants_red",
                dict(
                    actor_id=10,
                    versions=[version(1, (5, "red")), version(2, (6, "red")), version(3, (7, "red")), version(4, (8, "red"))],
                ),
                {5: "red", 6: "red", 7: "red", 8: "red", 9: "red"},
            ),
            (
                "25_five_claims_make_non_claimants_red",
                dict(
                    actor_id=10,
                    versions=[
                        version(1, (6, "red")),
                        version(2, (7, "red")),
                        version(3, (8, "red")),
                        version(4, (9, "red")),
                        version(5, (10, "red")),
                    ],
                ),
                {6: "red", 7: "red", 8: "red", 9: "red"},
            ),
            (
                "26_overfilled_version_and_remaining_possibilities",
                dict(
                    actor_id=8,
                    versions=[version(1, (2, "red")), version(3, (4, "black"), (5, "black")), version(6, (7, "black"))],
                ),
                {2: "red", 3: "black"},
            ),
            (
                "27_checked_black_trusts_remaining_version",
                dict(
                    actor_id=4,
                    versions=[version(1, (4, "black"), (2, "red")), version(3, (5, "black"), (2, "red"))],
                ),
                {1: "black", 2: "red", 3: "red", 5: "black"},
            ),
            (
                "28_game_continuation_rejects_three_alive_blacks",
                dict(
                    actor_id=7,
                    versions=[version(1, (2, "black"), (3, "black")), version(4, (1, "black"), (2, "black"), (3, "black"))],
                    alive_states=[PLAYER_IDS, {1, 2, 3, 7, 8, 9}],
                ),
                {1: "red", 2: "black", 3: "black", 4: "black", 5: "red", 6: "red", 8: "red", 9: "red", 10: "red"},
            ),
            (
                "32_sheriff_private_black_closes_three",
                dict(
                    actor_id=1,
                    sheriff_id=1,
                    black_ids={7},
                    sheriff_checks={1: {7}},
                    versions=[version(2, (3, "red")), version(4, (5, "black"))],
                ),
                {2: "black", 3: "red", 4: "black", 5: "red", 6: "red", 7: "black", 8: "red", 9: "red", 10: "red"},
            ),
            (
                "33_two_counterclaims_and_a_closed_version",
                dict(
                    actor_id=7,
                    versions=[version(1, (7, "black")), version(3, (7, "black")), version(5, (2, "red"), (6, "black"))],
                ),
                {1: "black", 2: "red", 3: "black", 4: "red", 5: "red", 6: "black", 8: "red", 9: "red", 10: "red"},
            ),
        ]

        for name, kwargs, expected in cases:
            with self.subTest(name=name):
                self.assertDictEqual(self.obvious_colors(**kwargs), expected)

    def test_night_opinion_uses_the_versions_snapshot_at_that_moment(self) -> None:
        first_version = [version(1, (2, "black"))]
        later_versions = [*first_version, version(3, (4, "black"))]
        roles = {user_id: "citizen" for user_id in PLAYER_IDS}
        scoring_rules = build_game_scoring_rules_snapshot()

        before_check = calculate_game_scoring_audit(
            mode="rating",
            roles={**roles, 1: "sheriff", 5: "mafia"},
            player_ids=PLAYER_IDS,
            scoring_rules=scoring_rules,
            actions=[
                {"type": "night_opinions", "opinions": {1: {5: "black"}}},
                {"type": "night_check", "actor_id": 1, "target_id": 5},
            ],
        )
        self.assertEqual([item["obvious"] for item in before_check], [False])

        before_new_claim = calculate_game_scoring_audit(
            mode="rating",
            roles=roles,
            player_ids=PLAYER_IDS,
            scoring_rules=scoring_rules,
            actions=[
                {"type": "versions", "versions": first_version},
                {"type": "night_opinions", "versions": first_version, "opinions": {7: {1: "black", 2: "black"}}},
                {"type": "versions", "versions": later_versions},
            ],
        )
        self.assertEqual([item["obvious"] for item in before_new_claim], [True, True])

        before_claim_removal = calculate_game_scoring_audit(
            mode="rating",
            roles=roles,
            player_ids=PLAYER_IDS,
            scoring_rules=scoring_rules,
            actions=[
                {"type": "versions", "versions": later_versions},
                {"type": "night_opinions", "versions": later_versions, "opinions": {7: {1: "black", 2: "black"}}},
                {"type": "versions", "versions": first_version},
            ],
        )
        self.assertEqual([item["obvious"] for item in before_claim_removal], [False, False])
