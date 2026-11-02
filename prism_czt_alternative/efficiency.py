from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import xraylib as xl
out=Path(__file__).parent
E=np.linspace(10,50,801)
comp={'Cd':.9,'Zn':.1,'Te':1}
mass=sum(n*xl.AtomicWeight(xl.SymbolToAtomicNumber(e)) for e,n in comp.items())
weights={e:n*xl.AtomicWeight(xl.SymbolToAtomicNumber(e))/mass for e,n in comp.items()}
def mu_czt(e):return sum(w*xl.CS_Total(xl.SymbolToAtomicNumber(z),e)for z,w in weights.items())
def eff(mu,rho,t):return 100*(-np.expm1(-np.array(mu)*rho*t))
curves=[('Si SDD · 450 µm',eff([xl.CS_Total(14,e)for e in E],2.33,.045),'#e63946'),('HPGe · 1 mm',eff([xl.CS_Total(32,e)for e in E],5.32,.1),'#2786b3'),('CZT · 2 mm',eff([mu_czt(e)for e in E],5.8,.2),'#249a46')]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.labelcolor':'#002a48','xtick.color':'#002a48','ytick.color':'#002a48'})
fig,ax=plt.subplots(figsize=(5.4,3.7))
for label,ys,c in curves:ax.plot(E,ys,label=label,c=c,lw=2.4)
ax.axvline(22.2,color='#002a48',lw=1.2,ls='--',alpha=.7)
ax.text(23,55,'Ag Kα\n22.2 keV',fontsize=11,color='#002a48',va='center')
ax.set(xlim=(10,50),ylim=(0,105),xlabel='Photon energy (keV)',ylabel='Interaction efficiency (%)')
ax.set_yticks([0,25,50,75,100]);ax.grid(axis='y',alpha=.18);ax.spines[['top','right']].set_visible(False)
ax.legend(loc='center right',frameon=False,fontsize=10)
fig.tight_layout(pad=.7)
fig.savefig(out/'efficiency.png',dpi=250)
fig.savefig(out/'efficiency.pdf')
print('Ag Kalpha Si efficiency:',eff([xl.CS_Total(14,22.2)],2.33,.045)[0])
print('Ag Kalpha CZT efficiency:',eff([mu_czt(22.2)],5.8,.2)[0])
plt.show()
