"""Bounded, orbital-driven window proposals from existing VASP outputs.

PAW weights are qualitative character estimates, not Wannier projectabilities.
All selection is performed relative to one SCF Fermi reference.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass

import rank_wannier_bands as ranker


class WindowSelectionError(ValueError):
    """A proposed model or its input data cannot satisfy window constraints."""


@dataclass(frozen=True)
class WindowOptions:
    search: tuple[float, float] = (-20.0, 20.0)
    coverage: float = 0.8
    character_min: float = 0.70
    frozen_margin: float = 0.1

    def validate(self) -> None:
        if (len(self.search) != 2 or not all(map(math.isfinite, self.search))
                or not self.search[0] < self.search[1]):
            raise WindowSelectionError("--search-energy-range requires finite MIN < MAX")
        if not math.isfinite(self.coverage) or not 0 < self.coverage < 1:
            raise WindowSelectionError("--outer-coverage must be finite and strictly between 0 and 1")
        if not math.isfinite(self.character_min) or not 0 <= self.character_min <= 1:
            raise WindowSelectionError("--frozen-character-min must be finite and in [0, 1]")
        if not math.isfinite(self.frozen_margin) or self.frozen_margin < 0:
            raise WindowSelectionError("--frozen-margin must be finite and nonnegative")


def _grid(start: float, end: float, direction: int = 1) -> list[float]:
    """Quarter-eV steps, with exact endpoints, independent of absolute E_F."""
    steps = math.floor(abs(end - start) / 0.25)
    return sorted({start + direction * 0.25 * i for i in range(steps + 1)} | {end})


class Spectrum:
    """Sorted energies and prefix sums for repeated interval queries."""

    def __init__(self, energies, weights=None):
        if weights is None:
            weights = [1.0] * len(energies)
        ordered = sorted(zip(energies, weights))
        self.energies = [energy for energy, _ in ordered]
        if not all(math.isfinite(value) for row in ordered for value in row):
            raise WindowSelectionError("non-finite energy or projection weight")
        self.prefix = [0.0]
        for _, weight in ordered:
            self.prefix.append(self.prefix[-1] + weight)

    def indices(self, low, high):
        # Do not count states outside the inclusive bounds, even very close ones.
        return bisect_left(self.energies, low), bisect_right(self.energies, high)

    def count(self, low, high):
        left, right = self.indices(low, high)
        return right - left

    def weight(self, low, high):
        left, right = self.indices(low, high)
        return max(0.0, self.prefix[right] - self.prefix[left])

    def quantile(self, fraction):
        """First energy whose cumulative weight reaches the requested fraction.

        Use the discrete weighted CDF, without interpolation or smearing.
        Call only for a positive-weight spectrum and 0 < fraction < 1.
        """
        index = bisect_left(self.prefix, fraction * self.prefix[-1]) - 1
        return self.energies[max(0, index)]


def energy_meshes(procar: ranker.ProcarData, eigenval: ranker.EigenvalData, fermi: float = 0.0):
    """Return independent per-k-point spectra; never join the two meshes."""
    meshes = []
    for spin in procar.spin_channels:
        for kp in procar.kpoints[spin]:
            meshes.append(({"source": "SCF", "spin": spin, "kpoint": kp.kpoint_index},
                           Spectrum([band.energy - fermi for band in kp.bands])))
    for spin in eigenval.spin_channels:
        for k in range(eigenval.nkpoints):
            meshes.append(({"source": "DOS", "spin": spin, "kpoint": k + 1},
                           Spectrum([values[k] - fermi
                                     for values in eigenval.energies[spin].values()])))
    return meshes


def count_summary(meshes, low, high):
    counts = [{**location, "count": spectrum.count(low, high)}
              for location, spectrum in meshes]
    return {"minimum": min(counts, key=lambda item: item["count"]),
            "maximum": max(counts, key=lambda item: item["count"])}


def validate_outer_counts(procar, eigenval, low, high, num_wann):
    summary = count_summary(energy_meshes(procar, eigenval), low, high)
    if summary["minimum"]["count"] < num_wann:
        raise WindowSelectionError(
            f"outer window has fewer than NUM_WANN={num_wann} states: {summary['minimum']}")
    return summary


def select_adaptive(procar: ranker.ProcarData, eigenval: ranker.EigenvalData,
                    projected: dict[str, tuple[tuple[ranker.PairedState, ...], ...]],
                    labels: list[str] | tuple[str, ...], num_wann: int, fermi: float,
                    options: WindowOptions):
    """Return absolute (outer, optional frozen) intervals and diagnostics."""
    options.validate()
    if not math.isfinite(fermi) or num_wann <= 0:
        raise WindowSelectionError("finite Fermi energy and positive NUM_WANN are required")
    if procar.spin_channels != eigenval.spin_channels:
        raise WindowSelectionError("SCF and DOS spin channels differ")
    search = options.search
    meshes = energy_meshes(procar, eigenval, fermi)
    distributions = []
    unavailable = []
    bad_states = []
    objective_energies, objective_weights = [], []
    spin_energies = {spin: [] for spin in procar.spin_channels}
    requested_weight = 0.0
    for spin, blocks in projected.items():
        weight_sum = math.fsum(kp.weight for kp in procar.kpoints[spin])
        if weight_sum <= 0:
            raise WindowSelectionError(f"nonpositive SCF integration weight for spin {spin}")
        for k, states in enumerate(blocks):
            kp = procar.kpoints[spin][k]
            # Remove distant bands before summing to preserve NBANDS independence.
            local = [state for state in states
                     if search[0] <= state.energy - fermi <= search[1]]
            energies = [state.energy - fermi for state in local]
            location = {"spin": spin, "kpoint": kp.kpoint_index}
            for pair, label in enumerate(labels):
                spectrum = Spectrum(energies, [state.pair_weights[pair] for state in local])
                total = spectrum.weight(*search)
                entry = {**location, "pair": label}
                if total > 0:
                    distributions.append((entry, spectrum, total))
                else:
                    unavailable.append(entry)
            for state in local:
                energy = state.energy - fermi
                weight = math.fsum(state.pair_weights)
                requested_weight += weight
                spin_energies[spin].append(energy)
                objective_energies.append(energy)
                objective_weights.append(weight * kp.weight / weight_sum)
                fraction = weight / state.total_weight if state.total_weight > 0 else None
                if fraction is None or fraction < options.character_min:
                    bad_states.append({**location, "band": state.band_index,
                                       "energy_relative": energy,
                                       "target_character": fraction})
    if requested_weight <= 0:
        raise WindowSelectionError("requested orbital set has no weight in the search energy interval")

    tail_fraction = (1.0 - options.coverage) / 2.0
    quantile_intervals = [
        {**location, "lower_relative": spectrum.quantile(tail_fraction),
         "upper_relative": spectrum.quantile(1.0 - tail_fraction)}
        for location, spectrum, _ in distributions
    ]
    quantile_envelope = (min(row["lower_relative"] for row in quantile_intervals),
                         max(row["upper_relative"] for row in quantile_intervals))
    # Keep the E_F-relative quarter-eV grid, but allow both boundaries on
    # either side of E_F. Count checks can expand the envelope, never trim it.
    boundaries = sorted({search[0], search[1]} | {
        i * 0.25 for i in range(math.ceil(search[0] / 0.25),
                               math.floor(search[1] / 0.25) + 1)})
    lowers = [a for a in boundaries if a <= quantile_envelope[0]]
    uppers = [b for b in boundaries if b >= quantile_envelope[1]]
    initial_outer = (max(lowers), min(uppers))
    candidates = sorted(((a, b) for a in lowers for b in uppers if a < b),
                        key=lambda ab: (round(ab[1] - ab[0], 10),
                                        round(abs(ab[0] + ab[1]), 10), ab[0]))
    outer = None
    for a, b in candidates:
        if any(spectrum.count(a, b) < num_wann for _, spectrum in meshes):
            continue
        outer = (a, b)
        break
    if outer is None:
        limiting = count_summary(meshes, *search)["minimum"]
        raise WindowSelectionError(
            f"no feasible outer window within E_F-relative search region {search}; "
            f"NUM_WANN={num_wann}, limiting state count={limiting}. "
            "Review the orbital model, available bands, or --search-energy-range.")

    bad = Spectrum([state["energy_relative"] for state in bad_states])
    objective = Spectrum(objective_energies, objective_weights)
    spins = [Spectrum(energies) for energies in spin_energies.values()]
    frozen = None
    best_key = None
    rejected = {"margin_or_width": 0, "low_character": 0,
                "too_many_states": 0, "empty_spin": 0}
    for lower in _grid(outer[0], outer[1]):
        for upper in _grid(outer[1], outer[0], -1):
            a, b = lower + options.frozen_margin, upper - options.frozen_margin
            if a >= b:
                rejected["margin_or_width"] += 1
                continue
            if bad.count(a, b):
                rejected["low_character"] += 1
                continue
            if any(spectrum.count(a, b) > num_wann for _, spectrum in meshes):
                rejected["too_many_states"] += 1
                continue
            if any(spectrum.count(a, b) == 0 for spectrum in spins):
                rejected["empty_spin"] += 1
                continue
            key = (-round(objective.weight(a, b), 12), -round(b - a, 10), a)
            if best_key is None or key < best_key:
                frozen, best_key = (a, b), key

    coverage = []
    for label in labels:
        records = [{**location, "coverage": spectrum.weight(*outer) / total}
                   for location, spectrum, total in distributions if location["pair"] == label]
        coverage.append({"pair": label, "minimum": min(records, key=lambda row: row["coverage"])
                         if records else None})
    edge_locations = [{**location, "lower": outer[0] <= spectrum.energies[0] + 1e-9,
                       "upper": outer[1] >= spectrum.energies[-1] - 1e-9}
                      for location, spectrum in meshes
                      if outer[0] <= spectrum.energies[0] + 1e-9
                      or outer[1] >= spectrum.energies[-1] - 1e-9]
    warnings = []
    if outer[0] == search[0] or outer[1] == search[1]:
        warnings.append("outer window reaches the configured search boundary")
    if edge_locations:
        warnings.append("outer window reaches available band-energy limits; NBANDS convergence is unverified")
    if unavailable:
        warnings.append("some pair/k-point distributions have zero weight; their coverage is unavailable")
    def absolute(interval):
        return [value + fermi for value in interval] if interval else None
    report = {
        "method": "adaptive", "fermi_energy": fermi,
        "outer_selection": "local_equal_tail_quantiles",
        "parameters": {"search_energy_range": list(search), "outer_coverage": options.coverage,
                       "tail_fraction": tail_fraction,
                       "frozen_character_min": options.character_min,
                       "frozen_margin": options.frozen_margin, "grid_step": 0.25},
        "projection_pairs": list(labels), "num_wann": num_wann,
        "windows_relative": {"search": list(search),
                             "outer": list(outer), "frozen": list(frozen) if frozen else None},
        "windows_absolute": {"search": absolute(search),
                             "outer": absolute(outer), "frozen": absolute(frozen)},
        "coverage_by_pair": coverage, "unavailable_coverage": unavailable,
        "outer_quantiles": {
            "scope": "each nonzero pair/k-point/spin distribution within the search range",
            "probabilities": [tail_fraction, 1.0 - tail_fraction],
            "intervals": quantile_intervals,
            "envelope_relative": list(quantile_envelope),
            "envelope_absolute": absolute(quantile_envelope),
            "rounded_grid_relative": list(initial_outer),
            "expanded_for_state_count": any(spectrum.count(*initial_outer) < num_wann
                                            for _, spectrum in meshes),
            "expanded_for_nonzero_width": initial_outer[0] == initial_outer[1],
        },
        "outer_counts": count_summary(meshes, *outer),
        "search_counts": count_summary(meshes, *search),
        "frozen_counts": count_summary(meshes, *frozen) if frozen else None,
        "frozen_rejections": rejected, "low_character_states_in_search": bad_states,
        "outer_only_reason": ("No frozen candidate inside the outer window satisfied character, state-count, "
                              "spin-occupancy and margin constraints.") if frozen is None else None,
        "band_edge_locations": edge_locations, "warnings": warnings,
        "validation_scope": "Supplied SCF/DOS meshes only; generated Wannier mesh is unverified. "
                            "PAW character and local coverage are heuristics, not projectabilities "
                            "or proof of radial-shell identity or interpolation accuracy.",
    }
    return absolute(outer), absolute(frozen), report
