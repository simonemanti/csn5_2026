#!/usr/bin/env python3
"""Plot the Ag foil K-edge reference and an illustrative sampling grid.

The reference is the normalized NIMS/SPring-8 Ag foil spectrum already
prepared in this directory (DOI: 10.48505/nims.1453). Markers are linearly
interpolated on that reference, not new measurements.
"""
from pathlib import Path
import argparse

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--data', type=Path, default=HERE / 'ag_foil_reference.dat',
                        help='Normalized reference spectrum: energy relative to E0 (eV), absorption')
    parser.add_argument('--output', type=Path, default=HERE / 's2_plot_XANES.png',
                        help='Output figure')
    parser.add_argument('--dpi', type=int, default=300, help='Output resolution')
    parser.add_argument('--figsize', type=float, nargs=2, default=(6, 4),
                        metavar=('WIDTH', 'HEIGHT'), help='Figure size in inches')
    parser.add_argument('--coarse-color', default='C0', help='Matplotlib color for the coarse grid')
    parser.add_argument('--fine-color', default='C1', help='Matplotlib color for the fine grid')
    args = parser.parse_args()

    if not np.isfinite(args.figsize).all() or any(size <= 0 for size in args.figsize):
        parser.error('--figsize requires two finite positive values')
    plt.rcParams.update({
        'font.family': 'Arial',
        'axes.unicode_minus': False,
        'svg.fonttype': 'none',
        'mathtext.fontset': 'custom',
        'mathtext.rm': 'Arial',
        'mathtext.it': 'Arial:italic',
        'mathtext.bf': 'Arial:bold',
    })

    energy, absorption = np.loadtxt(args.data, unpack=True)
    if (not np.isfinite(energy).all() or not np.isfinite(absorption).all()
            or not np.all(np.diff(energy) > 0)):
        raise ValueError('Reference energies must be finite and strictly increasing')

    pre = np.arange(-150, -39, 10)
    fine = np.arange(-30, 71, 2)
    post = np.arange(80, 141, 10)
    if energy[0] > pre[0] or energy[-1] < post[-1]:
        raise ValueError('Reference spectrum does not cover the sampling grid')

    fig, ax = plt.subplots(figsize=args.figsize, constrained_layout=True)
    ax.plot(energy, absorption, color='black', lw=1.5, label='Ag foil reference')
    for grid, color, label in ((np.concatenate((pre, post)), args.coarse_color, r'Coarse Grid ($\Delta E = 10$ eV)'),
                               (fine, args.fine_color, r'Fine Grid ($\Delta E = 2$ eV)')):
        ax.scatter(grid, np.interp(grid, energy, absorption), s=24, color=color,
                   edgecolors='white', linewidths=0.4, zorder=3, label=label)
    ax.set(xlim=(-160, 150), xlabel=r'Energy relative to Ag K Edge (eV)',
           ylabel='Normalized Absorption')
    ymin, ymax = ax.get_ylim()
    ax.set_ylim(ymin, ymax)
    ax.vlines(0, ymin, np.interp(0, energy, absorption), color='0.45',
              linestyles='--', lw=1)
    ax.spines[['top', 'right']].set_visible(False)
    ax.text(-105, 0.16, 'Coarse Grid\n' + r'$\Delta E = 10$ eV',
            color=args.coarse_color, fontsize=13, ha='center')
    ax.text(15, 1.08, 'Fine Grid\n' + r'$\Delta E = 2$ eV',
            color=args.fine_color, fontsize=13, ha='center')
    ax.text(3, 0.52, 'Ag K Edge', color='0.45', fontsize=12, rotation=90,
            va='center')
    ax.text(110, 1.08, 'Coarse Grid\n' + r'$\Delta E = 10$ eV',
            color=args.coarse_color, fontsize=13, ha='center')
    fig.savefig(args.output, dpi=args.dpi, facecolor='white')
    fig.savefig(args.output.with_suffix('.svg'), facecolor='white')
    print(f'Saved {args.output} and {args.output.with_suffix(".svg")}; {len(pre)} pre-edge, {len(fine)} fine and '
          f'{len(post)} post-edge points: {len(pre) + len(fine) + len(post)} energies.')
    plt.show()


if __name__ == '__main__':
    main()
