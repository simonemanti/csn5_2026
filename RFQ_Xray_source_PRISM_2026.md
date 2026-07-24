# PRISM - shortlist e richieste di quotazione per sorgente X sopra 20 keV

> **Status rispetto alla proposta:** il documento esplora uno specifico scenario
> HAPG/von Hamos successivo alla v2. La fonte autorevole corrente è
> `VERSIONS/v2_Proposal_Grant_Giovani_2026-2.pdf`, che non ha ancora congelato
> cristallo e geometria. Le conclusioni qui riportate sono quindi input al WP di
> simulazione e alla futura selezione, non requisiti già approvati del progetto.

Data della ricerca: 14 luglio 2026  
Scadenza operativa per ricevere le offerte: 28 luglio 2026  
Budget di riferimento: 40 kEUR complessivi; chiedere sempre prezzo netto, IVA, trasporto e installazione separati.

## Esito in breve

Lo scenario studiato in questa nota è una geometria **von Hamos dispersiva con cristallo HAPG cilindricamente curvato**. La sua compatibilità con la fluorescence-XAS PRISM deve essere dimostrata esplicitando come l'energia incidente sul campione viene scansita o codificata e ricostruita. In questo scenario la sorgente deve massimizzare i fotoni utili accettati dall'intera ottica e dalla banda simultanea, non semplicemente avere lo spot più piccolo.

La scelta raccomandata è un anodo di tungsteno (W), non Mo/Rh/Ag. Per massimizzare il flusso occorre chiedere subito due classi prestazionali, entrambe molto superiori ai 75-100 W inizialmente considerati:

1. **Massimo flusso a 20-30 keV:** tubo da diffrazione W **60 kV/2 kW a fuoco lineare**, candidato **KeyWay KYW600 normal-focus** (line focus apparente 0,1 x 10 mm), con generatore, tube hood e raffreddamento **xHuber 60 kV/3,5 kW**. A 40 kV il punto nominale è 50 mA/2 kW. È la configurazione da confrontare direttamente con Yamamoto e LynXes.
2. **Massimo flusso con estensione 20-50 keV:** generatore **Spellman DXM100, 100 kV/1,2 kW** più tubo W water-cooled da almeno 1 kW continuo e fuoco apparente compatibile con von Hamos (lineare preferito; in alternativa <=1 mm). I Comet MXR dimostrano la disponibilità della classe 1-3 kW, ma i modelli standard MXR101/MXR100-12 hanno spot di diversi millimetri: vanno quotati solo in variante small/line-focus o dopo ray tracing.
3. **Backup integrato più credibile nel cap:** **Spellman XRB100PN500HR**, 100 kV/500 W, cone beam e spot opzionale 0,5 mm; target W e rating continuo devono comparire nell'offerta.
4. **Fase 0/backup a basso rischio:** riuso uXHP65P100 con Micro X-Ray W o rtw MCBH. Serve alla validazione, ma non è la sorgente “massimo flusso”.

Il cap di 40 kEUR per una sorgente completa da 1-2 kW è **da verificare con RFQ**, non un prezzo di mercato già dimostrato. Se nessuna configurazione kW rientra nel cap, la gerarchia diventa XRB100PN500HR, poi XRB80PN320, mantenendo la predisposizione meccanica e di cooling per il futuro upgrade kW.

Non ci sono prezzi pubblici affidabili per questi prodotti: le pagine ufficiali mostrano “Get/Request a Quote”. Di conseguenza, i 40 kEUR sono un **cap da inserire nella RFQ**, non una stima di prezzo già verificata.

## Requisito ricavato dai documenti

La v2 del proposal PRISM richiede XAS in fluorescenza oltre 20 keV, fino a 50 keV, con CZT multicanale, risoluzione sub-keV e QE >90% fino a circa 40 keV (`VERSIONS/v2_Proposal_Grant_Giovani_2026-2.pdf`).

I lavori locali rendono credibile e conservativa la scelta von Hamos:

- `SANDBOX/Praetz_2025_OperandoLaboratory.pdf` dimostra una piattaforma scan-free con tubo microfocus 30 W/70 x 70 um, HAPG curvo e rivelatore 2D: campione a circa 8 cm dalla sorgente, circa 500 eV di banda XANES o 1500 eV EXAFS e acquisizioni di 5-25 min;
- `SANDBOX/Praetz_2026_OperandoLaboratory.pdf` usa esplicitamente un tubo **rtw MCBI50B-70Mo**, HAPG cilindrico ed EIGER2 R500K, con spettri Ni K in 5-15 min;
- lo scenario di upgrade valutato in questa nota conserva la stessa architettura dispersiva e aumenta potenza, energia, efficienza HAPG e rivelazione CZT. La continuità con questi lavori è un vantaggio, ma non sostituisce la validazione quantitativa rispetto alle altre geometrie candidate.

Il benchmark Yamamoto usa un generatore open-tube W a:

- 27 kV x 50 mA per Pb L3;
- 30 kV x 50 mA per Br K;
- 40 kV x 50 mA, cioè circa 2 kW, per Ag K a 25,514 keV;
- monocromatori Johann/Johansson R = 320 mm, incluso Ge(880);
- Xe proportional counter per I0 e scintillatore da 1,5 pollici in trasmissione.

