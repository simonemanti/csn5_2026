import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xraylib
from matplotlib import rc

rc('font', **{'family': 'sans-serif', 'sans-serif': ['FreeSans']})


def main():
    parser = argparse.ArgumentParser(
        description='Plot intrinsic X-ray detector efficiencies.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--emin', type=float, default=0.1, help='minimum energy (keV)')
    parser.add_argument('--emax', type=float, default=50, help='maximum energy (keV)')
    parser.add_argument('--si-thickness', type=float, default=450,
                        help='Si SDD thickness (um)')
    parser.add_argument('--ge-thickness', type=float, default=1,
                        help='HPGe thickness (mm)')
    parser.add_argument('--czt-thickness', type=float, default=1,
                        help='CZT thickness (mm)')
    parser.add_argument('--edges', nargs='*', default=['Fe', 'Co', 'Ni', 'Cu'],
                        help='elements whose K edges are shown')
    args = parser.parse_args()
    if args.emin <= 0 or args.emax <= args.emin:
        parser.error('require 0 < emin < emax')
    if min(args.si_thickness, args.ge_thickness, args.czt_thickness) <= 0:
        parser.error('detector thicknesses must be positive')

    energy = np.linspace(args.emin, args.emax, 1000)
    si_thickness = args.si_thickness * 1e-4
    ge_thickness = args.ge_thickness * 0.1
    czt_thickness = args.czt_thickness * 0.1

    def efficiency(mu_rho, density, thickness_cm):
        return 1 - np.exp(-np.asarray(mu_rho) * density * thickness_cm)

    si_mu = [xraylib.CS_Total(xraylib.SymbolToAtomicNumber('Si'), e) for e in energy]
    ge_mu = [xraylib.CS_Total(xraylib.SymbolToAtomicNumber('Ge'), e) for e in energy]

    composition = {'Cd': 0.9, 'Zn': 0.1, 'Te': 1.0}
    molar_mass = sum(n * xraylib.AtomicWeight(xraylib.SymbolToAtomicNumber(el))
                     for el, n in composition.items())
    mass_fractions = {
        el: n * xraylib.AtomicWeight(xraylib.SymbolToAtomicNumber(el)) / molar_mass
        for el, n in composition.items()
    }
    czt_mu = [
        sum(w * xraylib.CS_Total(xraylib.SymbolToAtomicNumber(el), e)
            for el, w in mass_fractions.items())
        for e in energy
    ]

    si_eff = efficiency(si_mu, 2.33, si_thickness)
    ge_eff = efficiency(ge_mu, 5.32, ge_thickness)
    czt_eff = efficiency(czt_mu, 5.8, czt_thickness)

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(energy, si_eff, label=f'Si SDD ({args.si_thickness:g} µm)')
    ax.plot(energy, ge_eff, label=f'HPGe ({args.ge_thickness:g} mm)')
    ax.plot(energy, czt_eff, label=f'CZT ({args.czt_thickness:g} mm)')

    edge_labeled = False
    for element in args.edges:
        try:
            z = xraylib.SymbolToAtomicNumber(element)
        except ValueError:
            parser.error(f'invalid element symbol: {element}')
        edge = xraylib.EdgeEnergy(z, xraylib.K_SHELL)
        if edge <= args.emax:
            ax.axvline(edge, color='0.45', ls='--', lw=0.8,
                       label='K-edge' if not edge_labeled else '_nolegend_')
            edge_labeled = True
            ax.text(edge + 0.15, 0.04, element, rotation=90, color='0.35',
                    ha='left', va='bottom', fontsize=8)

    ax.set(xlabel='Energy [keV]', ylabel='Intrinsic detection efficiency',
           xlim=(0, args.emax), ylim=(0, 1.05))
    ax.grid(ls=':')
    ax.set_xlim(0, 50)
    ax.set_ylim(0, 1.05)
    ax.legend(loc='right', fontsize=10)
    fig.tight_layout()

    output = Path(__file__).with_suffix('')
    fig.savefig(output.with_suffix('.pdf'))
    fig.savefig(output.with_suffix('.png'), dpi=300)
    plt.show()


if __name__ == '__main__':
    main()
