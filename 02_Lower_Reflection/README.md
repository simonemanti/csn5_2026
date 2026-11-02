# Lower-order reflections of Ge(880)

This is a PRISM candidate-optics study supporting the design simulations. Ge(880)
has not yet been selected as the final crystal in the authoritative v2 proposal.

The default calculation studies a symmetric perfect Ge(880) crystal set to
20 keV. At the same physical orientation, the parallel planes are `n(110)`.
The Ge diamond-lattice extinction rules remove the odd orders, so the allowed
lower orders are:

| Reflection | Nominal energy at the Ge(880), 20 keV setting |
|---|---:|
| Ge(220) | 5 keV |
| Ge(440) | 10 keV |
| Ge(660) | 15 keV |
| Ge(880) | 20 keV |

Small energy shifts printed by the script come from the refraction-corrected
Bragg angle used by `crystalpy`.

Run in the requested environment:

```bash
conda run -n shadow4 python 2_Lower_Reflection/s1_reflection.py
```

The script produces PNG/PDF plots and a CSV table. It uses the same
`PerfectCrystalDiffraction` Guigay thick-crystal calculation called by
SHADOW4's `S4Crystal`. The plotted quantity is the unpolarized intrinsic
reflectivity, `(R_sigma + R_pi)/2`. The CSV reports both the angular integral
and its energy-equivalent value from `dE/dtheta = -E cot(theta)`. The lower
plot uses the latter because it is the more relevant throughput proxy for a
broadband laboratory source at a fixed crystal angle. It must still be
multiplied by the actual spectral flux and beamline transmission at each
energy.

Absolute output rates cannot be obtained from reflectivity alone. For each
order `i`, they require a source/beamline calculation of

```text
N_i = integral Phi(E,theta) R_i(E,theta) T(E) A(E,theta) dE dtheta,
```

where `Phi` is the incident spectral-angular flux, `T` contains windows,
filters and air paths, and `A` is the geometrical/detector acceptance. A full
SHADOW4 ray trace should therefore launch the actual polychromatic source and
compare the sum of statistical ray weights reaching the sample/detector in
bands around 5, 10, 15 and 20 keV.

For a CZT resolving time `tau`, the leading two-photon pile-up rates close to
20 keV are approximately

```text
P_440+440 = N_440^2 tau
P_220+660 = 2 N_220 N_660 tau
```

for low occupancy (`N_total tau << 1`). Use the measured effective resolving
time of the complete CZT plus shaping/DAQ chain, not just the sensor charge
collection time. Filters can strongly suppress 5 and 10 keV photons and must
be included before drawing a pile-up conclusion.

For fluorescence XAS the relevant ROI is normally the selected fluorescence
line, not the 20 keV incident energy. Check a different ROI with, for example,
`--pileup-roi 17.5 --pileup-tolerance 0.3`.

Limitations: this script models a flat, symmetric, perfect Ge crystal. Bending,
strain, Johann error, source divergence, finite apertures and crystal defects
must be included in the final SHADOW4 beamline model.

## Ag K-edge: Ge vs HAPG (`s2_ge_vs_hapg.py`)

```bash
conda activate shadow4-mosaics
python 02_Lower_Reflection/s2_ge_vs_hapg.py
python 02_Lower_Reflection/s2_ge_vs_hapg.py --ge-hkl 8 8 0 --hapg-hkl 0 0 2
python 02_Lower_Reflection/s2_ge_vs_hapg.py --ge-hkl 8 8 0 --hapg-hkl 0 0 8 --mosaic-fwhm-deg 0.1
python 02_Lower_Reflection/s2_ge_vs_hapg.py --help
```

I percorsi sopra sono relativi alla radice del progetto. Lo script salva PNG,
CSV delle curve (anche σ e π separatamente), JSON dei parametri/risultati e gli
input/log del calcolo in `s2_ge_vs_hapg_calculations/`. Chiama sempre `plt.show()`;
per una verifica senza display si può impostare `MPLBACKEND=Agg` (il backend
segnalerà che la finestra non è interattiva).

