from __future__ import annotations

import json
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_wannier as preparer
import rank_wannier_bands as ranker
import wannier_windows as selector
from tests.test_prepare_wannier_integration import POSCAR


def inputs(channels, dos=None, shift=0.0):
    """Each state is (energy, Mn-d weight, Sb-p weight, other weight)."""
    blocks = {}
    for spin, rows in channels.items():
        blocks[spin] = tuple(ranker.ProcarKPoint(k + 1, (k / len(rows), 0, 0), 1 / len(rows), tuple(
            ranker.ProcarBand(n + 1, energy + shift, 0.0,
                             ((other, 0.0, d, other + d), (0.0, p, 0.0, p)))
            for n, (energy, d, p, other) in enumerate(states)))
            for k, states in enumerate(rows))
    first = next(iter(blocks.values()))
    procar = ranker.ProcarData(Path("PROCAR"), ("s", "p", "d", "tot"), len(first),
                              len(first[0].bands), 2, tuple(blocks), blocks)
    if dos is None:
        dos = {spin: [[state[0] for state in states] for states in rows]
               for spin, rows in channels.items()}
    eigenval = ranker.EigenvalData(
        Path("EIGENVAL"), len(next(iter(dos.values()))), len(next(iter(dos.values()))[0]),
        tuple(dos), {spin: {n + 1: tuple(row[n] + shift for row in rows)
                           for n in range(len(rows[0]))} for spin, rows in dos.items()})
    return procar, eigenval


class AdaptiveWindowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.poscar = Path(self.temporary.name) / "POSCAR"
        self.poscar.write_text(POSCAR)

    def select(self, channels, num_wann=2, dos=None, shift=0.0, **kwargs):
        procar, eigenval = inputs(channels, dos, shift)
        projected = ranker.project_pairs(procar, self.poscar, ["Mn", "Sb"], ["d", "p"])
        return selector.select_adaptive(procar, eigenval, projected, ["Mn:d", "Sb:p"],
                                        num_wann, shift, selector.WindowOptions(**kwargs))

    def test_exact_pairs_and_shared_elements_shells(self):
        procar, _ = inputs({"none": [[(-1, 0.2, 0.3, 0.5)]]})
        paired = ranker.project_pairs(procar, self.poscar, ["Mn", "Sb"], ["d", "p"])
        self.assertEqual(paired["none"][0][0].pair_weights, (0.2, 0.3))
        ranked = ranker.rank_paired_procar(procar, paired)
        self.assertAlmostEqual(ranked["none"][0].bz_weighted_projection, 0.5)
        repeated = ranker.project_pairs(procar, self.poscar, ["Mn", "Mn", "Sb"], ["d", "s", "d"])
        self.assertEqual(repeated["none"][0][0].pair_weights, (0.2, 0.5, 0.0))
        self.assertEqual(preparer.infer_num_wann(self.poscar, ["Mn", "Mn"], ["s", "d"]), 6)
        with self.assertRaisesRegex(ranker.PBandError, "duplicate"):
            ranker.project_pairs(procar, self.poscar, ["Mn", "mn"], ["d", "D"])
        with self.assertRaisesRegex(preparer.WannierPreparationError, "duplicate"):
            preparer.paired_projections(["Mn", "mn"], ["d", "D"])

    def test_fermi_reference_shift_invariance(self):
        channels = {"none": [[(-1, 1, 0, 0), (0, 1, 1, 0), (1, 0, 1, 0)]]}
        outer, frozen, report = self.select(channels, num_wann=3)
        self.assertEqual(outer, [-1, 1])
        self.assertEqual(frozen, [-0.9, 0.9])
        shifted = self.select(channels, num_wann=3, shift=17.12345)
        self.assertEqual(report["windows_relative"], shifted[2]["windows_relative"])
        for old, new in zip(outer + frozen, shifted[0] + shifted[1]):
            self.assertAlmostEqual(new - old, 17.12345)
        json.dumps(report, allow_nan=False)

    def test_distant_d_bands_do_not_change_selection(self):
        base = [(-1, 1, 0, 0), (1, 0, 1, 0)]
        old = self.select({"none": [base]})
        new = self.select({"none": [base + [(25, 1000, 0, 0), (40, 1000, 0, 0)]]})
        self.assertEqual(old[:2], new[:2])
        self.assertEqual(old[2]["coverage_by_pair"], new[2]["coverage_by_pair"])

    def test_equal_tail_quantiles_replace_shortest_coverage_interval(self):
        # [0, 5] holds 98.5%, but drops more than 1% from the lower tail.
        channels = {"none": [[(-15, 0.015, 0.015, 0), (0, 0.97, 0.97, 0),
                               (5, 0.015, 0.015, 0)]]}
        outer, _, report = self.select(channels, coverage=0.98)
        self.assertEqual(outer, [-15, 5])
        self.assertEqual(report["outer_selection"], "local_equal_tail_quantiles")
        self.assertEqual(report["outer_quantiles"]["envelope_relative"], [-15, 5])
        self.assertFalse(report["outer_quantiles"]["expanded_for_state_count"])

    def test_quantiles_trim_both_tails_and_round_outward(self):
        channels = {"none": [[(-15, 0.005, 0.005, 0), (-2.13, 0.495, 0.495, 0),
                               (3.11, 0.495, 0.495, 0), (20, 0.005, 0.005, 0)]]}
        outer, _, report = self.select(channels)
        self.assertEqual(outer, [-2.25, 3.25])
        quantiles = report["outer_quantiles"]
        self.assertEqual(quantiles["envelope_relative"], [-2.13, 3.11])
        self.assertEqual(quantiles["rounded_grid_relative"], outer)
        self.assertEqual(len(quantiles["intervals"]), 2)
        for pair in report["coverage_by_pair"]:
            self.assertAlmostEqual(pair["minimum"]["coverage"], 0.99)
        self.assertFalse(report["warnings"])

    def test_quantile_envelope_preserves_each_pair_and_kpoint(self):
        channels = {"none": [
            [(-8, 0.005, 0, 0), (-2, 0.495, 0, 0), (1, 0.5, 1, 0), (20, 0, 0, 1)],
            [(-10, 0, 0, 1), (0, 100, 0, 0), (4, 0, 0.001, 0), (20, 0, 0, 1)],
        ]}
        outer, _, report = self.select(channels)
        self.assertEqual(outer, [-2, 4])
        self.assertEqual(len(report["outer_quantiles"]["intervals"]), 4)

    def test_custom_coverage_sets_equal_tail_probabilities(self):
        channels = {"none": [[(-15, 0.05, 0.05, 0), (-1, 0.45, 0.45, 0),
                               (1, 0.45, 0.45, 0), (20, 0.05, 0.05, 0)]]}
        self.assertEqual(self.select(channels, coverage=0.98)[0], [-15, 20])
        outer, _, report = self.select(channels)
        self.assertEqual(outer, [-1, 1])
        low, high = report["outer_quantiles"]["probabilities"]
        self.assertAlmostEqual(low, 0.1)
        self.assertAlmostEqual(high, 0.9)

    def test_quantiles_keep_degenerate_endpoint_states(self):
        spectrum = selector.Spectrum([-15, -2, -2, 3, 20], [0, 0.005, 0.495, 0.5, 0])
        self.assertEqual(spectrum.quantile(0.01), -2)
        self.assertEqual(spectrum.quantile(0.99), 3)
        self.assertEqual(spectrum.weight(-2, 3), 1)

    def test_local_high_energy_character_can_expand_both_windows(self):
        outer, frozen, report = self.select({"none": [[(-1, 1, 0, 0), (1, 0, 1, 0), (5, 1, 0, 0)]]})
        self.assertEqual(outer, [-1, 5])
        self.assertEqual(frozen, [-0.9, 4.9])
        self.assertEqual(report["coverage_by_pair"][0]["minimum"]["coverage"], 1)

    def test_weak_pair_is_not_hidden_by_strong_pair(self):
        outer, _, _ = self.select({"none": [[(-1, 100, 0, 0), (1, 0, 0.01, 0), (4, 0, 0.09, 0)]]})
        self.assertEqual(outer, [-1, 4])

    def test_orbital_transfer_across_noncontiguous_indices(self):
        channels = {"none": [[(-1, 1, 0, 0), (0, 0, 0, 1), (1, 0, 1, 0)],
                             [(-1, 0, 1, 0), (0, 0, 0, 1), (1, 1, 0, 0)]]}
        outer, frozen, report = self.select(channels)
        self.assertEqual(outer, [-1, 1])
        self.assertIsNone(frozen)
        self.assertGreater(report["frozen_rejections"]["low_character"], 0)

    def test_dos_mesh_independently_limits_counts(self):
        channels = {"none": [[(-1, 1, 0, 0), (1, 0, 1, 0), (5, 0, 0, 1)]]}
        dos = {"none": [[-1, 1, 5], [-1, 3.1, 5]]}
        outer, _, report = self.select(channels, dos=dos)
        self.assertEqual(outer, [-1, 3.25])
        self.assertEqual(report["outer_counts"]["minimum"]["count"], 2)
        self.assertEqual(report["outer_quantiles"]["envelope_relative"], [-1, 1])
        self.assertEqual(report["outer_quantiles"]["rounded_grid_relative"], [-1, 1])
        self.assertTrue(report["outer_quantiles"]["expanded_for_state_count"])

    def test_states_just_outside_bounds_do_not_satisfy_outer_count(self):
        channels = {"none": [[(-1, 1, 0, 0), (1, 0, 1, 0)]]}
        outer, _, _ = self.select(channels, dos={"none": [[-1, 2 + 5e-10]]})
        self.assertEqual(outer, [-1, 2.25])

    def test_outer_ties_prefer_lower_lower_bound(self):
        channels = {"none": [[(0, 1, 0, 0), (0, 0, 1, 0), (1, 0, 0, 1)]]}
        outer, _, _ = self.select(channels, dos={"none": [[-2.25, 0, 2.25]]})
        self.assertEqual(outer, [-2.25, 0])

    def test_legacy_common_validation_catches_insufficient_scf_states(self):
        procar, eigenval = inputs({"none": [[(-1, 1, 0, 0), (10, 0, 1, 0)]]},
                                 dos={"none": [[-1, 1]]})
        with self.assertRaisesRegex(selector.WindowSelectionError, "SCF"):
            selector.validate_outer_counts(procar, eigenval, -2, 2, 2)

    def test_dos_degeneracy_prevents_freezing_too_many_states(self):
        channels = {"none": [[(-1, 1, 0, 0), (1, 0, 1, 0), (5, 0, 0, 1)]]}
        _, frozen, report = self.select(channels, dos={"none": [[0, 0, 0]]})
        self.assertIsNone(frozen)
        self.assertGreater(report["frozen_rejections"]["too_many_states"], 0)

    def test_spin_channels_share_window_and_each_needs_frozen_states(self):
        channels = {"up": [[(-1, 1, 0, 0), (1, 0, 1, 0)]],
                    "down": [[(4, 1, 0, 0), (4, 0, 1, 0)]]}
        outer, frozen, report = self.select(channels)
        self.assertEqual(outer, [-1, 4])
        self.assertIsNone(frozen)
        self.assertGreater(report["frozen_rejections"]["empty_spin"], 0)

    def test_margin_and_zero_total_weight_fallback(self):
        channels = {"none": [[(-1, 1, 0, 0), (1, 0, 1, 0)]]}
        self.assertIsNone(self.select(channels, frozen_margin=2)[1])
        channels["none"][0].insert(1, (0, 0, 0, 0))
        self.assertIsNone(self.select(channels)[1])

    def test_no_search_weight_fails_and_zero_pair_is_reported(self):
        with self.assertRaisesRegex(selector.WindowSelectionError, "no weight"):
            self.select({"none": [[(21, 1, 0, 0), (22, 0, 1, 0)]]})
        _, _, report = self.select({"none": [[(-1, 1, 0, 0), (1, 1, 0, 0)]]})
        self.assertIsNone(report["coverage_by_pair"][1]["minimum"])
        self.assertTrue(report["unavailable_coverage"])

    def test_search_limits_are_enforced_and_reported(self):
        channels = {"none": [[(-1, 1, 0, 0), (20, 0, 1, 0)]]}
        self.assertIn("search boundary", " ".join(self.select(channels)[2]["warnings"]))
        with self.assertRaisesRegex(selector.WindowSelectionError, "limiting state count"):
            self.select(channels, search=(-2, 2))

    def test_inclusive_degenerate_character_rejection(self):
        _, frozen, _ = self.select({"none": [[(0, 1, 0, 0), (0, 0, 0, 1), (1, 0, 1, 0)]]})
        self.assertIsNone(frozen)

    def test_options_and_fermi_validation(self):
        for kwargs in ({"search": (2, 2)}, {"search": (-1, float("inf"))},
                       {"search": (2, -2)}, {"coverage": 1}, {"coverage": float("nan")},
                       {"character_min": 1.1}, {"frozen_margin": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(selector.WindowSelectionError):
                selector.WindowOptions(**kwargs).validate()
        path = Path(self.temporary.name) / "OUTCAR"
        path.write_text("E-fermi : 1.0\nE-fermi : 2.5D+00\nE-fermi : NaN\n")
        self.assertEqual(preparer.read_fermi_energy(path), 2.5)
        path.write_text("no Fermi value")
        with self.assertRaisesRegex(preparer.WannierPreparationError, "no finite E-fermi"):
            preparer.read_fermi_energy(path)

    def test_cli_defaults_and_overrides(self):
        args = preparer.parse_args(["--elements", "Mn", "--orbitals", "d"])
        self.assertEqual(args.window_method, "adaptive")
        self.assertEqual(tuple(args.search_energy_range), (-20, 20))
        self.assertEqual(args.outer_coverage, 0.8)
        self.assertEqual(selector.WindowOptions().search, (-20, 20))
        self.assertEqual(selector.WindowOptions().coverage, 0.8)
        args = preparer.parse_args(["--elements", "Mn", "--orbitals", "d",
                                   "--window-method", "legacy", "--search-energy-range", "-1", "3",
                                   "--outer-coverage", "0.95",
                                   "--frozen-character-min", "0.8"])
        self.assertEqual(args.window_method, "legacy")
        self.assertEqual(args.search_energy_range, [-1, 3])

    def test_removed_range_and_padding_options_are_rejected(self):
        base = ["--elements", "Mn", "--orbitals", "d"]
        for obsolete in (["--target-energy-range", "-2", "2"], ["--outer-search-padding", "5"]):
            with self.subTest(obsolete=obsolete), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    preparer.parse_args(base + obsolete)
                self.assertEqual(error.exception.code, 2)

    def test_no_hidden_target_region_and_no_zero_width_outer(self):
        outer, frozen, report = self.select(
            {"none": [[(-4, 1, 0, 0), (-3, 1, 0, 0), (3, 0, 1, 0), (4, 0, 1, 0)]]},
            num_wann=4)
        self.assertEqual(outer, [-4, 4])
        self.assertEqual(frozen, [-3.9, 3.9])
        self.assertEqual(set(report["windows_relative"]), {"search", "outer", "frozen"})
        self.assertNotIn("target_counts", report)
        outer, _, _ = self.select({"none": [[(0, 1, 0, 0)]]}, num_wann=1)
        self.assertEqual(outer, [-0.25, 0])

    def test_narrow_outer_and_asymmetric_non_grid_search_endpoints(self):
        outer, frozen, _ = self.select(
            {"none": [[(-0.5, 1, 0, 0), (0, 1, 1, 0), (0.5, 0, 1, 0)]]}, num_wann=3)
        self.assertEqual(outer, [-0.5, 0.5])
        self.assertEqual(frozen, [-0.4, 0.4])
        outer, _, _ = self.select({"none": [[(-0.3, 1, 0, 0), (0.4, 0, 1, 0)]]},
                                  search=(-0.3, 0.4))
        self.assertEqual(outer, [-0.3, 0.4])

    def test_one_sided_outer_does_not_expand_to_fermi(self):
        outer, frozen, _ = self.select({"none": [[(5, 1, 0, 0), (6, 0, 1, 0)]]})
        self.assertEqual(outer, [5, 6])
        self.assertIsNone(frozen)  # The margin excludes both available states.

    def test_both_windows_can_lie_above_or_below_fermi(self):
        for low, high in ((5, 7), (-7, -5)):
            channels = {"none": [[(low, 1, 0, 0), (low + 1, 1, 1, 0),
                                    (high, 0, 1, 0)]]}
            for search in ((-20, 20), (low - 0.13, high + 0.11)):
                with self.subTest(low=low, search=search):
                    outer, frozen, report = self.select(channels, num_wann=3, search=search)
                    self.assertEqual(outer, [low, high])
                    self.assertEqual(frozen, [low + 0.1, high - 0.1])
                    shifted = self.select(channels, num_wann=3, search=search, shift=17.125)
                    self.assertEqual(report["windows_relative"], shifted[2]["windows_relative"])
                    for old, new in zip(outer + frozen, shifted[0] + shifted[1]):
                        self.assertAlmostEqual(new - old, 17.125)

    def test_frozen_can_avoid_low_character_and_excess_states_at_fermi(self):
        channels = {"none": [[(-4, 0.2, 0, 0), (-3, 0.2, 0, 0), (-2, 0.2, 0, 0),
                                (0, 0, 0, 1), (2, 0, 1, 0), (3, 0, 1, 0), (4, 0, 1, 0)]]}
        outer, frozen, report = self.select(channels, num_wann=3,
                                            dos={"none": [[-4, 0, 0, 0, 0, 2, 3]]})
        self.assertEqual(outer, [-4, 4])
        self.assertEqual(frozen, [0.1, 3.9])
        self.assertGreater(report["frozen_rejections"]["low_character"], 0)
        self.assertLessEqual(report["frozen_counts"]["maximum"]["count"], 3)

    def test_one_sided_search_endpoints_and_count_expansion(self):
        channels = {"none": [[(5.13, 1, 0, 0), (6.11, 0, 1, 0)]]}
        outer, _, report = self.select(channels, search=(5.13, 7.11),
                                       dos={"none": [[5.13, 7.11]]})
        self.assertEqual(outer, [5.13, 7.11])
        self.assertTrue(report["outer_quantiles"]["expanded_for_state_count"])
        with self.assertRaisesRegex(selector.WindowSelectionError, "limiting state count"):
            self.select(channels, search=(5.13, 7), dos={"none": [[5.13, 7.11]]})

    def test_search_may_start_or_end_at_fermi(self):
        for search in ((0, 2), (-2, 0)):
            selector.WindowOptions(search=search).validate()

    def test_outer_only_incar_and_joint_optional_bounds(self):
        text = preparer.rewrite_incar("ENCUT=520", "test", 4, 2, ["Mn:d"],
                                      preparer.WannierWindows(None, None, -2, 2),
                                      "begin kpoint_path\nG 0 0 0 X 0.5 0 0\nend kpoint_path")
        self.assertNotIn("dis_froz", text)
        self.assertIn("dis_win_min = -2", text)
        with self.assertRaises(preparer.WannierPreparationError):
            preparer.WannierWindows(None, 1, -2, 2)


if __name__ == "__main__":
    unittest.main()