Il risultato Ag K-edge con Ge(880) richiede circa 12 h e l'EXAFS non è praticabile per il basso rate. Lo stesso articolo identifica come upgrade un rivelatore energy-dispersive di grande area. Il limite principale non è solo la risoluzione: Ge(880) porta componenti indesiderate da Ge(220), Ge(440), Ge(660) e righe Ge K; il filtro Al riduce il problema ma non elimina bene la componente a 19,2 keV.

Ne segue che “migliore di Yamamoto” deve significare:

- intervallo energetico dimostrato oltre Ag K-edge, idealmente fino a 40-50 keV;
- XAS in fluorescenza, non solo trasmissione;
- discriminazione in energia sul CZT e sul monitor I0;
- soppressione armoniche progettata nell'ottica, non demandata solo a un filtro Al;
- tempo Ag K-edge XANES inferiore a 12 h a parità di qualità, come milestone misurata e non promessa a priori.

## Perché W è il target preferito

- Il continuum di bremsstrahlung cresce con Z: W (Z=74) offre più continuum di Mo (Z=42) a parità di kV e W elettrici.
- Con 60-65 kV non si eccitano le righe K del W (soglia circa 69,5 keV); le righe L del W sono sotto circa 12 keV e si filtrano facilmente rispetto alla banda 20-50 keV.
- Il Mo in-kind produce righe K circa 17,5 e 19,6 keV, proprio sotto il Mo K-edge. Yamamoto mostra inoltre un artefatto associato alla riga Mo Kbeta3 a 19,59 keV attraverso una riflessione di ordine superiore.
- Rh, Pd e Ag hanno righe K dentro o molto vicine alla banda 20-27 keV e sono meno adatti a una sorgente “bianca” generalista per Mo/Rh/Ag/Cd XAS.
- A 100 kV compaiono le righe K del W a circa 59-67 keV, sopra la banda PRISM; vanno comunque considerate nello shielding e controllate con soglia superiore sul detector.

## Opzione A - riuso dello Spellman uXHP65P100

### Vincoli elettrici verificati

Il manuale locale `SANDBOX/uXHPMAN_Power_Supply.pdf` identifica la famiglia uXHP come:

- uscita positiva per tubi a catodo a massa;
- 50/65/80 kV, 5 mA massimi, limitata a 100 W;
- filamento 0,3-3,5 A, 5 V massimo;
- ritorno filamento da riportare al pin FIL RETURN, non da mettere a massa esternamente;
- per la variante 65 kV: connettore HV tipo banana salvo opzioni K5302/K2001/XCC.