Gli indici sono specificati con tre interi; le opzioni `--ge-hkl` e `--hapg-hkl`
possono essere ripetute. Per default si confrontano Ge 220/440/660/880 e grafite
002/004/006/008. **Ogni riflessione viene allineata separatamente al massimo a
K-edge Ag (25,514 keV)**: non sono armoniche eccitate contemporaneamente nella stessa orientazione.
Con un solo hkl per materiale si possono impostare `--ge-angle-deg` e
`--hapg-angle-deg`, ossia i valori angolari immessi nella scansione in energia
XCRYSTAL, invece dell'allineamento automatico. Gli angoli scelti e gli spessori
effettivi sono registrati nel JSON.

### Parametri e modello

- Ge perfetto, spessore finito 1 mm: letto da
  `03_Simulations/config/wp1_geometry.json`. Nella proposta corrente
  `FINAL/Progetto.pdf` Ge(880) è il candidato baseline.
- HAPG rappresentato da grafite mosaica gaussiana, FWHM 0,1°: letta dal nodo
  HAPG del workflow `v1_Reflectivity.ows`.
- HAPG 100 µm: valore di modello già usato in
  `12_VOXES_Feasebility/s2_compare.py`, modificabile con
  `--hapg-thickness-um`. Quel precedente usa 100 µm per il cristallite perfetto:
  qui lo stesso valore è assunto come spessore totale del modello mosaico.
  **Non è una misura o una specifica certificata dello strato HAPG disponibile**;
  per previsioni quantitative di efficienza va verificato e sostituito.
- Stesso backend Fortran `diff_pat` e preprocessor `bragg_calc2` del widget
  OASYS2 XOPPY → Optics → CRYSTAL. Libreria predefinita xraylib; disponibile
  anche `--library dabax`. Fattore termico 1, geometria Bragg simmetrica piatta,
  polarizzazione non polarizzata `(Rσ + Rπ)/2` (selezionabili anche σ o π).

Il grafico è la risposta **a orientazione fissa** al variare dell'energia,
non la riflettività massima ottenuta riallineando il cristallo a ogni energia.
Un reticolo fitto attorno al picco risolve il Ge insieme alla finestra larga
necessaria all'HAPG. Le FWHM hanno precisione limitata anche dall'output testuale
Fortran (circa 0,001 eV in questa regione): per Ge(880) è appropriato riportare
circa 0,074 eV, senza interpretare le ultime cifre. L'integrale nel JSON è limitato
alla finestra selezionata, ±600 eV per default, e non è un conteggio di fotoni.

### Correzione della GUI salvata

Nel file originale `v1_Reflectivity.ows`:

1. Tutti i quattro nodi Ge hanno hkl=(220), anche quelli rinominati 440/660/880.
2. Tutti i CRYSTAL sono impostati a 10000 eV, non al K-edge Ag=25514 eV
   (energia da xraylib).
3. **Crystal Thickness è in cm**: 0,7 significa 7 mm. Per il modello corrente
   usare Ge=0,1 cm e HAPG=0,01 cm.
4. La scansione angolare ±100 µrad è troppo stretta per una mosaicità di 0,1°
   (1745 µrad FWHM). Per una rocking curve HAPG usare ad esempio ±0,4° con
   `Th - Th Bragg (corrected)` e unità Degrees; Ge richiede una scala più fine.
5. MARE calcola diffrazione multipla/diagrammi azimutali, non questo confronto
   quantitativo di bande passanti. Non serve collegarlo ai nodi CRYSTAL.

