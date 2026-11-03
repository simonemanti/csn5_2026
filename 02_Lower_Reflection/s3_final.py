#!/usr/bin/env python3
"""One explanatory plot: why Ge(880) gives a compact hard-X-ray von Hamos.

Uses the actual VOXES HAPG configuration and the R206 O-2094 substrate drawing.
This is a curved GEOMETRY calculation, not a bent-crystal reflectivity model.
No unprovided Ge thickness, elastic tensor or bonding strain is invented.
Outputs a PNG, numerical CSV and provenance JSON; always calls plt.show().
"""
import argparse
import ast
import csv
import json
import re
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xraylib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VOXES = Path('/home/smanti/WORK/VOXES/RAY-TRACING/07_VOXES_Single_Spectrum/s1_compare_GUI.py')
SUPPORT = ROOT / '03_Simulations/O-2094 subsrate for Von Hamos analyzer 50x25 R206.pdf'
HC_KEV_A = 12.398419843320026


def voxes_parameters(path):
    """Read source as data; never execute the VOXES simulation."""
    tree = ast.parse(path.read_text())
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Name) and node.func.id == 'S4SphereMosaicCrystal']
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one VOXES mosaic crystal in {path}')
    keys = ['material', 'miller_index_h', 'miller_index_k', 'miller_index_l',
            'thickness', 'radius', 'is_cylinder', 'cylinder_direction',
            'mosaicity_fwhm_deg', 'mosaicity_profile_flag']
    params = {kw.arg: ast.literal_eval(kw.value) for kw in matches[0].keywords if kw.arg in keys}
    if params.get('is_cylinder') != 1:
        raise ValueError('The selected VOXES source does not specify a cylindrical crystal.')
    return params


def support_parameters(path):
    result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                            text=True, capture_output=True, check=True)
    text = result.stdout
    title = re.search(r'Aluminum substrate for convex crystal\s+(\d+)x(\d+) R(\d+(?:\.\d+)?)', text)
    if title is None:
        raise ValueError('Cannot verify material/dimensions/radius in the O-2094 drawing.')
    return dict(substrate_material='Aluminum 2017A',
                substrate_dimensions_mm=[float(title[1]),float(title[2])],
                radius_m=float(title[3])/1000,
                crystal_material_specified=False, crystal_thickness_specified=False,
                crystal_hkl_specified=False,
                note='PDF describes the substrate, not a complete Ge crystal specification.')


