#!/usr/bin/env python3
"""Prepare the measured Ag-foil reference for the PRISM v2 animation.

Uses the same normalization as 21_XANES_Ag/s1_ref_comparison.py. PCHIP makes a
smooth, shape-preserving display curve without changing measured ordinates.
The plotted curve is not filtered, energy shifted, broadened or flattened.
Only the operational edge-position estimator smooths a copy of the curve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
DEFAULT_DATA = PROJECT / '21_XANES_Ag/data/Ag_foil/Ag-K_Ag-foil_Si311_50ms_160624.txt'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--source', type=Path, default=DEFAULT_DATA, help='Measured encoder-energy Ag foil spectrum.')
    parser.add_argument('--output', type=Path, default=HERE / 'v2_xas_reference.json', help='Portable JSON consumed by Blender.')
    parser.add_argument('--relative-min', type=float, default=-45.0, help='Display minimum energy relative to the slope-derived E0, in eV.')
    parser.add_argument('--relative-max', type=float, default=130.0, help='Display maximum energy relative to the slope-derived E0, in eV.')
    parser.add_argument('--step-ev', type=float, default=0.1, help='Maximum display-grid spacing in eV.')
    parser.add_argument('--e0-ev', type=float, default=25514.0, help='Normalization reference energy, not an energy shift.')
    parser.add_argument('--edge-estimator-sigma-ev', type=float, default=1.5, help='Gaussian sigma used only to locate the maximum edge slope.')
    args = parser.parse_args()
    if not (np.isfinite([args.relative_min, args.relative_max, args.step_ev, args.e0_ev, args.edge_estimator_sigma_ev]).all()
            and args.relative_max > args.relative_min and args.step_ev > 0 and args.edge_estimator_sigma_ev > 0):
        parser.error('Require finite values, relative-min < relative-max and positive step/sigma.')

    energy, mu = np.loadtxt(args.source).T
    if not (np.isfinite(energy).all() and np.isfinite(mu).all() and np.all(np.diff(energy) > 0)):
        raise ValueError('Invalid measured energy or absorption values.')
    relative = energy - args.e0_ev
    pre_window = (-280.0, -150.0)
    post_window = (150.0, 700.0)
    pre_mask = (relative >= pre_window[0]) & (relative <= pre_window[1])
    post_mask = (relative >= post_window[0]) & (relative <= post_window[1])
    pre = np.polyfit(relative[pre_mask], mu[pre_mask], 1)
    post = np.polyfit(relative[post_mask], mu[post_mask], 2)
    edge_step = float(post[-1] - pre[-1])
    if edge_step <= 0:
        raise ValueError('Invalid normalization edge step.')
    normalized = (mu - np.polyval(pre, relative)) / edge_step

    pchip = PchipInterpolator(energy, normalized, extrapolate=False)
    # Derivative of raw noisy data yields an unstable maximum. This smoothing is
    # for a display timing coordinate only; it never modifies the displayed curve.
    estimator_energy = np.linspace(25465.0, 25540.0, 751)
    estimator = gaussian_filter1d(pchip(estimator_energy), args.edge_estimator_sigma_ev / 0.1)
    derivative = np.gradient(estimator, estimator_energy)
    edge_search = (estimator_energy >= 25485) & (estimator_energy <= 25515)
    edge_energy = float(estimator_energy[edge_search][np.argmax(derivative[edge_search])])
    start, stop = edge_energy + args.relative_min, edge_energy + args.relative_max
    if not (energy[0] <= start < stop <= energy[-1]):
        raise ValueError('Display range must lie within the measured energy domain.')
    number = int(np.ceil((stop - start) / args.step_ev)) + 1
    display_energy = np.linspace(start, stop, number)
    spacing = float(display_energy[1] - display_energy[0])
    display_absorption = pchip(display_energy)

    # PCHIP should remain within both endpoint ordinates of each measured interval.
    left = np.clip(np.searchsorted(energy, display_energy, side='right') - 1, 0, len(energy) - 2)
    lower = np.minimum(normalized[left], normalized[left + 1])
    upper = np.maximum(normalized[left], normalized[left + 1])
    overshoot = np.maximum(lower - display_absorption, display_absorption - upper)
    max_overshoot = float(max(0.0, overshoot.max()))
    if max_overshoot > 1e-10:
        raise AssertionError('Display interpolation overshoots measured interval bounds.')

    edge_progress = (edge_energy - start) / (stop - start)
    visible_raw = (energy >= start) & (energy <= stop)
    raw_error = float(np.max(np.abs(pchip(energy[visible_raw]) - normalized[visible_raw])))
    result = {
        'sample': 'Ag foil',
        'reference_type': 'Measured synchrotron reference; not a PRISM measurement or performance simulation.',
        'source': {
            'file': str(args.source.resolve().relative_to(PROJECT)),
            'sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
            'doi': '10.48505/nims.1453',
            'facility': 'SPring-8 BL14B2',
            'depositor': 'JASRI / Hironori Ofuchi',
            'measurement_date': '2016-06-24',
            'mode': 'Transmission; Si(311); encoder-energy .txt export, not *_fe.',
            'measured_points': len(energy),
            'energy_shift_eV': 0.0,
            'energy_note': 'Encoder energy retained without alignment. The slope-based operational edge is near 25.499 keV; 25.514 keV is only the original normalization reference.'
        },
        'normalization': {
            'reference_script': '21_XANES_Ag/s1_ref_comparison.py',
            'e0_eV': args.e0_ev,
            'pre_window_relative_eV': list(pre_window),
            'post_window_relative_eV': list(post_window),
            'pre_linear_coefficients': pre.tolist(),
            'post_quadratic_coefficients': post.tolist(),
            'edge_step': edge_step,
            'formula': '(mu - linear_pre_edge(E-E0)) / (quadratic_post_edge(0) - linear_pre_edge(0))'
        },
        'interpolation': {
            'method': 'PCHIP, shape preserving on each measured interval',
            'display_step_eV': spacing,
            'smoothing': False,
            'broadening': False,
            'flattening': False,
            'points': number,
            'maximum_interval_overshoot': max_overshoot,
            'maximum_residual_at_measured_points': raw_error
        },
        'edge_energy_keV': edge_energy / 1000,
        'e0_derivative_eV': edge_energy,
        'edge_progress': edge_progress,
        'edge_locator': {
            'purpose': 'Operational animation timing; not an independently calibrated Ag K-edge determination.',
            'method': 'Maximum first derivative after Gaussian smoothing of a temporary estimator copy.',
            'gaussian_sigma_eV': args.edge_estimator_sigma_ev,
            'search_window_eV': [25485, 25515],
            'curve_itself_smoothed': False
        },
        'axis': {
            'xlabel': 'E − E₀ (eV)',
            'ylabel': 'Normalized absorption',
            'xlim_keV': [start / 1000, stop / 1000],
            'xlim_relative_eV': [args.relative_min, args.relative_max],
            'ylim': [-0.05, 1.15],
            'xticks_relative_eV': [-40, 0, 40, 80, 120],
            'yticks': [0.0, 0.5, 1.0],
            'xtick_format': '.0f',
            'ytick_format': '.1f'
        },
        'energy_eV': display_energy.tolist(),
        'energy_keV': (display_energy / 1000).tolist(),
        'relative_energy_eV': (display_energy - edge_energy).tolist(),
        'normalized_absorption': display_absorption.tolist()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Saved {args.output}')
    print(f'{number} points; slope edge {edge_energy / 1000:.6f} keV; progress {edge_progress:.6f}; relative range {args.relative_min:.1f} to {args.relative_max:.1f} eV')
    print(f'No smoothing or energy shift applied to displayed curve. PCHIP max overshoot: {max_overshoot:.3g}')


if __name__ == '__main__':
    main()
