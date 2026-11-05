#!/usr/bin/env python3
"""Prepare vector-plot tables from the local measured Ag foil reference."""
from pathlib import Path
import json
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / '21_XANES_Ag/data/Ag_foil/Ag-K_Ag-foil_Si311_50ms_160624.txt'
E0 = 25514.0


def main():
    energy, mu = np.loadtxt(SOURCE).T
    if not np.isfinite([energy, mu]).all() or not np.all(np.diff(energy) > 0):
        raise ValueError('Invalid reference spectrum')
    x = energy - E0
    # Identical normalization to 21_XANES_Ag/s1_ref_comparison.py.
    pre = np.polyfit(x[(x >= -280) & (x <= -150)], mu[(x >= -280) & (x <= -150)], 1)
    post = np.polyfit(x[(x >= 150) & (x <= 700)], mu[(x >= 150) & (x <= 700)], 2)
    step = float(post[-1] - pre[-1])
    norm = (mu - np.polyval(pre, x)) / step
    coarse = np.arange(-105.0, -5.0, 10.0)
    fine = np.linspace(-5.0, 70.0, 140)
    grid = np.concatenate([coarse, fine])
    assert len(grid) == 150 and np.all(np.diff(grid) > 0)
    assert np.allclose(np.diff(fine), 75 / 139)
    # Preserve every original point; TikZ clips to the displayed window.
    np.savetxt(HERE / 'ag_foil_reference.dat', np.column_stack([x, norm]), fmt='%.12g')
    for name, positions in [('coarse', coarse), ('fine', fine)]:
        # Interpolation places planned sampling marks on the reference curve only.
        np.savetxt(HERE / f'scan_{name}.dat',
                   np.column_stack([positions, np.interp(positions, x, norm)]), fmt='%.12g')
    np.savetxt(HERE / 'scan_grid.dat', np.column_stack([np.arange(1, 151), grid, E0 + grid]),
               fmt=['%d', '%.12f', '%.12f'], header='index  relative_energy_eV  energy_eV')
    report = dict(reference=str(SOURCE.relative_to(HERE.parent)), doi='10.48505/nims.1453',
                  e0_eV=E0, edge_step=step, coarse_points=10, fine_points=140,
                  total_energies=150, fine_step_eV=75 / 139,
                  coarse_relative_eV=coarse.tolist(), fine_range_relative_eV=[-5, 70],
                  reference_energy_shift_eV=0, reference_smoothing=False,
                  sequence=['I: full grid', 'I0: same full grid'],
                  crystal_resolution_eV=None,
                  constraint='Both scan steps must be smaller than the crystal energy resolution')
    (HERE / 'protocol.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'150 energies: 10 coarse + 140 fine; fine step = {75/139:.9f} eV')


if __name__ == '__main__':
    main()
