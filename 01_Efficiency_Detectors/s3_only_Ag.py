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
    parser.add_argument('--emin', type=float, default=10, help='minimum energy (keV)')
    parser.add_argument('--emax', type=float, default=50, help='maximum energy (keV)')
    parser.add_argument('--si-thickness', type=float, default=450,
                        help='Si SDD thickness (um)')
    parser.add_argument('--ge-thickness', type=float, default=1,
                        help='HPGe thickness (mm)')
    parser.add_argument('--czt-thickness', type=float, default=2,
                        help='CZT thickness (mm)')
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

    fig, ax = plt.subplots(figsize=(5, 3.4))
    ax.plot(energy, 100 * si_eff, c='#ff3333', lw=1.5,
            label=f'Si SDD · {args.si_thickness:g} µm')
    ax.plot(energy, 100 * ge_eff, c='#0088cc', lw=1.5,
            label=f'HPGe · {args.ge_thickness:g} mm')
    ax.plot(energy, 100 * czt_eff, c='#00b83f', lw=1.5,
            label=f'CZT · {args.czt_thickness:g} mm')

    ag_ka = 22.2  # Ag Kalpha reference energy shown in the supplied figure (keV).
    ax.axvline(ag_ka, color='#34495e', ls='--', lw=0.8)
    ax.annotate('Ag Kα\n22.2 keV', xy=(ag_ka, 55), xytext=(6, 0),
                textcoords='offset points', ha='left', va='center', fontsize=9)

    ax.set(xlabel='Photon energy (keV)', ylabel='Interaction efficiency (%)',
           xlim=(args.emin, args.emax), ylim=(0, 105))
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='0.92', lw=0.6)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis='both', length=0, labelsize=9)
    ax.legend(loc='center right', bbox_to_anchor=(1, 0.5),
              frameon=False, fontsize=9, handlelength=1.8)
    fig.tight_layout()

    output = Path(__file__).with_suffix('')
    fig.savefig(output.with_suffix('.pdf'))
    fig.savefig(output.with_suffix('.png'), dpi=300,
                bbox_inches='tight', pad_inches=1 / 25.4)
    plt.show()


if __name__ == '__main__':
    main()