def geometry(material, hkl, energy_kev, radius_m):
    crystal = xraylib.Crystal_GetCrystal(material)
    d = xraylib.Crystal_dSpacing(crystal, *hkl)
    energy = np.asarray(energy_kev,dtype=float)
    arg = HC_KEV_A / (2*d*energy)
    accessible = (arg > 0) & (arg < 1)
    angle = np.arcsin(np.where(accessible,arg,np.nan))
    return dict(angle_deg=np.degrees(angle), distance_m=radius_m/np.sin(angle),
                axial_source_to_focus_m=2*radius_m/np.tan(angle),
                angular_sensitivity_ev_per_mrad=energy/np.tan(angle),
                d_angstrom=d)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--voxes-script',type=Path,default=VOXES,help='verified current VOXES HAPG configuration')
    p.add_argument('--ge-support-pdf',type=Path,default=SUPPORT,help='O-2094 drawing: radius of the proposed Ge substrate')
    p.add_argument('--energy-kev',type=float,default=xraylib.EdgeEnergy(47,xraylib.K_SHELL),help='energy highlighted in the plot: Ag K edge')
    p.add_argument('--emin-kev',type=float,default=24.5,help='minimum plotted energy around the Ag K edge')
    p.add_argument('--emax-kev',type=float,default=26.5,help='maximum plotted energy around the Ag K edge')
    p.add_argument('--ge-hkl',type=int,nargs=3,action='append',default=argparse.SUPPRESS,
                   help='repeat for Ge planes; default: 220, 440, 660, 880')
    p.add_argument('--hapg-orders',type=int,nargs='+',default=[2,4,6,8],help='graphite (00l) reflections; 002 is current VOXES usage')
    p.add_argument('--points',type=int,default=1001,help='points on each energy curve')
    p.add_argument('--output',type=Path,default=HERE/'s3_final',help='output basename for PNG, CSV and JSON')
    a=p.parse_args()
    if not all(np.isfinite(v) for v in (a.emin_kev,a.emax_kev,a.energy_kev)) or not 0<a.emin_kev<a.emax_kev or not a.emin_kev<=a.energy_kev<=a.emax_kev:
        p.error('Require 0 < emin < emax and highlight energy inside the plotted range.')
    if a.points<10 or any(order<=0 or order%2 for order in a.hapg_orders):
        p.error('Require points >= 10 and positive even graphite orders.')
    ge_hkls=getattr(a,'ge_hkl',None) or [[n,n,0] for n in [2,4,6,8]]
    if any(not any(hkl) for hkl in ge_hkls):p.error('(000) is not a reflection.')
    hapg=voxes_parameters(a.voxes_script)
    ge=support_parameters(a.ge_support_pdf)
    energies=np.linspace(a.emin_kev,a.emax_kev,a.points)
    ka=xraylib.LineEnergy(47,xraylib.KA1_LINE)
    edge=xraylib.EdgeEnergy(47,xraylib.K_SHELL)
    cases=[]
    for i,hkl in enumerate(ge_hkls):
        cases.append(dict(name='Ge('+''.join(map(str,hkl))+')',material='Ge',hkl=hkl,
                          radius_m=ge['radius_m'],color=plt.cm.Blues(.45+.5*i/max(1,len(ge_hkls)-1)),
                          style='-',highlight=hkl==[8,8,0]))
    actual_hkl=[hapg[f'miller_index_{s}'] for s in 'hkl']
    for i,order in enumerate(a.hapg_orders):
        hkl=[0,0,order]
        cases.append(dict(name=f'HAPG(00{order})',material=hapg['material'],hkl=hkl,
                          radius_m=hapg['radius'],color=plt.cm.Oranges(.45+.4*i/max(1,len(a.hapg_orders)-1)),
                          style='--',highlight=hkl==actual_hkl))
    fig,ax=plt.subplots(figsize=(12.5,7.6))
    fig.subplots_adjust(left=.09,right=.72,bottom=.20,top=.79)
    rows=[]
    for case in cases:
        values=geometry(case['material'],case['hkl'],energies,case['radius_m'])
        selected=geometry(case['material'],case['hkl'],a.energy_kev,case['radius_m'])
        angle=float(selected['angle_deg'])
        if not np.isfinite(angle):p.error(f"{case['name']} is inaccessible at the highlighted energy.")
        row=dict(crystal=case['name'],hkl=case['hkl'],radius_mm=case['radius_m']*1000,
                 energy_kev=a.energy_kev,bragg_angle_deg=angle,
                 source_to_crystal_cm=float(selected['distance_m'])*100,
                 axial_source_to_focus_cm=float(selected['axial_source_to_focus_m'])*100,
                 angular_sensitivity_ev_per_mrad=float(selected['angular_sensitivity_ev_per_mrad']))
        rows.append(row)
        ax.plot(energies,values['angle_deg'],color=case['color'],ls=case['style'],
                lw=3 if case['highlight'] else 1.4,
                label=f"{case['name']}   {angle:.1f}° · {row['source_to_crystal_cm']:.0f} cm")
        ax.scatter(a.energy_kev,angle,s=65 if case['highlight'] else 24,
                   color=case['color'],zorder=5,edgecolor='white',linewidth=.6)
    ax.axvline(a.energy_kev,color='#334155',lw=1,alpha=.6)
    ax.text(a.energy_kev+.12,ax.get_ylim()[1]*.97,
            ('K-edge Ag · 25,514 keV' if abs(a.energy_kev-edge)<.001 else f'{a.energy_kev:g} keV'),
            va='top',color='#334155',fontsize=11)
    if a.emin_kev<edge<a.emax_kev and abs(edge-a.energy_kev)>.05:
        ax.axvline(edge,color='#64748b',ls=':',lw=1.2)
        ax.text(edge+.15,ax.get_ylim()[1]*.97,'K-edge Ag\n(energia incidente XAS)',
                va='top',color='#64748b',fontsize=10)
    ax.set(xlim=(a.emin_kev,a.emax_kev),ylim=(0,None),
           xlabel='Energia dei raggi X [keV]',ylabel='Angolo di Bragg [gradi]')
    ax.grid(alpha=.18)
    ax.spines[['top','right']].set_visible(False)
    ax.tick_params(labelsize=11)
    ax.xaxis.label.set_size(12); ax.yaxis.label.set_size(12)
    fig.text(.09,.94,'Perché Ge(880) attorno al K-edge dell’Ag?',fontsize=21,weight='bold',color='#0f172a')
    fig.text(.09,.885,'Angolo più grande → geometria più compatta e minore sensibilità agli errori angolari',fontsize=12.5,color='#334155')
    legend=ax.legend(loc='upper left',bbox_to_anchor=(1.02,1.015),frameon=False,
                     title=f'A {a.energy_kev:.2f} keV: angolo · distanza\nsorgente–cristallo',fontsize=10,
                     title_fontsize=10,labelspacing=1.)
    candidate=next((r for r in rows if r['hkl']==[8,8,0] and r['crystal'].startswith('Ge')),None)
    current=next((r for r,c in zip(rows,cases) if c['material']==hapg['material'] and c['hkl']==actual_hkl),None)
    if candidate and current:
        ratio=current['source_to_crystal_cm']/candidate['source_to_crystal_cm']
        sensitivity=current['angular_sensitivity_ev_per_mrad']/candidate['angular_sensitivity_ev_per_mrad']
        fig.text(.74,.225,f'Ge(880) vs HAPG attuale\nDistanza {ratio:.1f}× più corta\nSensibilità angolare {sensitivity:.1f}× minore',
                 fontsize=10.5,linespacing=1.6,color='#123d6a',
                 bbox=dict(boxstyle='round,pad=.8',facecolor='#eef5fc',edgecolor='none'))
    fig.text(.09,.115,f"R HAPG = {hapg['radius']*1000:g} mm (VOXES); R supporto Ge = {ge['radius_m']*1000:g} mm (O-2094)",fontsize=10,color='#475569')
    fig.text(.09,.073,'Geometria von Hamos ideale: L = R / sin θB. La curvatura focalizza; non cambia la legge di Bragg.',fontsize=10,color='#475569')
    fig.text(.09,.033,'Il grafico non predice efficienza o risoluzione finale. Strain, spessore e riflettività del Ge curvo restano da verificare.',fontsize=10,color='#475569')
    output=a.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output.with_suffix('.png'),dpi=240,facecolor='white')
    with output.with_suffix('.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    meta=dict(model='Ideal symmetric cylindrical von Hamos geometry; Bragg law with xraylib lattice spacings',
              source_files=[str(a.voxes_script.resolve()),str(a.ge_support_pdf.resolve())],
              voxes_hapg=hapg,ge_substrate=ge,
              ge_crystal_assumption='Ge material and candidate hkl requested by user; not specified by substrate drawing',
              actual_hapg_hkl=actual_hkl,
              hapg_higher_orders='Accessible reciprocal-lattice reflections, not separate crystal cuts or verified high-energy efficiencies',
              reference='Ag K absorption edge; not Ag Kalpha fluorescence',ag_kedge_kev=edge,
              formulas=dict(bragg='sin(theta)=hc/(2*d*E)',distance='L=R/sin(theta)',
                            sensitivity='abs(dE/dtheta)=E*cot(theta); tabulated in eV/mrad',
                            axial_focus='z=2*R*cot(theta); standard von Hamos only'),
              references=['https://doi.org/10.3390/condmat4020038',
                          'https://journals.iucr.org/a/issues/2012/01/00/wx0006/index.html'],
              settings={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},results=rows)
    output.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
    for row in rows:
        print(f"{row['crystal']:12s} {row['bragg_angle_deg']:6.2f} deg  L={row['source_to_crystal_cm']:7.2f} cm  dE/dtheta={row['angular_sensitivity_ev_per_mrad']:7.2f} eV/mrad")
    print(f'Saved {output}.png, .csv, .json')
    plt.show()


if __name__=='__main__':
    main()
