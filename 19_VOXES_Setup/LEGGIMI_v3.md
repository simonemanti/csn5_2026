# VOXES v3

Aprire `v3_VOXES.blend`, quindi **N → VOXES**. Se Blender era già aperto, avviare `Apri_VOXES_v3.sh` per caricare il pannello aggiornato. **F12** per renderizzare.

- Palette derivata da `1_Ref_Old_VOXES.png`: tubo in acciaio chiaro e slits neri, camera e piastre alluminio chiaro, portacampione ottone, ottica azzurra, rivelatore grigio.
- Setup: rimossi `204A004A / Part__Feature1585` e `204A008A / Part__Feature1604` dalla faccia frontale.
- Trasmissione: rimosso `204A004A / Part__Feature1585`; `204A008A / Part__Feature1604` ruotato e montato sopra, con faccia inferiore a z = 64.5 mm. Tubo mantenuto sul retro.
- Tutte le telecamere sono rivolte verso il lato aperto. Le viste dall'alto sono sostituite da viste rialzate inclinate per mantenere visibile il portacampione.
- Fascio rosso schematico nelle viste d'insieme del setup, senza ramo ED-XRF. Il percorso collega i centri del CAD e illustra la disposizione; non deriva da una simulazione ottica. Si può nascondere con **Fascio schematico**.
- Etichette Arial modificabili e font incorporato. Sfondo trasparente selezionabile nel pannello.

Render delle sette viste: `previews_v3/`. Verifica geometrica della visibilità del portacampione: `blender_assets/verification_v3.json`.

Il file v1 e il FreeCAD di origine non sono stati modificati.

Aggiornamento materiali e pannello:
- Tubo in metallo chiaro lucido; piastre SOLID, base flangiata e coperchio superiore condividono il materiale di 204C001B, anche in trasmissione.
- Preset Forest per Material Preview e ambiente Forest incorporato per i render, con sfondo bianco.
- N → VOXES → Dimensione etichette: scala globale da 0.25 a 3; 1 corrisponde alla dimensione originale.
