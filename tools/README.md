# Smash Péi — pipeline de sprites Blender

Rend un personnage dans Blender et le fait dessiner par le jeu depuis une spritesheet, à la place de son rendu vectoriel. Les 62 autres personnages restent vectoriels.

Le mode d'emploi détaillé est en tête de chaque fichier.

| Étape | Où | Commande | Produit |
|---|---|---|---|
| 1. Poses | navigateur, jeu ouvert, console (F12) | `SPRITES.exporterPoses('tijean')` | `tijean.poses.json`, à ranger dans `rendus/tijean/` |
| 2. Squelette (une fois) | terminal | `blender -b --python tools/blender/sp_rendu_spritesheet.py -- --poses rendus/tijean/tijean.poses.json --mode squelette --mannequin` | `rendus/tijean/tijean_squelette.blend` (armature `SP_Rig` aux longueurs du jeu) |
| 3. Modèle | Blender | modéliser, attacher à `SP_Rig`, enregistrer `rendus/tijean/tijean.blend` | |
| 3 bis. Ou : modèle tout fait | terminal | `blender -b --python tools/blender/sp_modele.py -- --poses rendus/tijean/tijean.poses.json` | `rendus/tijean/tijean.blend` : un vrai modèle 3D (Ti Jean pour l'instant), déjà attaché au squelette ; passer directement à l'étape 4 avec `--style ultimate --tete sprite` |
| 4. Rendu | terminal | `blender -b rendus/tijean/tijean.blend --python tools/blender/sp_rendu_spritesheet.py -- --poses rendus/tijean/tijean.poses.json --mode rendu --sans-tete` | `rendus/tijean/images/<anim>/<anim>_NNNN.png` + `manifeste.json` |
| 5. Planche | terminal (Node 18+, rien à installer) | `node tools/spritesheet/sp_assembler.mjs rendus/tijean sprites` | `sprites/tijean.sprites.js` (+ `.png`, `.json`) |
| 6. Activation | jeu | ajouter `'tijean'` à `SPRITES_CONFIG.ACTIFS` (bloc `105-sprites.js`) ou `SPRITES.charger('tijean')` | |

Le dossier `sprites/` doit être à côté du fichier HTML.

Pour revenir au rendu vectoriel sans recharger la page : `SPRITES.actif('tijean', false)`.

Le dossier `rendus/` peut devenir volumineux (une image PNG par pose). Il vaut mieux ne pas le versionner.
