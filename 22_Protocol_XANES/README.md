# Protocollo XANES — Ag foil

`make` produce `Protocol_XANES.svg` direttamente dal sorgente TikZ/XDV con
dvisvgm, poi `Protocol_XANES.png` a 3300 px con Inkscape. L'SVG contiene solo
vettori, inclusi i caratteri convertiti in tracciati. Dipendenze: Python/NumPy,
XeLaTeX, font Arial, PGFPlots/TikZ, dvisvgm e Inkscape.

## Griglia concordata

Il requisito iniziale di 140 punti fra −5 e +70 eV non è compatibile con un
passo di 5 eV. Su indicazione dell'utente si mantiene il totale di circa 150
punti riducendo il passo fine. Qui si ottengono esattamente 150 energie:

- 10 punti grossolani a −105, −95, …, −15 eV rispetto a E0, passo 10 eV;
- 140 punti da −5 a +70 eV, estremi inclusi, passo esatto 75/139 eV
  (0,539568345… eV; 0,54 eV è soltanto l'arrotondamento grafico).

Il tratto grossolano copre una finestra di 100 eV da −105 eV fino all'inizio
della griglia fine a −5 eV; quest'ultimo punto appartiene solo alla griglia
fine. La soglia di riferimento è E0 = 25514 eV. La griglia uniforme fine
non include necessariamente un punto esattamente a E0.

`scan_grid.dat` contiene le 150 energie effettive, relative e assolute.
`protocol.json` contiene parametri e provenienza. Si acquisisce prima
l'intera scansione I e poi I0 sulla stessa griglia: 150 energie per ciascuna
scansione, 300 acquisizioni complessive se si effettua una acquisizione per
energia e per segnale. Tempi e ripetizioni non sono specificati.

Il vincolo ΔE_scansione < δE_cristallo è riportato come requisito da
verificare, non come risultato: non è stato fornito un valore della risoluzione
del cristallo. Vale anche per il passo grossolano di 10 eV.

## Curva di riferimento

Fonte locale: `../21_XANES_Ag/data/Ag_foil/Ag-K_Ag-foil_Si311_50ms_160624.txt`,
NIMS / SPring-8 BL14B2, DOI 10.48505/nims.1453. Si usa la stessa normalizzazione
di `../21_XANES_Ag/s1_ref_comparison.py`: baseline lineare tra −280 e −150 eV,
post-edge quadratico tra +150 e +700 eV, salto estrapolato a E0. Nessuno
spostamento energetico, smoothing o broadening è applicato alla curva.

La linea rappresenta i punti originali normalizzati; i marcatori della
scansione prevista sono posizionati mediante interpolazione lineare della
curva di riferimento, per illustrare il campionamento. Non sono nuovi dati
misurati né una previsione delle prestazioni PRISM. `Sketch.jpg` resta il
riferimento grafico originale dell'utente.