La pagina ufficiale Spellman conferma che uXHP è destinato a tubi a catodo a massa di Varex, Kevex, Oxford, RTW, Superior e Trufocus ed è stato sviluppato con Varex per VF-80J: [Spellman uXHP](https://www.spellmanhv.com/en/high-voltage-power-supplies/uXHP).

La compatibilità deve comunque essere dichiarata per **numero di modello, seriale e opzioni** dell'unità in-kind. Non basta che il tubo appartenga alla stessa famiglia.

### A1 - rtw MCBH 80B-0,5 W

Specifiche ufficiali:

- catodo a massa, anodo alimentato a +HV;
- +80 kV, 100 W continui;
- target W;
- spot 0,5 mm, anodo 12 gradi, emissione 30 gradi;
- raffreddamento ad aria, acqua o conduzione;
- cavo HV incluso e adattabile al generatore/filamento richiesto;
- privo di schermatura X integrata.

Fonte e contatto: [rtw MCBH](https://rtwxray.de/index.php?id=catalog&list=tubes&part=MCBH), `rtw@rtwxray.de`, +49 3342 84 200.

Uso previsto sul supply in-kind: massimo 65 kV/100 W, quindi corrente massima operativa 1,538 mA a 65 kV. Chiedere curva di emissione e garanzia di funzionamento continuo esattamente in questo punto.

**Vantaggio:** sfrutta tutti i 100 W e ha compatibilità di principio con polarità positiva/catodo a massa.  
**Rischio:** spot dieci volte più grande del Micro X-Ray attuale; servono ray tracing e/o slit sorgente. Housing, collimatore e schermatura vanno inclusi nella quotazione.

### A2 - Micro X-Ray Packaged Tube, W, filamento 2,0 A

Specifiche ufficiali:

- catodo a massa;
- 60 kV, 75 W;
- filamento 1,7 o 2,0 A; fino a 5 mA con versione 2,0 A, restando nel limite di potenza;
- spot 50 um +/-50%;
- target Mo, W, Rh o Cu, altri su richiesta;
- angolo fascio 25 o 40 gradi;
- finestra 127 um;
- raffreddamento ad aria, 150 CFM raccomandati, thermal switch a 70 C;
- cavo HV e filamento inclusi, pacchetto schermato e isolato.

Fonte e contatto: [Micro X-Ray packaged tube](https://microxray.com/products/mini-focus-packaged-x-ray-tube/), `support@microxray.com`, +1 831 207 4900. Datasheet: [Packaged X-Ray Tube](https://microxray.com/wp-content/uploads/2025/07/Packaged-X-Ray-Tube.pdf).

**Vantaggio:** stesso involucro/famiglia dell'in-kind, spot piccolo, rischio meccanico minore; W dà circa 1,76 volte il continuum di Mo nel modello Kramers a pari potenza/tensione.  
**Rischio:** nessun miglioramento di tensione o potenza rispetto al tubo attuale; non è la soluzione finale credibile per 50 keV.

### A3 - Varex VF-80J, target W, tube-only

Specifiche ufficiali del sottosistema VF-80/uXHP:

- 20-80 kVp, 100 W, massimo 4 mA;
- target W, Rh, Pd; Mo/altro su richiesta;
- finestra Be 75 um;
- spot tipico 1,0 mm;
- filamento massimo 3,3 A/2,8 V;
- raffreddamento ad aria;
- stabilità dichiarata 0,05% in 8 h dopo warm-up.

Fonte e RFQ: [Varex VF-80/uXHP](https://www.vareximaging.com/solutions/vf-80-uxhp/), datasheet [VF-80/uXHP PDF](https://www.vareximaging.com/wp-content/uploads/2022/04/VF-80_uXHP-PDS-1.pdf).

**Vantaggio:** VF-80J e uXHP sono stati sviluppati come coppia e testati come sottosistema.  
**Rischio:** la brochure descrive l'accoppiamento con generatore 80 kV; chiedere esplicitamente se il **tube-only VF-80J** può essere collegato al vostro uXHP65P100 senza modifica di connettore, cavo e controllo filamento. Lo spot da 1 mm penalizza la risoluzione/etendue se non gestito.

### Ordine di preferenza per A

| Priorità | Candidato | Scelta se... | Stop/go |
|---|---|---|---|
| A1 | rtw MCBH 80B-0,5 W | si privilegia flusso 20-40 keV | go solo con certificato rtw di compatibilità e housing incluso |
| A2 | Micro X-Ray W/2,0 A | si privilegiano spot 50 um, semplicità e rischio minimo | go per fase Mo-Rh-Ag-Cd; non dichiararlo sufficiente a 50 keV |
| A3 | Varex VF-80J W | si vuole una coppia storicamente progettata con uXHP | go solo con conferma sulla specifica unità 65P100 e studio spot da 1 mm |

## Opzione B - tubo e alimentatore nuovi

### B1 - rtw MCBH 100B-0,5 W + Spellman XLG100P100/FL

Questa combinazione resta una baseline a componenti separati, ma **non** è la scelta massimo flusso: XLG100P100 è limitato a 1 mA, quindi eroga soltanto 40 W a 40 kV e 50 W a 50 kV. Anche XLG100P200 arriverebbe a soli 80 W a 40 kV. Va quotata solo come confronto a basso rischio/costo.

Tubo rtw:

- +100 kV, 100 W, target W;
- catodo a massa;
- spot 0,5 mm, emissione 30 gradi;
- cavo incluso e connettore adattabile;
- raffreddamento aria/acqua/conduzione;
- housing/schermatura non inclusi di serie.

Alimentatore Spellman:

- modello di riferimento **XLG100P100**;
- +100 kV, 1 mA, 100 W;
- filamento riferito a massa, hot anode, polarità positiva;
- opzione FL 3 A/3 V o FH 9 A/3 V da scegliere insieme al catodo rtw;
- stabilità 0,01%/8 h dopo mezz'ora, cavo HV 3,3 m;
- componente OEM da installare in un sistema, non apparecchio stand-alone.

Fonte e RFQ: [Spellman XLG](https://www.spellmanhv.com/en/high-voltage-power-supplies/XLG). Contatto Italia: +39 0464 668 187, `hvsales@spellmanhv.co.uk` ([uffici Spellman](https://www.spellmanhv.com/en/Contact-Us/Find-your-closest-Sales-Office)).

Richiedere una **offerta congiunta o due lettere di compatibilità incrociate** che definiscano: catodo/filamento, cavo, connettore, resistenza serie, preheat, emission curve, interlock e protocollo di conditioning.

### B2 - Spellman XRB100N100 Monoblock

- tubo W a anodo fisso;
- 40-100 kV, 0,1-1 mA, 100 W continui;
- spot 0,5 mm;
- fascio a ventaglio 74 x 10 gradi;
- supply, filamento, tubo, beam port e controllo integrati;
- controllo analogico e RS-232.

Fonte/RFQ: [Spellman XRB100N100](https://www.spellmanhv.com/en/high-voltage-power-supplies/XRB100N100).

È la baseline più semplice per arrivare a 100 kV. Chiedere opzione/custom beam port che illumini l'intero cristallo alla distanza di progetto, spettro e flusso ai 20,0/25,5/30/40/50 keV, e attenuazione dovuta a Lexan/olio/vetro.

### B3 - Spellman XRB100PN210HR, 350HR o 500HR

- famiglia 100 kV con 210, 350 o 500 W;
- spot 0,8 mm standard, 0,5 mm opzionale;
- fascio conico 40 gradi opzionale;
- controllo RS-232/Ethernet, data logging e seasoning automatico;
- garanzia dichiarata 3 anni.

Fonte/RFQ: [Spellman XRBHR](https://www.spellmanhv.com/en/high-voltage-power-supplies/XRBHR).

Richiedere in una sola RFQ i prezzi XRB100PN210HR, 350HR e **500HR** con target W, spot 0,5 mm e cone beam. Per il massimo flusso la 500HR è la scelta raccomandata se entra nel cap 40 kEUR. La tabella pubblica indica fino a 8 mA per il modello 500HR: a 40 kV è quindi limitato a 320 W e raggiunge 500 W da 62,5 kV. Target e potenza continua vanno confermati nell'offerta.

### B4 - Spellman XRB80PN320

- 40-80 kV, 0,5-4 mA, 320 W continui;
- target W, spot 0,8 mm;
- fascio a ventaglio 80 x 10 gradi;
- heat exchanger con pompa olio e ventola;
- massa massima 54,4 kg.

Fonte/RFQ: [Spellman XRB80PN320](https://www.spellmanhv.com/en/high-voltage-power-supplies/XRB80PN320).

È la verifica di mercato più utile per massimizzare il flusso tra 20 e 40 keV. A 50 keV ha meno margine della versione 100 kV e l'integrazione è più pesante.

### B5 - Spellman uXRB130P65 / Thermo Fisher PXS10

- 20/45-130 kV, fino a 0,5 mA e 65 W;
- target W;
- spot minimo 6-8 um, tipicamente 16 W o meno per spot piccolo;
- 53 gradi standard, 115 gradi wide beam;
- tubo, HV e controllo integrati; RS-232.

Fonti/RFQ: [Spellman uXRB130P65](https://www.spellmanhv.com/en/high-voltage-power-supplies/uXRB130P65) e [Thermo Fisher PXS10](https://www.thermofisher.com/order/catalog/product/PXS10). Thermo Fisher indica fino a 48 h per la risposta alla richiesta di quotazione sulla pagina della famiglia sorgenti.

È il miglior confronto per risoluzione geometrica e margine a 50 keV, ma non per flusso: la potenza piena di 65 W è raggiunta a 130 kV e alle tensioni inferiori il limite può essere 16/40 W secondo configurazione.

### B6 - Malvern Panalytical 90 kV microfocus con generatore dedicato

La famiglia ufficiale offre 60, 90 e 160 kV, spot 10-50 um e generatore HV dedicato da rack 19 pollici: [Malvern Panalytical Microfocus Tube](https://www.malvernpanalytical.com/en/products/category/x-ray-tubes/x-rayindustrialtubes/microfocustube).

Chiedere target W, potenza continua a 90 kV, corrente, geometria, spessore finestra, stabilità e prezzo. La potenza non è pubblicata, quindi questa è una RFQ di confronto e non una scelta già qualificata.

## Opzione C - sorgenti massimo flusso per von Hamos

### C1 - KeyWay KYW600 W 60 kV/2 kW + generatore xHuber 3,5 kW

La pagina ufficiale [KeyWay KYW600](https://www.keyway-china.com/keyway-product/kyw600-diffraction-tube-series%C2%A0.html) dichiara, per target W/Mo/Cu/Ag:

- 60 kV massimi e 2 kW nominali nella versione normal-focus;
- area reale 1 x 10 mm, line focus apparente 0,1 x 10 mm e point focus 1 x 1 mm;
- versione fine-focus da 1 kW con line focus 0,04 x 8 mm;
- configurazioni custom; contatto `service@keyiwei.com`.

Il generatore ufficiale [xHuber 60 kV/3,5 kW](https://www.xhuber.com/en/products/4-accessories/43-beam/x-ray-sources/generators/) fornisce fino a 60 kV, 80 mA e 3,5 kW e può essere fornito con tube hood, tubazioni e controllo acqua. Il punto richiesto è 40 kV/50 mA = 2 kW, continuo.

**Perché è la prima RFQ:** il fuoco lineare è coerente con la direzione non dispersiva di von Hamos e la potenza eguaglia Yamamoto e LynXes, mantenendo più headroom di tensione. A 25,5 keV il semplice screening Kramers dà circa 47 volte il tubo Mo in-kind e 1,6 volte Yamamoto W 40 kV/2 kW.

**Gate:** KeyWay e xHuber devono firmare la compatibilità incrociata o uno dei due deve assumere la responsabilità del sottosistema completo. Richiedere CE, shielding, shutter, chiller, acceptance test, curva di derating, lifetime e supporto europeo. Il prezzo entro 40 kEUR non è verificato.

### C2 - Spellman DXM100 1,2 kW + tubo W water-cooled small/line-focus

Il [Spellman DXM100](https://www.spellmanhv.com/en/high-voltage-power-supplies/DXM100) offre 100 kV, 12 mA e 1,2 kW, uscita negativa per tubo a filamento flottante e alimentazione filamento fino a 5 A/10 V. La corrente massima rimane 12 mA: 480 W a 40 kV, 600 W a 50 kV e 1,2 kW a 100 kV.

Come riferimento di disponibilità della classe di potenza, [Comet MXR101](https://xray.comet.tech/en/products/mxr-101) è 100 kV/1 kW/W e water-cooled; MXR100/12 arriva a 3 kW continui. Gli spot standard, circa 5,5 mm EN per entrambi, sono però troppo grandi per essere assunti compatibili senza calcolo ottico.

La RFQ deve quindi chiedere a Spellman e a Comet/altro costruttore un pacchetto 100 kV con:

- almeno 1 kW continuo e funzionamento 8-24 h;
- target W;
- line focus preferito oppure dimensione apparente <=1 mm nella direzione dispersiva;
- curva spot/potenza e flusso integrato sull'apertura HAPG reale;
- housing, cooling e compatibilità generatore-tubo certificata.

Questa è la scelta che conserva più flusso verso 40-50 keV, ma è anche quella con maggiore rischio di prezzo e integrazione.

### C3 - Spellman XRB100PN500HR integrato

È il fallback commerciale da quotare subito: 100 kV/500 W, spot opzionale 0,5 mm e cone beam opzionale 40 gradi nella famiglia [XRBHR](https://www.spellmanhv.com/en/high-voltage-power-supplies/XRBHR). Riduce fortemente il rischio di accoppiamento tubo-generatore. Richiedere per iscritto target W, rating continuo, flusso spettrale, finestra e duty 8-24 h.

### C4 - VJ IXS1050, solo con certificazione di potenza continua

La pagina ufficiale [VJ IXS1050](https://vjxray.com/products/ixs1050/) dichiara 100 kV, 500 W massimi, spot 0,4 mm, cone beam 30 gradi e modi continuous/pulsing, ma non separa pubblicamente la potenza continua da quella di picco. Non assegnare 500 W continui nel proposal finché il fornitore non certifica il punto operativo per 8-24 h. Il modello VJ IXS101K da 1 kW è dichiarato con esposizioni brevi/duty limitato nella brochure e non è adatto a scansioni XAS lunghe.

### Nota su MetalJet e sorgenti rotanti

[Excillum MetalJet D2+](https://www.excillum.com/products/metaljet/metaljet-d2/) offre 70 kV/250 W con spot 10-20 um e altissima brillanza, ma il target liquido Ga/In/Sn introduce righe caratteristiche, inclusa In Kalpha vicino a 24 keV, nella regione di interesse. Va trattato come benchmark di brillanza/costo, non come prima scelta generalista. Una sorgente rotating-anode da 9 kW come [Rigaku MultiMax-9](https://rigaku.com/products/components/x-ray-sources/multimax-9) supera nettamente il budget atteso ed è un benchmark, non una RFQ prioritaria.

### Corrente realmente disponibile a 40 kV

| Configurazione | Limite di corrente a 40 kV | Potenza a 40 kV | Nota |
|---|---:|---:|---|
| KeyWay KYW600 2 kW + xHuber | 50 mA richiesti | 2.000 W | da certificare come punto continuo tubo-generatore |
| Spellman DXM100 | 12 mA | 480 W | limitato dalla corrente del generatore |
| Spellman XRB100PN500HR | 8 mA | 320 W | raggiunge 500 W da 62,5 kV |
| Spellman XRB80PN320 | 4 mA | 160 W | raggiunge 320 W a 80 kV |
| uXHP65P100 + tubo >=100 W | 2,5 mA | 100 W | limitato dalla potenza |
| Micro X-Ray 75 W | 1,875 mA | 75 W | limite termico del tubo |
| XLG100P100 + rtw | 1 mA | 40 W | non è una soluzione massimo flusso |

Per confronto, **LynXes dichiara un tubo da diffrazione water-cooled da 2 kW**, ma non pubblica il punto kV/mA; se operasse a 40 kV, la corrente corrispondente sarebbe 50 mA. **Sigray QuantumLeap2100 dichiara 300 W massimi**, W/Rh e line-focus: il vantaggio dichiarato deriva dall'accoppiamento geometrico e dall'etendue, non da una sorgente kW. Questi due sistemi vanno usati come benchmark di flusso utile, chiedendo direttamente ai costruttori tensione, corrente, dimensioni del fuoco e photon rate al campione.

## Screening di flusso del continuum

Per ordinare le RFQ è utile un confronto preliminare con la legge di Kramers:

`F(E) proporzionale P x Z x (U-E)/(U x E)`

I valori sotto sono normalizzati, a ciascuna energia, al tubo in-kind Mo 60 kV/75 W. Sono solo uno screening: non includono self-absorption del target, finestra, take-off, spot, solid angle, filtri, riflettività del cristallo o stabilità.

| Sorgente | 25,5 keV | 40 keV | 50 keV |
|---|---:|---:|---:|
| In-kind Mo 60 kV/75 W | 1,00 | 1,00 | 1,00 |
| Micro X-Ray W 60 kV/75 W | 1,76 | 1,76 | 1,76 |
| W 65 kV/100 W su supply in-kind | 2,48 | 2,71 | 3,25 |
| W 80 kV/100 W | 2,78 | 3,52 | 5,29 |
| W 100 kV/100 W | 3,04 | 4,23 | 7,05 |
| W 130 kV/65 W | 2,14 | 3,17 | 5,64 |
| W 80 kV/320 W | 8,91 | 11,28 | 16,91 |
| W 100 kV/210 W | 6,39 | 8,88 | 14,80 |
| W 100 kV/350 W | 10,66 | 14,80 | 24,67 |
| W 100 kV/500 W | 15,20 | 21,15 | 35,25 |
| W 100 kV/1,2 kW | 36,48 | 50,76 | 84,60 |
| W 60 kV/2 kW line-focus | 46,93 | 46,93 | 46,93 |
| Yamamoto W 40 kV/2 kW | 29,60 | 0 | 0 |

Interpretazione:

- nessuna sorgente da 100 W eguaglia il flusso grezzo di Yamamoto all'Ag K-edge;
- il tubo W 60 kV/2 kW è la scelta di flusso a 25,5 keV e conserva un margine di tensione maggiore di Yamamoto;
- la piattaforma W 100 kV/1,2 kW è inferiore a 25,5 keV nel semplice modello, ma è nettamente preferibile a 40-50 keV;
- i valori non includono l'etendue: il confronto finale deve usare i fotoni accettati dall'HAPG e rivelati nella banda simultanea;
- normalizzare il valore a 50 keV non rende il tubo 60 kV adeguato: il valore assoluto è basso perché mancano solo 10 kV all'endpoint.

## Scenario architetturale da validare rispetto a Yamamoto

### 1. Von Hamos dispersivo come scenario progettuale

Questa nota valuta per PRISM la geometria **von Hamos scan-free**, con campione vicino alla sorgente, cristallo HAPG cilindricamente curvato e rivelatore position-sensitive lungo la direzione dispersiva. È la continuità diretta dei lavori Praetz 2025/2026 e permette di acquisire simultaneamente in trasmissione una banda di centinaia di eV fino a circa 1,5 keV. Prima di assumerla come baseline PRISM va però definita e validata la ricostruzione della fluorescence-XAS in funzione dell'energia incidente. Il confronto con Johann di Yamamoto resta un benchmark esterno.

Per PRISM:

- ottimizzare con ray tracing il prodotto `spettro sorgente x area/angolo accettati dall'HAPG x riflettività x efficienza CZT` per ciascun edge;
- mantenere una distanza sorgente-campione dell'ordine di 80 mm come baseline da verificare, così da sfruttare il fascio divergente;
- progettare ottiche HAPG intercambiabili per una modalità XANES ad alta risoluzione/banda circa 500 eV e una modalità wide-band fino a circa 1500 eV;
- orientare il line focus con la dimensione corta nella direzione dispersiva e quella lunga nella direzione non dispersiva; questa compatibilità va dimostrata con ray tracing, non dedotta dai soli watt;
- accettare point focus fino a circa 0,5-1 mm solo se l'aumento di fotoni utili compensa il broadening energetico;
- sopprimere armoniche e righe spurie con scelta HAPG/riflessione, soglie CZT, filtri e spettro I0 energy-resolving;
- usare beam path evacuato o in He e meccanica rigida/termicamente stabile per acquisizioni lunghe.

### 2. CZT multicanale come rivelatore di fluorescenza

Il lavoro locale `SANDBOX/CZT/Abbene_2019_RoomTemperature.pdf` è direttamente abilitante:

- CZT B-VB da 1 mm, pixel pitch 250/500 um;
- 0,9 keV FWHM a 22,1 keV, circa 1 keV a 59,5 keV;
- nessuna polarizzazione fino a 2,2e6 fotoni mm^-2 s^-1;
- lettura PIXIE ASIC e correzione digitale di charge sharing/losses.

Configurazione raccomandata:

- array iniziale 3x3 o 4x4 di pixel/canali indipendenti, 1 mm CZT, posto circa a 90 gradi rispetto al fascio incidente;
- elettronica per-channel, dead-time e pile-up misurati, non solo rate totale;
- coincidence time analysis + charge sharing addition e correzione position-dependent;
- ROI dinamica sulla riga di fluorescenza dell'elemento e acquisizione dello spettro completo per diagnosticare scatter, escape e armoniche;
- collimazione/Soller e schermatura locale per evitare che il continuum diretto saturi il detector.

Prodotti utili come benchmark, non come sostituti automatici del detector PRISM:

- **Amptek XR-100CdTe**, 1 mm CdTe e 25 mm2: ottimo singolo canale di controllo; Amptek indica alta efficienza 10-100 keV ma area/rate limitati per la piattaforma finale ([Amptek XR-100CdTe](https://www.amptek.com/internal-products/xr-100cdte-x-ray-and-gamma-ray-detector));
- **ADVACAM AdvaPIX MAGIC CdTe 1 mm**, 14 x 14 mm, Timepix3, evento per evento, quasi 100% di efficienza fino a circa 80 keV; utile come monitor I0/beam imager e per armoniche, ma la risoluzione pubblicata 1,2-9,9 keV non garantisce il target sub-keV ([AdvaPIX MAGIC](https://advacam.com/camera/advapix-magic/));
- **DECTRIS EIGER2 X/XE CdTe**, 750 um, due soglie, fino a 100 keV e rate elevato; ottimo stretch detector per I0/trasmissione e sottrazione armoniche, non uno spettrometro multicanale completo della fluorescenza ([DECTRIS EIGER2 CdTe](https://www.dectris.com/en/detectors/x-ray-detectors/eiger2/eiger2-for-synchrotrons/eiger2-x-cdte/));
- **Kromek GR1** non è raccomandato per PRISM: il range parte circa da 20-30 keV, il rumore elettronico pubblicato è <10 keV FWHM e il throughput circa 30 kcps, incompatibili con sub-keV nella banda di fluorescenza ([Kromek GR1](https://www.kromek.com/detection/civil-nuclear/gr1-czt-gamma-ray-detectors/)).

### 3. Monitor I0 energy-resolving

Yamamoto mostra che il proportional counter può saturare per riflessioni inferiori. Inserire:

- detector I0 energy-resolving sottile o fortemente attenuato;
- due ROI simultanee: energia nominale e contaminanti/armoniche;
- feedback automatico su filtri e slit se il rapporto contaminante/fondamentale supera la soglia;
- reference foil e detector Iref dopo il campione per ogni edge, per calibrazione energetica e drift.

### 4. Filtri e percorso del fascio

- ruota motorizzata con Al e Cu/Al graded filters, spessori selezionati da simulazione e verificati con MCA;
- percorso evacuato o in He, utile soprattutto per stabilità e riduzione del background anche se l'assorbimento dell'aria è meno severo sopra 20 keV;
- slit sorgente regolabile: con spot 0,5-1 mm permette il compromesso flusso/risoluzione; con spot 50 um può restare più aperta;
- beam stop, shutter fail-safe, monitor di temperatura e interlock hardware indipendente dal software.

## Milestone misurabili rispetto a Yamamoto

1. **Fase 0, in-kind:** Mo K-edge con tubo Mo attuale, mappa completa di armoniche e spettro I0; serve a validare geometria e CZT.
2. **Fase 1, W e 65 kV:** Mo/Rh/Ag/Cd K-edge; target Ag K-edge XANES in meno di 12 h con qualità quantitativa e contaminazione armonica misurata.
3. **Fase 2, 100 kV:** dimostrazione almeno a 30 keV e a un K-edge vicino a 40 keV; questo è il vero superamento del range 13-25 keV di Yamamoto.
4. **Fase 3:** XAS in fluorescenza su campione diluito/operando, con tempo, SNR, dead-time, rate per canale e limite di rivelazione pubblicati.
5. **EXAFS:** dichiararlo obiettivo stretch sopra Ag K-edge fino a quando un test di flusso non dimostra rate sufficiente; non prometterlo sulla sola base dei kV.

## Criteri obbligatori nella quotazione

Chiedere che l'offerta contenga:

- modello e configurazione esatti;
- target W e certificato/materiale target;
- tensione, corrente e potenza **continue**, con operating envelope completo;
- corrente e potenza continue disponibili esattamente a 40, 50, 60, 80 e 100 kV, senza ricavare il dato dalla sola potenza di picco;
- spettro o photon flux misurato/simulato a 20,0, 25,5, 30, 40 e 50 keV, con distanza e apertura dichiarate;
- focal/line spot vs potenza, orientazione rispetto alla direzione dispersiva e stabilità della posizione dello spot in 8 h;
- photon rate integrato sull'area HAPG, alla distanza sorgente-campione e nella banda simultanea fornite da INFN;
- finestra, filtrazione inerente, take-off angle, beam cone/fan e FOD;
- cooling, thermal switch, duty cycle e temperatura ambiente ammessa;
- per riuso: lettera firmata di compatibilità con Spellman uXHP65P100, incluse opzioni del seriale;
- cavi HV/LV, connettori, resistenza serie, ritorno filamento, preheat e conditioning;
- housing, schermatura, shutter, interlock e dichiarazione di leakage; indicare chiaramente cosa resta a carico INFN;
- CE/RoHS, documentazione per integrazione in Italia e acceptance test;
- lead time, Incoterm/DDP Frascati, imballo, trasporto, installazione e collaudo;
- garanzia, lifetime attesa/ore, ricambio tubo e supporto UE/Italia;
- prezzo netto, IVA, trasporto e opzioni separati; validità offerta almeno 90 giorni;
- cap commerciale: 40 kEUR complessivi, precisando se il cap del bando è IVA inclusa o esclusa.

## Messaggio RFQ pronto da inviare

**Subject:** Budgetary and firm quotation due 24 July 2026 - W-anode X-ray source for 20-50 keV laboratory fluorescence XAS - INFN Frascati / PRISM

Dear Sales and Applications Team,

INFN Laboratori Nazionali di Frascati is preparing the PRISM laboratory hard-X-ray absorption spectroscopy project. We request a budgetary/firm quotation and written technical compliance statement for **[MODEL / CONFIGURATION]**.

The instrument will perform scan-free, energy-dispersive XANES/EXAFS and fluorescence XAS above 20 keV, initially at the Mo, Rh, Ag and Cd K-edges, with an upgrade path to approximately 50 keV. The source will illuminate a cylindrically bent HAPG crystal in a fixed **von Hamos geometry**, with the sample located approximately 80 mm from the source and a simultaneous energy bandwidth of approximately 0.5-1.5 keV. It will operate continuously for long acquisitions. A tungsten target is preferred to obtain a clean bremsstrahlung continuum in the 20-50 keV band.

**Requested operating requirements**

- continuous operation, not pulsed rating;
- two requested performance classes: (A) 60 kV, 2 kW continuous line-focus for maximum flux at 20-30 keV; or (B) 100 kV, at least 500 W and preferably 1 kW continuous for extension toward 50 keV;
- tungsten target;
- line focus preferred, with its short axis in the von Hamos dispersive direction; alternatively an apparent spot <=1 mm, subject to ray-tracing validation;
- high output stability for scans lasting 8-24 h;
- divergent beam geometry able to illuminate the full HAPG optic at the proposed source-sample distance;
- full safety/interlock, cooling and integration documentation.

**For the reuse option only:** the available generator is a Spellman uXHP65P100, positive polarity, +65 kV, 5 mA setpoint, 100 W maximum, ground-referenced/grounded-cathode tube architecture, 0.3-3.5 A filament supply. Please provide a signed confirmation of compatibility, including HV connector/cable, filament voltage/current and return, preheat, emission control, series resistance, cooling and conditioning procedure. Photographs, serial number and option codes can be provided immediately.

Please include:

1. exact model and configuration;
2. tube/generator operating envelope and emission curves, including maximum continuous current and power at 40, 50, 60, 80 and 100 kV;
3. point/line focal spot dimensions, orientation, spot versus power and 8 h position/intensity stability;
4. measured or simulated spectral photon output at 20.0, 25.5, 30, 40 and 50 keV, plus the useful photon rate accepted by the stated HAPG aperture and geometry;
5. window, inherent filtration, target/take-off angle, FOD and beam aperture;
6. included HV/LV cables, cooling, housing, shielding, shutter and interlocks;
7. CE/RoHS status and radiation leakage data;
8. acceptance test, warranty, expected tube lifetime and EU/Italy support;
9. lead time and DDP delivery to INFN-LNF, Frascati, Italy;
10. itemized price excluding VAT, VAT, shipping, installation and optional accessories separately.

The total project cap is EUR 40,000. For the separate-component option, please itemize the X-ray tube/housing (target allocation EUR 30,000) and the generator/control system (target allocation EUR 10,000). Please also propose the highest-performance configuration available within the same total cap.

We would appreciate technical acknowledgement by 17 July 2026 and a complete quotation by 24 July 2026, with at least 90 days validity.

Best regards,

[Name / role]  
INFN - Laboratori Nazionali di Frascati  
[email / phone / VAT and delivery details]

## Invii da fare entro due settimane

| Entro | Azione | Destinatario/modelli |
|---|---|---|
| 14-15 luglio | RFQ massimo flusso 20-30 keV | KeyWay KYW600 W 2 kW + xHuber 60 kV/3,5 kW, chiedendo responsabilità di sistema e compatibilità incrociata |
| 14-15 luglio | RFQ massimo flusso 20-50 keV | Spellman DXM100 + Comet/altro tubo W 100 kV >=1 kW small/line-focus |
| 14-15 luglio | RFQ integrato ad alto flusso | Spellman XRB100PN500HR; VJ IXS1050 solo con rating continuo certificato |
| 14-15 luglio | RFQ riuso | Micro X-Ray W/2,0 A; rtw MCBH 80B; Varex VF-80J tube-only |
| 14-15 luglio | RFQ nuovo separato | rtw MCBH 100B + Spellman XLG100P100/FL |
| 14-15 luglio | RFQ nuovo integrato | Spellman XRB100N100 + XRB100PN210HR/350HR + XRB80PN320 |
| 14-15 luglio | RFQ confronto microfuoco | Thermo PXS10; Malvern 90 kV |
| 17 luglio | conferma tecnica | richiedere acknowledgement, application engineer e lista dati mancanti |
| 20 luglio | sollecito | telefonata a Spellman Italia, rtw e Varex EU; chiudere configurazioni |
| 22 luglio | pre-selezione | eliminare offerte senza compatibilità scritta o oltre cap |
| 24 luglio | offerte complete | prezzo firmato, validità, lead time, acceptance test |
| 27 luglio | decisione | matrice tecnica/economica e scelta primaria + backup |
| 28 luglio | buffer | recupero ultimo documento/amministrazione |

## Matrice di decisione

Valutare solo configurazioni che superano i gate target W, continuous duty 8-24 h, compatibilità scritta con von Hamos e costo entro cap.

| Criterio | Peso |
|---|---:|
| flusso utile documentato attraverso HAPG a 25,5/40/50 keV | 30% |
| margine energetico e potenza continua | 20% |
| point/line spot, stabilità e compatibilità con von Hamos | 20% |
| rischio di integrazione elettrica/meccanica | 10% |
| prezzo, lead time e completezza del pacchetto | 15% |
| supporto UE/Italia, garanzia, ricambi e conformità | 5% |

La scelta finale non deve essere fatta sui soli kV/W nominali: il dato decisivo da richiedere è il flusso utile attraverso la finestra, nella geometria reale, alle energie PRISM.
