# VOXES per PRISM — Blender v1

Aprire `v1_VOXES.blend` in Blender 5.2. Nella vista 3D premere **N** e selezionare la scheda **VOXES**. Il pannello è installato per l'utente locale e compare soltanto nei file VOXES. Se Blender era già aperto prima della creazione del pannello, riavviarlo oppure usare `Apri_VOXES.sh`.

## Viste

1. Insieme — obliqua frontale, vista iniziale.
2. Insieme — obliqua opposta.
3. Pianta — percorso dei componenti ottici.
4. Prospetto — altezza del fascio.
5. Dettaglio — sorgente VOXES con tubo superiore.
6. Trasmissione — sorgente con tubo posteriore, obliqua.
7. Trasmissione — sorgente con tubo posteriore, dall'alto.

I pulsanti cambiano telecamera, configurazione e relative etichette insieme. **F12** genera il render. Il pannello permette di nascondere le etichette o esportare con sfondo trasparente. Le etichette sono testo Blender modificabile; il font Arial è incorporato nel `.blend`.

## Derivazione dal CAD

Origine: `v004_VOXES.FCStd`, preservato. Le mesh mantengono le posizioni globali del FreeCAD e le dimensioni fisiche, convertendo mm in m. Sono mantenuti la camera della sorgente con portacampione, tubo, attacco laser, le due fenditure, il cristallo HAPG e relativi piccoli supporti, il MYTHEN. Sono esclusi linea ED-XRF, motori, guide, rotaie, telaio e tavolo. Il cristallo resta quello HAPG presente nel modello VOXES, senza sostituirlo con il futuro Ge di PRISM.

Trasmissione: duplicati collegati delle mesh della sorgente, con il tubo ruotato di -90° attorno a Y e la faccia della flangia allineata al piano posteriore x = -70 mm, al posto dell'attacco laser. Questa è una configurazione illustrativa: non introduce né certifica un adattatore meccanico o la compatibilità delle forature. Le due viste in trasmissione escludono slits, cristallo e MYTHEN anche fuori dall'inquadratura.

## Portabilità

Lo script del pannello è anche incorporato come testo `voxes_panel.py`. Su un altro computer: aprire il file, passare a **Scripting**, scegliere `voxes_panel.py` e premere **Run Script**. In alternativa utilizzare `Apri_VOXES.sh` con lo script affiancato al `.blend`. Non è necessario abilitare globalmente l'esecuzione automatica degli script.

I render delle telecamere sono nella cartella `previews`. Script riproducibili e inventario degli oggetti originali sono in `blender_assets`.
