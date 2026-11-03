#!/usr/bin/env python3
"""Intrinsic, fixed-angle Ag K-edge reflectivity using OASYS/XCRYSTAL diff_pat.

Flat symmetric Bragg geometry: finite perfect Ge, Gaussian mosaic graphite.
Each reflection is independently aligned to the maximum at the Ag K edge unless
an absolute glancing angle is supplied. This is not a curved-optics ray trace.
Run in shadow4-mosaics. All figures are saved and displayed with plt.show().
"""
import argparse
import ast
import contextlib
import csv
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent


def project_defaults():
    geometry = json.loads((PROJECT / '03_Simulations/config/wp1_geometry.json').read_text())
    tree = ET.parse(HERE / 'v1_Reflectivity.ows')
    props = ast.literal_eval(tree.find("./node_properties/properties[@node_id='4']").text)
    return geometry['crystal']['thickness_m'] * 1000, props['MOSAIC_FWHM']


def fwhm(x, y):
    """Interpolated half-maximum width of the connected dominant peak."""
    peak = int(np.argmax(y))
    if y[peak] <= 1e-12:
        raise ValueError('Reflection is extinct or numerically negligible.')
    half = y[peak] / 2
    left = peak
    right = peak
    while left > 0 and y[left] >= half:
        left -= 1
    while right < len(y)-1 and y[right] >= half:
        right += 1
    if left == 0 and y[left] >= half or right == len(y)-1 and y[right] >= half:
        raise ValueError('Scan clips the half-maximum; increase --span-ev or check the supplied angle.')
    xl = np.interp(half, y[left:left+2], x[left:left+2])
    xr = np.interp(half, y[right-1:right+1][::-1], x[right-1:right+1][::-1])
    return float(xr-xl)


def scan(work, material, hkl, thickness_mm, mosaic_deg, scan_type, fixed,
         low, high, points, library):
    """Same preprocessor and Fortran backend as the local OASYS2 XCRYSTAL.

    diff_pat thickness is cm; mosaic FWHM and fixed energy-scan angle are deg.
    The isolated directory prevents overwriting OASYS intermediate files.
    """
    import xraylib
    from dabax.dabax_xraylib import DabaxXraylib
    from xoppylib.crystals.tools import bragg_calc2
    from xoppylib.xoppy_util import locations

    work.mkdir(parents=True, exist_ok=True)
    emin, emax = (low-2, high+2) if scan_type == 3 else (fixed-100, fixed+100)
    constants = xraylib if library == 'xraylib' else DabaxXraylib()
    pre = work / 'crystal.bra'
    with (work / 'preprocessor.log').open('w') as log, contextlib.redirect_stdout(log):
        bragg_calc2(descriptor=material, hh=hkl[0], kk=hkl[1], ll=hkl[2],
                    temper=1.0, emin=emin, emax=emax, estep=(emax-emin)/500,
                    ANISO_SEL=0, fileout=str(pre), do_not_prototype=0,
                    verbose=False, material_constants_library=constants)
    values = [str(pre), str(int(mosaic_deg > 0)), '0']
    if mosaic_deg > 0:
        values += [str(mosaic_deg), str(thickness_mm/10)]
    else:
        values += [str(thickness_mm/10), '0']
    values += [str(scan_type+1), f'{fixed:.12g}']
    if scan_type <= 2:
        values += ['2']  # absolute angles in degrees
    values += [f'{low:.12g}', f'{high:.12g}', str(points)]
    inp = '\n'.join(values) + '\n'
    (work / 'input.txt').write_text(inp)
    result = subprocess.run([str(Path(locations.home_bin()) / 'diff_pat')],
                            input=inp, text=True, cwd=work, capture_output=True)
    (work / 'diff_pat.log').write_text(result.stdout + result.stderr)
    if result.returncode or not (work / 'diff_pat.dat').exists():
        raise RuntimeError(f'XCRYSTAL failed: see {work / "diff_pat.log"}')
    data = np.loadtxt(work / 'diff_pat.dat', comments='#', ndmin=2)
    # Local widget labels: column 5 = pi, column 6 = sigma (zero based).
    rs, rp = data[:, 6], data[:, 5]
    if not np.isfinite(data).all() or np.min([rs.min(), rp.min()]) < -1e-7 or max(rs.max(), rp.max()) > 1.00001:
        raise RuntimeError(f'Unphysical diff_pat output in {work}')
    for name in ('diff_pat.dat', 'diff_pat.gle', 'diff_pat.xop'):
        (work / name).unlink(missing_ok=True)
    return data[:, 0], rs, rp