`v2_Ge_vs_HAPG_AgKa.ows` conserva il precedente studio alla Kα₁ e non segue
il nuovo riferimento K-edge di s2. Contiene gli otto CRYSTAL,
con indici, spessori e modello corretti e scansioni **Energy [eV]**. Il campo
**Fix value (E[eV] or Theta[deg])** contiene l'angolo trovato dallo script,
non 22162,9: nel modo Energy il valore fisso è Theta in gradi. Gli intervalli
sono ±5 eV per Ge e ±600 eV per HAPG, con 20001 punti, per risolvere i picchi.
Per confrontare la GUI con s2 aggiornare anche angoli e intervalli al K-edge
usando il nuovo JSON, e selezionare la stessa libreria xraylib;
la GUI mostra separatamente `s-polarized reflectivity` e
`p-polarized reflectivity`. La media delle due corrisponde alla curva di default.
Il file è stato verificato come configurazione salvata; non è stato eseguito
interattivamente nella GUI.

### Lettura per la motivazione dell'acquisto

Il confronto sostiene la **selettività energetica del Ge**, mentre il mosaico
HAPG accetta una banda e un flusso integrato maggiori. Per esempio il modello
predefinito dà Ge(880): picco ≈0,78, FWHM ≈0,074 eV; HAPG(002): picco ≈0,52,
FWHM ≈789 eV; HAPG(008): picco ≈0,008, FWHM ≈148 eV. Non normalizzare ogni
curva a uno se si vuole discutere anche l'efficienza. Il solo confronto non
stabilisce che 880 sia preferibile a ogni altro ordine Ge: bisogna includere
risoluzione richiesta, geometria, dispersione, accettanza e flusso.

Sono risposte intrinseche piatte, non la risoluzione finale del cristallo curvo:
curvatura/strain, dimensioni sorgente, fenditure, divergenza e posizione del
rivelatore richiedono il ray tracing e un modello di strain. Il confronto è ora
centrato sull'energia **incidente** della fluorescence-XAS al K-edge Ag,
25,514 keV, con finestra 24,914–26,114 keV (±600 eV). La riga Kα a 22,16 keV
non è più il riferimento dello script. Il bordo è soltanto un riferimento di
energia: non si moltiplica la riflettività per l'assorbimento del campione Ag.

