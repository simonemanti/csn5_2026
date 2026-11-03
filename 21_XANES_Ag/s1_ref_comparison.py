#!/usr/bin/env python3
"""Slide-ready comparison of measured Ag K-edge reference spectra.

Sources: NIMS MDR / JASRI, SPring-8 BL14B2, transmission, 2016-06-24.
Ag foil: doi:10.48505/nims.1453; Ag2O: doi:10.48505/nims.1463.
Uses the encoder-energy .txt files, NOT the alternative *_fe exports.
Normalization: subtract linear pre-edge; divide by the difference between
quadratic post-edge and linear pre-edge extrapolated to the common E0.
No energy alignment, smoothing, broadening, vertical offset or flattening.
These synchrotron references are not a simulation of PRISM performance.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MultipleLocator, FormatStrFormatter

HERE = Path(__file__).resolve().parent
SAMPLES = [
    ('Ag_foil', 'Ag-K_Ag-foil_Si311_50ms_160624.txt', 'Ag metal', 'C0', '10.48505/nims.1453'),
    ('Ag2O', 'Ag-K_Ag2O_Si311_50ms_160624.txt', r'Ag$_2$O', 'C1', '10.48505/nims.1463'),
]


def normalize(energy, mu, e0, pre_range, post_range):
    x = energy - e0
    pre_mask = (x >= pre_range[0]) & (x <= pre_range[1])
    post_mask = (x >= post_range[0]) & (x <= post_range[1])
    if pre_mask.sum() < 3 or post_mask.sum() < 4:
        raise ValueError('Insufficient points in normalization windows')
    pre = np.polyfit(x[pre_mask], mu[pre_mask], 1)
    post = np.polyfit(x[post_mask], mu[post_mask], 2)
    step = float(post[-1] - pre[-1])
    if not np.isfinite(step) or step <= 0:
        raise ValueError('Non-positive or invalid edge step')
    return (mu - np.polyval(pre, x)) / step, step


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--data-dir', type=Path, default=HERE / 'data', help='Extracted reference datasets')
    parser.add_argument('--output', type=Path, default=HERE / 's1_ref_comparison.png', help='Output PNG')
    parser.add_argument('--e0', type=float, default=25514.0, help='Common normalization reference in eV; does not shift energies')
    parser.add_argument('--pre-range', type=float, nargs=2, default=(-280., -150.), help='Pre-edge fit window relative to E0, eV')
    parser.add_argument('--post-range', type=float, nargs=2, default=(150., 700.), help='Post-edge fit window relative to E0, eV')
    parser.add_argument('--xmin', type=float, default=25.465, help='Minimum displayed incident energy, keV')
    parser.add_argument('--xmax', type=float, default=25.610, help='Maximum displayed incident energy, keV')
    parser.add_argument('--dpi', type=int, default=300, help='PNG resolution')
    args = parser.parse_args()
    if not np.isfinite([args.xmin, args.xmax]).all() or args.xmin >= args.xmax:
        parser.error('require finite xmin < xmax (keV)')
    plt.style.use('default')
    for font_path in font_manager.findSystemFonts():
        if 'arial' in Path(font_path).name.lower():
            font_manager.fontManager.addfont(font_path)
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Arial'],
        'mathtext.fontset': 'custom', 'mathtext.rm': 'Arial',
        'mathtext.it': 'Arial:italic', 'mathtext.bf': 'Arial:bold',
        'font.size': 10, 'axes.labelsize': 11,
        'xtick.labelsize': 10, 'ytick.labelsize': 10,
        'legend.fontsize': 11, 'axes.linewidth': .8,
        'pdf.fonttype': 42, 'ps.fonttype': 42,
    })
    fig, ax = plt.subplots(figsize=(160 / 25.4, 100 / 25.4))
    fig.subplots_adjust(left=.12, right=.98, bottom=.16, top=.97)
    report = {'normalization_e0_eV': args.e0, 'pre_window_relative_eV': args.pre_range,
              'post_window_relative_eV': args.post_range, 'energy_shift_eV': 0,
              'smoothing': False, 'samples': []}
    for folder, filename, label, color, doi in SAMPLES:
        path = args.data_dir / folder / filename
        data = np.loadtxt(path)
        if data.ndim != 2 or data.shape[1] != 2 or not np.isfinite(data).all():
            raise ValueError(f'Invalid spectrum: {path}')
        energy, mu = data.T
        if not np.all(np.diff(energy) > 0):
            raise ValueError(f'Energy grid is not strictly increasing: {path}')
        norm, step = normalize(energy, mu, args.e0, args.pre_range, args.post_range)
        ax.plot(energy / 1000, norm, color=color, lw=1.5, label=label)
        report['samples'].append({'file': str(path), 'doi': doi, 'edge_step': step, 'points': len(energy)})
    ax.set(xlim=(args.xmin, args.xmax), ylim=(-.05, 1.22), xlabel='Incident energy (keV)', ylabel='Normalized absorption')
    ax.legend(loc='upper left', frameon=False, fontsize=11, handlelength=2.0)
    ax.xaxis.set_major_locator(MultipleLocator(.025))
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    ax.yaxis.set_major_locator(MultipleLocator(.25))
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(direction='out', length=4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=args.dpi, facecolor='white')
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved {args.output}')
    plt.show()


if __name__ == '__main__':
    main()