def main():
    ge_mm, mosaic = project_defaults()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--ge-hkl', type=int, nargs=3, action='append', default=argparse.SUPPRESS,
                   help='repeat for several Ge reflections; default: 220, 440, 660, 880')
    p.add_argument('--hapg-hkl', type=int, nargs=3, action='append', default=argparse.SUPPRESS,
                   help='repeat for several graphite reflections; default: 002, 004, 006, 008')
    p.add_argument('--ge-thickness-mm', type=float, default=ge_mm, help='finite Ge thickness from PRISM geometry')
    p.add_argument('--hapg-thickness-um', type=float, default=100.,
                   help='HAPG model thickness; project precedent: 12_VOXES_Feasebility/s2_compare.py')
    p.add_argument('--mosaic-fwhm-deg', type=float, default=mosaic, help='Gaussian HAPG mosaic FWHM from saved OASYS workflow')
    p.add_argument('--ge-angle-deg', type=float, default=None, help='absolute glancing angle; requires one Ge hkl; None = align to Ag K-edge energy')
    p.add_argument('--hapg-angle-deg', type=float, default=None, help='absolute glancing angle; requires one HAPG hkl; None = align to Ag K-edge energy')
    p.add_argument('--span-ev', type=float, default=600., help='energy half-span around the Ag K edge')
    p.add_argument('--points', type=int, default=20001, help='points per scan; an additional fine energy grid resolves narrow peaks')
    p.add_argument('--polarization', choices=['unpolarized', 'sigma', 'pi'], default='unpolarized', help='incident polarization')
    p.add_argument('--library', choices=['xraylib', 'dabax'], default='xraylib', help='constants backend; select the same in GUI')
    p.add_argument('--output', type=Path, default=HERE / 's2_ge_vs_hapg', help='output basename: PNG, CSV, summary JSON, calculation logs')
    a = p.parse_args()
    ge = getattr(a, 'ge_hkl', None) or [[n, n, 0] for n in (2,4,6,8)]
    hapg = getattr(a, 'hapg_hkl', None) or [[0, 0, n] for n in (2,4,6,8)]
    if any(not np.isfinite(v) or v <= 0 for v in [a.ge_thickness_mm, a.hapg_thickness_um, a.mosaic_fwhm_deg, a.span_ev]) or a.points < 1001:
        p.error('Thicknesses, mosaicity and span must be positive and finite; points >= 1001.')
    for name, angle, hkls in [('Ge',a.ge_angle_deg,ge), ('HAPG',a.hapg_angle_deg,hapg)]:
        if angle is not None and (len(hkls) != 1 or not 0 < angle < 90):
            p.error(f'{name}: an explicit angle requires one hkl and 0 < angle < 90 deg.')
    if any(not any(hkl) for hkl in ge+hapg):
        p.error('(000) is not a reflection.')
    import xraylib
    import matplotlib.pyplot as plt
    edge_ev = xraylib.EdgeEnergy(47, xraylib.K_SHELL)*1000
    if edge_ev-a.span_ev <= 100:
        p.error('Energy scan extends outside the positive X-ray range.')
    output = a.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    logs = output.parent / (output.name + '_calculations')
    rows = []
    curves = []
    def selected(rs, rp):
        return {'unpolarized':(rs+rp)/2, 'sigma':rs, 'pi':rp}[a.polarization]
    for material, hkls, thickness, spread, fixed_angle in [
        ('Ge', ge, a.ge_thickness_mm, 0., a.ge_angle_deg),
        ('Graphite', hapg, a.hapg_thickness_um/1000, a.mosaic_fwhm_deg, a.hapg_angle_deg)]:
        for hkl in hkls:
            label = ('Ge' if material == 'Ge' else 'HAPG') + '(' + ','.join(map(str,hkl)) + ')'
            work = logs / label.replace(',','_')
            crystal = xraylib.Crystal_GetCrystal(material)
            d = xraylib.Crystal_dSpacing(crystal,*hkl)
            arg = 12398.419843320026/(2*d*edge_ev)
            if not 0 < arg < 1:
                p.error(f'{label}: Bragg condition inaccessible at the Ag K edge.')
            theta = np.degrees(np.arcsin(arg))
            angle = theta if fixed_angle is None else fixed_angle
            # Calibrate with energy scans themselves: XCRYSTAL's absolute
            # angular scan uses the surface-normal convention (90+grazing).
            # Do not mix that axis with the grazing input of an energy scan.
            x, rs, rp = scan(work/'initial',material,hkl,thickness,spread,3,angle,
                             edge_ev-a.span_ev,edge_ev+a.span_ev,a.points,a.library)
            r = selected(rs,rp)
            initial_width = fwhm(x,r)
            fine_span = max(5., 5*initial_width)
            resonance = float(x[np.argmax(r)])
            if fixed_angle is None:
                for iteration in range(3):
                    angle = float(np.degrees(np.arcsin(np.sin(np.radians(angle))*resonance/edge_ev)))
                    x, rs, rp = scan(work/f'tune_{iteration}',material,hkl,thickness,spread,3,angle,
                                     max(100.,edge_ev-fine_span),edge_ev+fine_span,a.points,a.library)
                    r = selected(rs,rp)
                    resonance = float(x[np.argmax(r)])
            ranges = [('wide', edge_ev-a.span_ev,edge_ev+a.span_ev),
                      ('fine',max(edge_ev-a.span_ev,resonance-fine_span),min(edge_ev+a.span_ev,resonance+fine_span))]
            parts=[]
            for name, lo, hi in ranges:
                if hi > lo:
                    parts.append(scan(work/name, material,hkl,thickness,spread,3,angle,lo,hi,a.points,a.library))
            if len(parts) == 2:
                # Use only the dense calculation inside its window. Mixing
                # sparse samples into that interval adds numerical artifacts.
                wide, fine = parts
                outside = (wide[0] < fine[0][0]) | (wide[0] > fine[0][-1])
                parts = [tuple(v[outside] for v in wide), fine]
            energies, sigma, pi = [np.concatenate([part[i] for part in parts]) for i in range(3)]
            energies, indices = np.unique(energies,return_index=True)
            sigma, pi = sigma[indices], pi[indices]
            r = selected(sigma,pi)
            width = fwhm(energies,r)
            peak = int(np.argmax(r))
            row = dict(crystal=label, hkl=hkl, thickness_mm=thickness, mosaic_fwhm_deg=spread,
                       angle_deg=angle, peak_energy_ev=float(energies[peak]), peak_reflectivity=float(r[peak]),
                       fwhm_ev=width, equivalent_angular_fwhm_deg=float(np.degrees(width*np.tan(np.radians(angle))/edge_ev)),
                       integral_ev=float(np.trapezoid(r,energies)),
                       r_at_kedge=float(np.interp(edge_ev,energies,r)))
            rows.append(row)
            curves.append((label,energies,r,sigma,pi))
            print(f'{label:13s} theta={angle:9.5f} deg  Rmax={r[peak]:.5f}  FWHM={width:9.4f} eV  integral={row["integral_ev"]:.5f} eV', flush=True)
    fig, axes = plt.subplots(1,2,figsize=(13,5.5),layout='constrained')
    colors = plt.cm.tab10(np.arange(len(curves)) % 10)
    for (label,energy,r,_,_), row, color in zip(curves,rows,colors):
        for ax in axes:
            ax.plot(energy-edge_ev,r,color=color,lw=1.6,ls='-' if label.startswith('Ge') else '--',
                    label=f'{label}  {row["fwhm_ev"]:.2f} eV')
    for ax in axes:
        ax.axvline(0,color='.4',lw=.9,alpha=.6)
        ax.set(xlabel=r'$E-E_{K,Ag}$ [eV]', ylabel=f'Intrinsic reflectivity ({a.polarization})',ylim=(0,1.03))
        ax.grid(alpha=.25)
    axes[0].text(0,.99,'Ag K-edge',ha='left',va='top')
    axes[0].set(xlim=(-a.span_ev,a.span_ev),title='Fixed-angle energy acceptance')
    zoom = min(a.span_ev,max(.2,6*min(row['fwhm_ev'] for row in rows if row['crystal'].startswith('Ge'))))
    axes[1].set(xlim=(-zoom,zoom),title='Narrow-band detail')
    axes[1].legend(fontsize=8,loc='upper right')
    fig.suptitle(f'Ge vs HAPG at Ag K-edge = {edge_ev/1000:.4f} keV\n'
                 f'Ge {a.ge_thickness_mm:g} mm; HAPG {a.hapg_thickness_um:g} µm, mosaic FWHM {a.mosaic_fwhm_deg:g}°; flat symmetric Bragg',fontsize=11)
    fig.savefig(output.with_suffix('.png'),dpi=220)
    with output.with_suffix('.csv').open('w',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['crystal','energy_ev','reflectivity','r_sigma','r_pi'])
        for label,energy,r,rs,rp in curves:
            writer.writerows(zip([label]*len(energy),energy,r,rs,rp))
    summary=dict(ag_kedge_ev=edge_ev,reference="Ag K absorption edge",polarization=a.polarization,library=a.library,
                 model='XCRYSTAL/diff_pat: finite perfect Ge; Gaussian mosaic graphite; flat symmetric Bragg; temperature factor=1',
                 defaults_sources=['03_Simulations/config/wp1_geometry.json: Ge thickness',
                                   '12_VOXES_Feasebility/s2_compare.py: 100 um model thickness',
                                   '02_Lower_Reflection/v1_Reflectivity.ows: mosaic FWHM'],
                 limitations='Intrinsic model, not measured HAPG efficiency or bent-optics resolution; integrals cover the selected energy window.',
                 parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},results=rows)
    output.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f'Saved {output}.png, .csv, .json and logs in {logs}')
    plt.show()


if __name__ == '__main__':
    main()
