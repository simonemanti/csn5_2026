#!/usr/bin/env python3
"""Render a schematic animation of switching between fluorescence and I0."""
import argparse
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
p.add_argument('--fps', type=int, default=12, help='frames per second')
p.add_argument('--width', type=int, default=1120, help='output width in pixels')
args = p.parse_args()
if args.fps < 1 or args.width < 100:
    p.error('fps must be positive and width must be at least 100')
work = ROOT / '.build'
work.mkdir(exist_ok=True)
def run(*cmd):
    subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
def smooth(t):
    t = min(1., max(0., t))
    return t*t*(3-2*t)
header = r'''\documentclass[multi=tikzpicture,border=0pt]{standalone}
\usepackage{fontspec}\usepackage{tikz}\usepackage{amsmath,bm}
\setsansfont{Arial}\usetikzlibrary{arrows.meta,calc}
\definecolor{ink}{HTML}{17365D}\definecolor{beamgreen}{HTML}{2CA02C}
\definecolor{fluororange}{HTML}{FF7F0E}\definecolor{detectorblue}{HTML}{1F77B4}
\definecolor{samplegray}{HTML}{7F7F7F}\definecolor{motioncyan}{HTML}{008FA8}
\begin{document}
'''
frames = []
# 1.5 s at each endpoint; 2 s for each direction; seamless loop.
for i in range(7 * args.fps):
    t = i / args.fps
    state = 0. if t < 1.5 else smooth((t-1.5)/2) if t < 3.5 else 1. if t < 5. else 1-smooth((t-5)/2)
    angle = math.pi/2 * (1-state)
    x, y = 4+2.55*math.cos(angle), 2.55*math.sin(angle)
    # Detector's sensitive face follows the sample as it rotates around it.
    rot = -90*state
    sample_y = 1.75*state
    fl = 1-smooth(state/0.38)
    direct = smooth((state-0.62)/0.38)
    frames.append(r'''\begin{tikzpicture}[x=1cm,y=1cm,line join=round,line cap=round,
 every node/.style={font=\sffamily\fontsize{12}{14}\selectfont,text=ink},
]
\newcommand{\BeamArrow}[4]{%
  \begin{scope}
    \coordinate (beamStart) at #3;
    \coordinate (beamEnd) at #4;
    \path let \p1 = ($(beamEnd)-(beamStart)$),
      \n1 = {atan2(\y1,\x1)}, \n2 = {veclen(\x1,\y1)} in
      \pgfextra{\xdef\beamAngle{\n1}\xdef\beamLength{\n2}};
    \begin{scope}[shift={(beamStart)},rotate=\beamAngle]
      \path[fill=#1,draw=black,opacity=#2,line width=.35mm,line join=round]
        (0,-1.2mm) -- (\beamLength-3.5mm,-1.2mm)
        -- (\beamLength-3.5mm,-2.5mm) -- (\beamLength,0)
        -- (\beamLength-3.5mm,2.5mm) -- (\beamLength-3.5mm,1.2mm)
        -- (0,1.2mm) -- cycle;
    \end{scope}
  \end{scope}
}
\path[use as bounding box] (-1.05,-1.25) rectangle (12.8878,4.35);
\node[anchor=west,font=\sffamily\bfseries\fontsize{14}{17}\selectfont] at (-.72,3.9) {Switching between $\bm{I_f}$ and $\bm{I_0}$};
\draw[ink!75,line width=.8pt,-{Stealth[length=2mm]}] (-.58,2.25) -- (.17,2.25) node[anchor=west,font=\sffamily\fontsize{11}{13}\selectfont] {$x$};
\draw[ink!75,line width=.8pt,-{Stealth[length=2mm]}] (-.58,2.25) -- (-.58,2.9) node[anchor=east,font=\sffamily\fontsize{11}{13}\selectfont] {$z$};
\BeamArrow{beamgreen}{OPINC}{(.45,0)}{(3.68,0)}
\node at (1.75,.48) {X-ray beam};
\BeamArrow{beamgreen}{OPDIR}{(.45,0)}{(5.98,0)}
\BeamArrow{fluororange}{OPFL}{(4,.35)}{(4,2.03)}
\node[opacity=OPFL,anchor=west] at (4.35,1.25) {$\bm{I_f}$};
\node[opacity=OPDIR] at (5.25,.48) {$\bm{I_0}$};
\begin{scope}[shift={(4,SAMPLE)}]
\path[draw=samplegray,fill=samplegray!35,line width=.8pt] (-.43,-.47) -- (-.29,-.57) -- (.43,.47) -- (.29,.57) -- cycle;
\end{scope}
\node[anchor=west,font=\sffamily\fontsize{10}{12}\selectfont] at (4.5,SAMPLELABEL) {Sample};
\begin{scope}[shift={(DX,DY)},rotate=ROT,transform shape]
\node[draw=detectorblue,fill=detectorblue!13,line width=1pt,minimum width=1.45cm,minimum height=.72cm,inner sep=2pt,font=\sffamily\bfseries\fontsize{13}{15}\selectfont] {CZT};
\end{scope}
\node[opacity=OPFL,font=\sffamily\bfseries\fontsize{13}{15}\selectfont,text=motioncyan] at (9.4,2.2) {Fluorescence};
\node[opacity=OPDIR,font=\sffamily\bfseries\fontsize{13}{15}\selectfont,text=motioncyan] at (9.4,2.2) {Incident beam};
\end{tikzpicture}
'''.replace('OPINC',f'{1-direct:.4f}').replace('OPDIR',f'{direct:.4f}').replace('OPFL',f'{fl:.4f}').replace('SAMPLELABEL',f'{sample_y-.72:.4f}').replace('SAMPLE',f'{sample_y:.4f}').replace('DX',f'{x:.4f}').replace('DY',f'{y:.4f}').replace('ROT',f'{rot:.4f}'))
tex = work/'animation.tex'
tex.write_text(header + ''.join(frames) + '\\end{document}\n')
run('xelatex','-interaction=nonstopmode','-halt-on-error','-output-directory=.build',str(tex))
run('/usr/bin/pdftoppm','-png','-scale-to-x',str(args.width),'-scale-to-y','-1','-r','120','.build/animation.pdf','.build/frame')
run('ffmpeg','-y','-loglevel','error','-framerate',str(args.fps),'-i','.build/frame-%02d.png','-vf','scale=trunc(iw/2)*2:trunc(iw*4.5/11.2/2)*2,format=yuv420p','-c:v','libx264','-crf','18','-movflags','+faststart','switching.mp4')
run('ffmpeg','-y','-loglevel','error','-i','switching.mp4','-filter_complex','fps=12,scale=896:360:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse','-loop','0','switching.gif')
print(f'Created {ROOT / "switching.mp4"} and {ROOT / "switching.gif"}')
