# PRISM — animazione v1

La versione più recente è **v2_Animation.blend**, con MP4 e GIF. Vedere
[README_v2.md](README_v2.md) per modifiche e parametri delle frecce.

Aprire **v1_Animation.blend** in Blender e premere **Spazio** per avviare.
Il file si apre al frame 1, in vista camera. **Numpad 0** richiama la camera.

- 14 secondi, 24 fps, 336 frame, ciclo continuo.
- Cristallo: rotazione di 80° attorno a Z, dimensione visiva aumentata 2,35 volte.
- Curva XAS fissa accanto al detector; pallino rosso che segue la scansione.
- Campione e fluorescenza verso il CZT si accendono oltre l'edge e si spengono al ritorno.
- Nessuna scritta, etichetta o valore numerico nell'immagine.
- Animazione interamente salvata in keyframe modificabili, texture incluse.
- Rendering impostato a 1920 × 1080, sequenza PNG in `frames/`.

`v1_Animation.mp4` è l'anteprima video pronta da riprodurre; `previews/` contiene
alcuni fotogrammi di controllo.

La scena deriva da `../11_SETUP_XAS/v2_Setup_PRISM.blend`. La curva XAS è
schematica; rotazione e scala del cristallo sono volutamente accentuate.
Il percorso ottico resta quello del setup originale e non viene ricalcolato
durante la rotazione: è un'animazione illustrativa, non una simulazione o una
misura. Queste note non compaiono nell'animazione.

Per rigenerare il file con Blender 5.2:

```bash
blender --background --python Y_Animation/create_animation.py
blender --background --python Y_Animation/create_animation.py -- --help
```

`animation_timing.json` conserva i valori per ogni frame; `verification.json`
riporta i controlli sul file salvato.