Riferimenti del backend: [XCRYSTAL ESRF](https://ftp.esrf.fr/scisoft/xop2.3/doc/WebHelp/applications/optics/xcrystal.htm),
[modelli e ruolo di MARE](https://ftpext.esrf.fr/scisoft/xop2.3/doc/WebHelp/functions/x_ray_optics.htm).

## Grafico finale di motivazione: `s3_final.py`

```bash
conda activate shadow4-mosaics
python 02_Lower_Reflection/s3_final.py
# Evidenziare un punto appena sopra soglia:
python 02_Lower_Reflection/s3_final.py --energy-kev 25.52 --output /tmp/s3_ag_edge
```

Produce un **solo grafico**, PNG, una tabella CSV e un JSON delle fonti/parametri.
Legge senza eseguire il workflow attuale
`/home/smanti/WORK/VOXES/RAY-TRACING/07_VOXES_Single_Spectrum/s1_compare_GUI.py`:
HAPG(002), spessore totale nel modello 100 µm, FWHM mosaico gaussiana 0,1°,
curvatura cilindrica R=206,7 mm. È quindi un riscontro del modello VOXES attuale,
non soltanto lo spessore di cristallite assunto nel precedente confronto Fe.
I parametri restano nominali di simulazione, non una nuova misura del pezzo.

Il disegno O-2094 specifica **un supporto in alluminio 2017A da 52×27 mm,
R=206 mm**; il nome del file menziona un analizzatore 50×25 mm, ma il cartiglio
riguarda il supporto. Il disegno non definisce materiale, spessore, orientazione
cristallografica, faccia riflettente o strain del wafer. Nel calcolo si applica
la curvatura del supporto al candidato Ge richiesto, senza inventarne lo spessore.
La concavità della faccia ottica e la compatibilità del montaggio devono essere
verificate sul disegno dell'assieme, non dedotte dal solo supporto.

Si confronta la **geometria cilindrica ideale**, con

```
sin(theta_B) = hc/(2*d_hkl*E)
L_sorgente-cristallo = R/sin(theta_B)
abs(dE/dtheta) = E*cot(theta_B)
```

Il riferimento corretto di `s3_final.py` è il **K-edge Ag = 25,514 keV**,
con finestra predefinita **24,5–26,5 keV**. Si tratta della regione di energia
incidente XAS, non della fluorescenza Kα. A 25,514 keV si ottengono:

| Riflessione | θB | L sorgente-cristallo | Sensibilità per errore angolare identico |
|---|---:|---:|---:|
| HAPG(002), attuale | 4,16° | 284,8 cm | 350,6 eV/mrad |
| HAPG(008) | 16,88° | 71,2 cm | 84,1 eV/mrad |
| Ge(660) | 21,37° | 56,5 cm | 65,2 eV/mrad |
| Ge(880) | 29,07° | 42,4 cm | 45,9 eV/mrad |

La minore sensibilità vale a parità di **errore angolare**; non è un guadagno
universale di risoluzione a parità di dimensione sorgente o pixel. Confrontare
880 con 660 mostra un miglioramento più moderato di quello rispetto a HAPG002:
circa 25% meno distanza e 30% meno sensibilità angolare. L'efficienza integrata
intrinseca diminuisce salendo d'ordine e va bilanciata con questi vantaggi.
Non si dimostra così un optimum globale: ordini più alti o altri tagli esistono.

Ge(220), (440), (660), (880) sono paralleli: possono essere armoniche dello
stesso cristallo orientato nella famiglia (110); non implicano quattro differenti
orientazioni della superficie. Selezionare l'ordine richiede anche il controllo
delle armoniche/lower orders. Per il Ge curvo servono una verifica meccanica e
un modello diffrattivo con spessore, orientazione elastica e condizioni di
incollaggio/montaggio, ad esempio Takagi–Taupin. Il ray tracing geometrico da
solo non introduce automaticamente lo strain e non certifica una Darwin width
da 0,06 eV per l'ottica reale.

### Darwin width: convenzione adottata

Per un cristallo perfetto, spesso, simmetrico e idealmente non assorbente,
la Darwin width angolare è l'intervallo di **riflessione totale** della teoria
dinamica, corrispondente al parametro di deviazione -1 ≤ η ≤ 1. Per ciascuna
polarizzazione:

```
Delta_theta_D = 2 |C| sqrt(|chi_h chi_-h|) / |sin(2 theta_B)|
C_sigma = 1; C_pi = cos(2 theta_B)
Delta_E_D ~= E |cot(theta_B)| Delta_theta_D   [theta in radianti]
```

È distinta dalla FWHM della curva completa: nell'ideale non assorbente la FWHM
è 3/(2 sqrt(2)) ≈ 1,061 volte la larghezza di riflessione totale. In presenza di
assorbimento, spessore finito o miscela delle polarizzazioni si misura la FWHM
del profilo effettivamente calcolato. I valori in eV di `s2_ge_vs_hapg.py` sono
queste **FWHM delle risposte intrinseche in energia**, non una risoluzione
strumentale e non automaticamente la Darwin width nella convenzione sopra.
La mosaicità dell'HAPG è un'altra larghezza: la FWHM della distribuzione delle
orientazioni dei microcristalliti. La sua accettanza non coincide con la
risoluzione di un intero spettrometro von Hamos, dove interviene il mosaic
focusing.

Fonti: [teoria dinamica IUCr](https://journals.iucr.org/a/issues/2012/01/00/wx0006/index.html),
[VOXES HAPG e geometria](https://doi.org/10.3390/condmat4020038),
[esempio von Hamos Si/Ge segmentato](https://doi.org/10.1063/5.0133896),
[effetto dello strain da curvatura](https://pubs.rsc.org/en/content/articlehtml/2019/ja/c9ja00159j).
