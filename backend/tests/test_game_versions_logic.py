"""Regression tests for the agreed versions and obvious-colors rules.

The scenarios are deliberately data-driven: every row describes a real game
position that was agreed with the product owner.  When the algorithm changes,
these checks prevent an already clarified interpretation from silently
regressing.
"""

from __future__ import annotations
import unittest
from collections.abc import Iterable, Mapping

try:
    # noinspection PyProtectedMember
    from app.services.game_scoring import (
        _night_opinion_obvious_colors,
        _normalize_action_versions,
        build_game_scoring_rules_snapshot,
        calculate_game_scoring_audit,
    )
except ModuleNotFoundError:  # PyCharm may run this file as backend.tests.*.
    # noinspection PyProtectedMember
    from app.services.game_scoring import (
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

    def test_late_game_agreed_scenarios(self) -> None:
        seven_alive_states = [PLAYER_IDS, set(range(1, 8))]
        six_alive_states = [*seven_alive_states, set(range(1, 7))]
        five_alive_states = [*six_alive_states, set(range(1, 6))]
        cases = [
            (
                "35_six_players_two_checked_blacks",
                dict(
                    actor_id=4,
                    versions=[version(1, (2, "black"), (3, "black"))],
                    alive_states=six_alive_states,
                ),
                {1: "red", 2: "black", 3: "black", 5: "red", 6: "red"},
            ),
            (
                "36_six_players_one_checked_black",
                dict(
                    actor_id=4,
                    versions=[version(1, (2, "black"))],
                    alive_states=six_alive_states,
                ),
                {1: "red", 2: "black"},
            ),
            (
                "37_five_players_two_checked_blacks",
                dict(
                    actor_id=4,
                    versions=[version(1, (2, "black"), (3, "black"))],
                    alive_states=five_alive_states,
                ),
                {1: "red", 2: "black", 3: "black", 5: "red"},
            ),
            (
                "38_five_players_impossible_first_version",
                dict(
                    actor_id=5,
                    versions=[version(1, (2, "black"), (3, "black")), version(4, (1, "black"))],
                    alive_states=five_alive_states,
                ),
                {1: "black", 4: "red"},
            ),
            (
                "39_five_players_two_possible_versions",
                dict(
                    actor_id=5,
                    versions=[version(1, (2, "black")), version(3, (4, "black"))],
                    alive_states=five_alive_states,
                ),
                {},
            ),
            (
                "40_two_false_claims_force_remaining_living_red",
                dict(
                    actor_id=5,
                    versions=[version(1, (2, "black"), (3, "black")), version(4, (5, "black"))],
                    alive_states=five_alive_states,
                ),
                {1: "black", 2: "red", 3: "red", 4: "black"},
            ),
            (
                "41_three_false_claims_close_the_team",
                dict(
                    actor_id=2,
                    versions=[version(1, (2, "black")), version(3, (4, "black")), version(5, (2, "black"))],
                    alive_states=five_alive_states,
                ),
                {1: "black", 3: "black", 4: "red", 5: "black"},
            ),
            (
                "42_three_false_claims_close_the_team_at_six",
                dict(
                    actor_id=2,
                    versions=[version(1, (2, "black")), version(3, (2, "black")), version(4, (5, "black"))],
                    alive_states=six_alive_states,
                ),
                {1: "black", 3: "black", 4: "black", 5: "red", 6: "red"},
            ),
            (
                "43_seven_players_two_possible_versions",
                dict(
                    actor_id=6,
                    versions=[version(1, (2, "black"), (3, "black")), version(4, (5, "black"))],
                    alive_states=seven_alive_states,
                ),
                {},
            ),
            (
                "44_three_closed_worlds_have_no_external_certainty",
                dict(
                    actor_id=7,
                    versions=[version(1, (2, "black")), version(3, (4, "black")), version(5, (6, "black"))],
                    alive_states=seven_alive_states,
                ),
                {},
            ),
            (
                "45_checked_black_excludes_own_version",
                dict(
                    actor_id=6,
                    versions=[version(1, (2, "black")), version(3, (4, "black")), version(5, (6, "black"))],
                    alive_states=seven_alive_states,
                ),
                {5: "black", 7: "red"},
            ),
            (
                "46_sheriff_check_and_counterclaim_at_six",
                dict(
                    actor_id=1,
                    sheriff_id=1,
                    black_ids={2},
                    sheriff_checks={1: {2}},
                    versions=[version(1, (3, "red")), version(4, (5, "black"))],
                    alive_states=six_alive_states,
                ),
                {2: "black", 3: "red", 4: "black", 5: "red", 6: "red"},
            ),
            (
                "47_sheriff_known_black_team_at_six",
                dict(
                    actor_id=1,
                    sheriff_id=1,
                    black_ids={2},
                    sheriff_checks={1: {2}},
                    versions=[version(3, (4, "black")), version(5, (6, "red"))],
                    alive_states=six_alive_states,
                ),
                {2: "black", 3: "black", 4: "red", 5: "black", 6: "red"},
            ),
            (
                "48_proxy_rejects_own_overfilled_version",
                dict(
                    actor_id=3,
                    versions=[version(1, (2, "red"), (4, "black")), version(3, (5, "black"), (6, "black"), (7, "black"))],
                    alive_states=seven_alive_states,
                ),
                {1: "red", 2: "red", 4: "black"},
            ),
            (
                "49_proxy_keeps_own_possible_version",
                dict(
                    actor_id=3,
                    versions=[version(1, (2, "red"), (4, "black")), version(3, (5, "black"))],
                    alive_states=seven_alive_states,
                ),
                {},
            ),
            (
                "50_dead_author_version_becomes_impossible",
                dict(
                    actor_id=6,
                    versions=[version(1, (2, "black"), (3, "black")), version(4, (5, "black"))],
                    alive_states=[PLAYER_IDS, set(range(1, 8)), set(range(2, 8))],
                ),
                {4: "red", 5: "black"},
            ),
            (
                "51_dead_author_does_not_create_certainty",
                dict(
                    actor_id=4,
                    versions=[version(1, (2, "black")), version(7, (3, "black"))],
                    alive_states=six_alive_states,
                ),
                {},
            ),
            (
                "52_two_false_claims_at_six_force_third_black_to_be_dead",
                dict(
                    actor_id=2,
                    versions=[version(1, (2, "black")), version(3, (2, "black"))],
                    alive_states=six_alive_states,
                ),
                {1: "black", 3: "black", 4: "red", 5: "red", 6: "red"},
            ),
            (
                "53_two_false_claims_at_seven_leave_a_live_black_possible",
                dict(
                    actor_id=2,
                    versions=[version(1, (2, "black")), version(3, (2, "black"))],
                    alive_states=seven_alive_states,
                ),
                {1: "black", 3: "black"},
            ),
            (
                "54_sheriff_check_overrides_four_claims_default",
                dict(
                    actor_id=5,
                    sheriff_id=5,
                    black_ids={6},
                    sheriff_checks={5: {6}},
                    versions=[
                        version(1, (4, "red")),
                        version(2, (4, "black")),
                        version(3, (6, "red")),
                        version(4, (6, "black")),
                    ],
                    alive_states=six_alive_states,
                ),
                {6: "black"},
            ),
        ]

        for name, kwargs, expected in cases:
            with self.subTest(name=name):
                current_table_ids = set(kwargs["alive_states"][-1])
                actual = {
                    user_id: color
                    for user_id, color in self.obvious_colors(**kwargs).items()
                    if user_id in current_table_ids
                }
                self.assertDictEqual(actual, expected)

    def test_late_multi_version_and_sheriff_capacity_scenarios(self) -> None:
        four_alive_states = [PLAYER_IDS, {4, 5, 6, 7}]
        five_first_players_alive_states = [PLAYER_IDS, set(range(1, 6))]
        five_sheriff_alive_states = [PLAYER_IDS, {4, 5, 6, 7, 8}]
        overflow_alive_states = [PLAYER_IDS, {1, 4, 6, 7, 8}]
        cases = [
            (
                "55_two_dead_authors_at_four_players",
                dict(
                    actor_id=6,
                    versions=[version(1, (4, "black")), version(2, (5, "black"))],
                    alive_states=four_alive_states,
                ),
                {7: "red"},
            ),
            (
                "56_one_dead_author_at_four_players",
                dict(
                    actor_id=6,
                    versions=[version(1, (4, "black"))],
                    alive_states=four_alive_states,
                ),
                {4: "black", 5: "red", 7: "red"},
            ),
            (
                "57_checked_black_at_five_uses_last_possible_version",
                dict(
                    actor_id=2,
                    versions=[version(1, (2, "black")), version(3, (4, "black")), version(5, (1, "black"))],
                    alive_states=five_first_players_alive_states,
                ),
                {1: "black", 3: "black", 4: "red", 5: "red"},
            ),
            (
                "58_other_checked_black_at_five_uses_last_possible_version",
                dict(
                    actor_id=4,
                    versions=[version(1, (2, "black")), version(3, (4, "black")), version(5, (1, "black"))],
                    alive_states=five_first_players_alive_states,
                ),
                {1: "black", 2: "red", 3: "black", 5: "red"},
            ),
            (
                "59_checked_black_rejects_version_at_five",
                dict(
                    actor_id=3,
                    versions=[version(1, (2, "red"), (3, "black")), version(4, (5, "black"))],
                    alive_states=five_first_players_alive_states,
                ),
                {1: "black", 2: "red", 4: "red", 5: "black"},
            ),
            (
                "60_four_claims_with_dead_authors",
                dict(
                    actor_id=5,
                    versions=[
                        version(1, (4, "red")),
                        version(2, (5, "black")),
                        version(3, (6, "red")),
                        version(4, (7, "black")),
                    ],
                    alive_states=four_alive_states,
                ),
                {6: "red", 7: "red"},
            ),
            (
                "61_sheriff_three_black_checks_make_counterclaims_red",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    black_ids={1, 2, 3},
                    sheriff_checks={4: {1, 2, 3}},
                    versions=[version(5, (7, "black")), version(6, (8, "red"))],
                    alive_states=five_sheriff_alive_states,
                ),
                {5: "red", 6: "red", 7: "red", 8: "red"},
            ),
            (
                "62_sheriff_two_black_checks_and_one_counterclaim",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    black_ids={1, 2},
                    sheriff_checks={4: {1, 2}},
                    versions=[version(5, (7, "black"))],
                    alive_states=five_sheriff_alive_states,
                ),
                {5: "black", 6: "red", 7: "red", 8: "red"},
            ),
            (
                "63_sheriff_two_black_checks_and_two_counterclaims",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    black_ids={1, 2},
                    sheriff_checks={4: {1, 2}},
                    versions=[version(5, (7, "black")), version(6, (8, "red"))],
                    alive_states=five_sheriff_alive_states,
                ),
                {7: "red", 8: "red"},
            ),
            (
                "64_sheriff_one_black_check_and_two_counterclaims",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    black_ids={1},
                    sheriff_checks={4: {1}},
                    versions=[version(5, (7, "black")), version(6, (8, "red"))],
                    alive_states=five_sheriff_alive_states,
                ),
                {5: "black", 6: "black", 7: "red", 8: "red"},
            ),
            (
                "65_sheriff_one_black_check_and_three_counterclaims",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    black_ids={1},
                    sheriff_checks={4: {1}},
                    versions=[version(5, (8, "red")), version(6, (8, "red")), version(7, (8, "red"))],
                    alive_states=five_sheriff_alive_states,
                ),
                {8: "red"},
            ),
            (
                "66_sheriff_without_black_checks_and_three_counterclaims",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    versions=[version(5, (8, "red")), version(6, (8, "red")), version(7, (8, "red"))],
                    alive_states=five_sheriff_alive_states,
                ),
                {5: "black", 6: "black", 7: "black", 8: "red"},
            ),
            (
                "67_sheriff_without_black_checks_and_four_counterclaims",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    versions=[
                        version(5, (8, "red")),
                        version(6, (8, "red")),
                        version(7, (8, "red")),
                        version(8, (7, "red")),
                    ],
                    alive_states=five_sheriff_alive_states,
                ),
                {},
            ),
            (
                "68_sheriff_red_check_of_counterclaim_author",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    black_ids={1, 2},
                    sheriff_checks={4: {1, 2, 5}},
                    versions=[version(5, (7, "black")), version(6, (8, "red"))],
                    alive_states=five_sheriff_alive_states,
                ),
                {5: "red", 6: "black", 7: "red", 8: "red"},
            ),
            (
                "69_sheriff_black_check_of_counterclaim_author",
                dict(
                    actor_id=4,
                    sheriff_id=4,
                    black_ids={1, 2, 5},
                    sheriff_checks={4: {1, 2, 5}},
                    versions=[version(5, (7, "black")), version(6, (8, "red"))],
                    alive_states=five_sheriff_alive_states,
                ),
                {5: "black", 6: "red", 7: "red", 8: "red"},
            ),
            (
                "70_true_sheriff_with_publicly_overfilled_version",
                dict(
                    actor_id=1,
                    sheriff_id=1,
                    black_ids={2, 3, 5},
                    sheriff_checks={1: {2, 3, 5}},
                    versions=[version(1, (2, "black"), (3, "black"), (5, "black")), version(4, (6, "black"))],
                    alive_states=overflow_alive_states,
                ),
                {4: "red", 6: "red", 7: "red", 8: "red"},
            ),
            (
                "71_checked_red_player_sees_both_claims_as_false",
                dict(
                    actor_id=6,
                    versions=[version(1, (2, "black"), (3, "black"), (5, "black")), version(4, (6, "black"))],
                    alive_states=overflow_alive_states,
                ),
                {1: "black", 4: "black", 7: "red", 8: "red"},
            ),
            (
                "72_external_player_rejects_overfilled_sheriff_version",
                dict(
                    actor_id=7,
                    versions=[version(1, (2, "black"), (3, "black"), (5, "black")), version(4, (6, "black"))],
                    alive_states=overflow_alive_states,
                ),
                {1: "black", 4: "red", 6: "black", 8: "red"},
            ),
        ]

        for name, kwargs, expected in cases:
            with self.subTest(name=name):
                current_table_ids = set(kwargs["alive_states"][-1])
                actual = {
                    user_id: color
                    for user_id, color in self.obvious_colors(**kwargs).items()
                    if user_id in current_table_ids
                }
                self.assertDictEqual(actual, expected)

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
