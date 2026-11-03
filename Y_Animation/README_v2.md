# PRISM — animazione v2

Aprire **v2_Animation.blend** e premere **Spazio**. **Numpad 0** richiama la camera.
Il ciclo dura 14 secondi: 336 frame a 24 fps, rendering 1920 × 1080.

- Sfondo bianco.
- Oggetto `Crystal` importato da `11_SETUP_XAS/v1.2_Setup_PRISM.blend`: mesh,
  scala, materiale, facce e orientamento centrale originali conservati.
- Rotazione illustrativa di 80° attorno a Z.
- Frecce in movimento verso campione e detector.
- Curva Ag foil ricavata dai dati numerici già presenti in `21_XANES_Ag`.
- Assi con tacche numeriche: `E − E₀ (eV)` e `Normalized absorption`.
- Pallino rosso sulla curva; fluorescenza oltre l'edge.

File pronti: **v2_Animation.mp4** (Full HD, 24 fps) e **v2_Animation.gif**
(1280 × 720, 16 fps, ripetizione continua).

## Parametri delle frecce

Selezionare **Animation_Controls**, quindi **Object Properties → Custom Properties**.
I parametri seguenti aggiornano il movimento direttamente, senza rigenerare il file.

| Proprietà | Default | Effetto |
|---|---:|---|
| `arrow_cycle_frames` | 84 | Durata di un passaggio sui fasci principali; ridurre per accelerare |
| `fluorescence_cycle_frames` | 42 | Durata di un passaggio dal campione al detector |
| `arrow_travel_start` | 0.08 | Inizio del percorso, frazione della lunghezza del fascio |
| `arrow_travel_end` | 0.92 | Fine del percorso, frazione della lunghezza del fascio |
| `arrow_size` | 1.25 | Dimensione delle frecce |

Mantenere `0 ≤ arrow_travel_start < arrow_travel_end ≤ 1`.
I periodi predefiniti dividono i 336 frame del ciclo, per un raccordo continuo.
Le frecce avanzano sempre nella direzione dei fotoni, anche durante la scansione
energetica di ritorno. Numero delle frecce e ampiezza di rotazione del cristallo
si impostano nello script di creazione.

## Curva di riferimento

Fonte: dati di trasmissione Ag foil NIMS/JASRI, SPring-8 BL14B2,
DOI [10.48505/nims.1453](https://doi.org/10.48505/nims.1453), già nel progetto.
La normalizzazione segue `21_XANES_Ag/s1_ref_comparison.py`.
L'interpolazione PCHIP conserva la forma dei dati senza overshoot; non viene
applicato un filtro alla curva. L'energia mostrata è relativa a E₀, definito
dal massimo della pendenza del riferimento. Le energie originali sono conservate.

È un riferimento misurato al sincrotrone, non una misura PRISM. La rotazione è
accentuata a scopo illustrativo e non ricalcola il percorso del fascio.

Dati e provenienza sono in `v2_xas_reference.json`, anche incorporato nel `.blend`.
Il font e le texture sono inclusi nel file. I driver usano soltanto espressioni
semplici: nessun handler Python o script da autorizzare all'apertura.

## Rigenerazione

```bash
blender --background --python Y_Animation/create_animation_v2.py
blender --background --python Y_Animation/create_animation_v2.py -- --help
blender --background --python Y_Animation/create_animation_v2.py -- --arrow-cycle-frames 56 --arrow-size 1.4
```

`prepare_xas_reference_v2.py` rigenera i dati interpolati. `previews_v2/` contiene
i fotogrammi di controllo. `v2_verification.json` riporta i controlli sul file.
I file v1 restano disponibili.
