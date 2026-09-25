# Smash Péi — Étape 1 : audit des points d'accroche

Fichier audité : `smash_pei (6).html` (56 485 lignes, un seul `<script>` de la ligne 2422 à la ligne 56483).
Les numéros de ligne renvoient à l'état du commit `4f3f4c9`.
Mesures prises dans Chromium sans affichage (fichier ouvert directement, aucune erreur console au chargement).

---

## 0. Conflits à signaler avant d'écrire du code

| # | Conflit | Détail |
|---|---------|--------|
| C1 | **Le hitlag existe déjà** (étape 2) | `Fighter.hitlag` (l. 15589), gel local `Match.impact()` (l. 21088), gel global `Match.hitstop()` plafonné à 7 images (l. 21081), multiplicateur `h.hitlag` sur chaque hitbox, option joueur `opts.hitstop`, champ transmis en ligne (l. 25338 / 25576), tremblement pendant le gel dans `50-impact.js`. L'étape 2 ne peut pas **créer** le hitlag : il faut la réorienter vers la **correction** du hitlag existant (voir §3.2). |
| C2 | **Le DI existe déjà** (étape 3) | `takeHit` l. 18018–18023 : `ang += ax * 15`. Il existe aussi `readDI()` (l. 15761), qui lit le stick pendant le hitlag dans `this.di` / `this.diY`… mais **ces deux valeurs ne sont jamais utilisées**. L'étape 3 devient une **reprise** du DI (voir §3.3). |
| C3 | **Le screen-shake et le juice existent déjà** (étape 4) | Trois couches se superposent déjà sur chaque coup : `06-fighter` (`FX.hit`, `M.shake(4 + power*14)`, `zoomPunch`), `50-impact` (`FX.frappe`, second `shake(1.5 + p*5)`) et `96-lisibilite-combat` (mots, couleurs par force). S'y ajoute le curseur « dose d'effets » de `93-cadre`. Ajouter une 4ᵉ couche doublerait tout. L'étape 4 doit **recalibrer via une table** plutôt qu'empiler. |
| C4 | **Noms des hooks** | Les noms cités dans la demande n'existent pas tels quels. Les vrais noms : `COS_TETE`, `COS_VISAGE`, `COS_DOS`, `COS_AURA` (avec un tiret bas), `MESURES_TETE`, `cosFitTete()` + `ch.cosFit` (il n'y a pas de `COSFIT`). « PAS » désigne la table des danses (`window.DANSES_PAS`, bloc 67) ; c'est aussi le nom d'une constante locale sans rapport dans `74-cadence` (= `TICK`). |
| C5 | **Nom du fichier** | Le fichier du dépôt s'appelle `smash_pei (6).html`, pas `smash_pei-6.html`. Je garde le nom actuel sauf avis contraire. |
| C6 | **Numérotation** | Le dernier bloc est `101-visite-plus.js`. Les numéros 27 et 70 sont libres mais les réutiliser casserait l'ordre chronologique. Proposition : **102 à 106**, sans collision de nom (voir §4). |

---

## 1. Conventions de code (à respecter par tout ajout)

### 1.1 Structure d'un bloc
```
/* ===== NN-nom-court.js ===== */
/* ============================================================
   SMASH PÉI — TITRE EN MAJUSCULES

   Diagnostic (ce que le joueur signale / ce que la mesure montre)
   Mesure chiffrée
   Correction, numérotée
   ============================================================ */
(function nomDuBloc() {
  if (typeof Fighter === 'undefined' || !Fighter.prototype) return;   // garde
  ...
})();
```
- Un bloc = **une IIFE nommée**, qui commence par des gardes `typeof X === 'undefined'`.
- Les réglages sont des **constantes MAJUSCULES en tête de l'IIFE** (`CONFIRME`, `GAIN`, `VMAX` dans `75-chute` ; `AMPLI` dans `58-silhouettes`).
- Commentaires en français, prose pleine, « on » ; `/* … */` pour les explications, `//` pour les notes courtes.
- Les erreurs non critiques sont avalées (`try {} catch (e) {}`) ou signalées **une seule fois** (`if (!bloc.__vu) { bloc.__vu = 1; console.error(...) }`).

### 1.2 Enveloppes (surcharge sans écrasement)
Trois formes, toutes utilisées dans le fichier :

```js
// a) méthode de classe
const orig = Fighter.prototype.update;
Fighter.prototype.update = function () {
  const r = orig.apply(this, arguments);
  try { /* ajout */ } catch (e) {}
  return r;
};

// b) fonction globale déclarée par `function X()` → on passe par window
const teteOrig = COS_TETE;
window.COS_TETE = function (ctx, r, f, P, pose) { ... return teteOrig(ctx, r, f, P, pose); };

// c) garde anti double enveloppe
if (Fighter.prototype.takeHit.__lis) return;
env.__lis = 1; Fighter.prototype.takeHit = env;
```
- `drawFighterRig` est déjà enveloppée **2 fois** (`44-lumiere` l. 38565, `83-persos-cine` l. 48632).
- `Fighter.prototype.takeHit` est déjà enveloppée **4 fois** (l. 39694 `47-coups`, 39871 `50-impact`, 41107 `55-objets-cosmetiques`, 53483 `96-lisibilite-combat`).
- `Fighter.prototype.update` est enveloppée au moins par `50-impact`, `66-inertie`, `75-chute`.
- Pour transformer une constante de `PHYS` en valeur calculée : `Object.defineProperty(PHYS, nom, { get, set })` (`66-inertie`).

L'**ordre des enveloppes compte** : un bloc ajouté en fin de fichier (102+) est la couche la plus externe. Il voit donc l'état *après* toutes les corrections précédentes.

---

## 2. Rendu des personnages

| Élément | Où | Contrat |
|---|---|---|
| `drawFighterRig(ctx, ch, pose, opt)` | l. 4608 | **Seul point d'entrée du rendu d'un corps.** Appelée par `Fighter.draw`, les replays (l. 20821), les écrans de sélection, de victoire et de vestiaire (l. 21865, 21916, 22900, 23477…). `opt = { scale, blink, tint, flash }`. Le repère est **aux pieds**, et le personnage est dessiné tourné vers la droite (le miroir est fait par l'appelant). |
| `RIG` | l. 4476 | Proportions de base (`torsoLen 30, headR 17, …`) × `ch.build` (`width, height, headScale, limbW, arm, leg, torso, shape`). |
| Ordre de dessin | l. 4670–4712 | 1) arrière : `wings`, `tail`, `cape`, `back` puis **`COS_DOS`** (si `features.backX`), `tentacles`, `fins` → 2) membres arrière → 3) `drawTorso` → 4) membres avant → 5) cou → 6) `drawHead`. |
| `drawHead(ctx, x, y, r, pose, ch, P, opt)` | l. 5352 | Forme = `ch.features.head` (famille). À la fin (l. 5770) : **`COS_TETE(ctx, r, f, P, pose)`** si `f.hatX`, puis **`COS_VISAGE(ctx, r, f, P, pose)`** si `f.faceX`. |
| `MESURES_TETE` | l. 5213 | `{ cx, top, hw }` en rayons pour les 10 familles : `round, oval, wide, drop, shark, beak, leaf, long, slim, bulky`. Surchargée par le bloc 65 (l. 44190). |
| `cosFitTete(ch, r, kind, f)` | l. 5232 | Renvoie `{dx, dy, sx, sy}` pour poser un accessoire ; réglage manuel par personnage via **`ch.cosFit = {dx, dy, sx, sy}`** (en rayons). |
| `TRAITS_TETE` / `drawTraitTete` | l. 5350 / 5270 | `horns, crest, leaf, flame, hair, finHead` : un trait natif passe sous les accessoires, un trait venu du vestiaire passe par-dessus. |
| Palette | `ch.pal` | `skin, skin2, cloth, accent, hand, shoe, wing, cape, hair, beak, horn` (la liste recolorée par les peaux, l. 3082). |
| Utilitaires couleur | l. 4168+ | `shade(hex, amt)` (en cache), `mixc`, `rgba(hex, a)`, `recolor(hex, opt)`. |

Distribution mesurée des familles de tête sur les **63 personnages** (`CHARS`, pas `CHAR_LIST`, qui ne contient que les personnages débloqués — 10 au départ) :

```
bulky 12 · beak 9 · oval 8 · slim 8 · drop 6 · round 6 · leaf 6 · wide 4 · long 2 · shark 2
```
Ces familles sont attribuées par `58-silhouettes` (table `TETES`) ; les carrures sont écartées (`AMPLI = 1.28`) ; les matières de corps sont corrigées par `68-tenues`.

## 3. Moteurs de jeu

### 3.1 Poses et animation
- `POSE_KEYS` (l. 4199) : **23 articulations**, en degrés ou en pixels : `hipX hipY hipRot torso head headX headY shL elL shR elR hpL knL hpR knR sx sy tail wing prop mouth eye lean`. C'est le **contrat** que le pipeline Blender (étape 5) devra reproduire (os ↔ clé).
- `REST` (l. 4205), `newPose(o)` = `Object.assign({}, REST, o)`.
- `POSE_RATE` + `lerpPoseSoft` : lissage par articulation ; `lerpPose`, `sampleFrames(frames, t)` avec des images clés `{t, p, ease}`.
- `Poses` (l. 4258) : `idle walk run dash jumpSquat air land crouch shield hurt tumble ledge dodgeSpot roll airDodge grabbed taunt victory lose`, de signature `(t, f)`.
- `ATK_ANIM` (l. 4337) : images clés des attaques, indexées par `move.anim`.
- `Fighter.updateAnim()` (l. 18286) choisit la pose **pendant la mise à jour** (pas au dessin) → `this.anim.pose`.
- Danses : `Poses.victory` enveloppée par `67-danses` ; table `window.DANSES_PAS`, correspondance `window.DANSES_ID` ; « qui danse » passe par `Poses.__danseur`.

### 3.2 Coups, hitlag, hitstun
- `ST` (l. 15531) : états en chaînes de caractères (`HITSTUN`, `TUMBLE`, `DEAD`…).
- Hitbox : `H({ s, e, x, y, w, h, dmg, ang, bkb, kbg, hitlag, sfx, fx, spike, link, … })`. `ang: 361` = angle de Sakurai.
- `knockback(pct, dmg, weight, bkb, kbg, ratio, rage)` et `kbToSpeed(kb, pct)` (l. 15544).
- `Fighter.takeHit(src, h, dir, hitPos)` (l. 17892) : contre, parade, bouclier, armures, super, **puis éjection** (l. 18010) → `kbAngle`, `kbSpeed`, `hitstun = max(6, kb * PHYS.hitstunMul)`, `setState(kb > 55 ? TUMBLE : HITSTUN)`.
- **Hitlag actuel** :
  - victime : `hitlag = floor(h.hitlag * (3 + dmg * 0.5))` (l. 18038) — **non plafonné, non multiplié par `opts.hitstop`** ;
  - attaquant : `M.impact(floor(h.hitlag * (2 + dmg * 0.42)), src)` (l. 18059) — plafonné à 14, multiplié par l'option.
  - ⇒ **l'attaquant et la victime ne sont pas gelés le même temps**, et le réglage « hitstop » du joueur ne s'applique qu'à l'attaquant. Exemple : smash avant de 15 % → victime 10 images, attaquant 8.
  - Pendant le gel, `Fighter.update` sort tôt (l. 15686) : `readDI()`, `shakeOffset`, rien d'autre. Les hitboxes d'un attaquant gelé ne sont pas testées (l. 21309).
  - Gel global `M.hitstopF` : réservé aux K.O., super, parade, bouclier brisé.
- Boucle à pas fixe : `TICK = 1000/60` (l. 2435) ; `Match.update()` (l. 21119) gère `slowF`, puis `hitstopF`, puis la partie. `74-cadence` sépare les accumulateurs.
- **Replays** (`21-replay`) : tampon d'**instantanés** (positions et poses), pas d'entrées rejouées → un changement de hitlag ne peut pas désynchroniser un replay existant.
- **En ligne** (`12-net`) : l'hôte fait autorité et envoie des instantanés ; `hitlag` (index 20) et `M.hitstopF` sont sérialisés. Les manettes distantes existent dans `Input.devices` côté hôte. Tout nouvel état qui influe sur la simulation doit être calculé côté hôte.

### 3.3 DI actuel
```js
const diIn = (this.slot.kind === 'cpu') ? 0 : (Input.devices[this.slot.device] || blankState()).ax;
if (diIn) ang += clamp(diIn, -1, 1) * 15;
```
Défauts constatés :
1. lu **à l'instant du coup**, alors que dans Smash on lit le stick **à la fin du hitlag** (c'est tout l'intérêt du gel) ; `this.di / this.diY` sont collectés pendant le gel puis ignorés ;
2. **seul l'axe horizontal** compte : on ne peut pas infléchir une éjection horizontale en tenant haut ou bas ;
3. l'effet n'est pas symétrique : tenir « droite » rend une éjection vers la droite plus verticale, mais rend une éjection vers la gauche plus horizontale ;
4. les bots ne font jamais de DI (à relier aux défauts calibrés de `57-bots`) ;
5. `FX.frappe` (`50-impact`) oriente l'onde de choc sur `h.ang`, pas sur `this.kbAngle` : elle ignore l'angle 361 et le DI.

`75-chute` : HITSTUN et TUMBLE sont dans `INTOUCHABLE` → aucun effet de condamnation pendant l'éjection. Le DI ne peut donc pas entrer en conflit avec lui tant qu'il n'agit que sur `kbAngle` au moment du lancement.

### 3.4 Particules et caméra
- `FX` (l. 15224) : pool de `Particle` (900, plafond 1400 vivantes), `FX.q()` = option `particles` (les types de `FX.OPTIONAL` sont éclaircis).
- Générateurs : `spark(x,y,vx,vy,col,life,r,layer)`, `streak`, `dust(x,y,n,col)`, `smoke(x,y,n,col)`, `ring(x,y,r,col,life,lw,grow,flat,rot)`, `burst`, `slash`, `star`, `spark4`, `shock`, `text`, `leaf`, `hit(x,y,dir,kind,col,power)`, `koBurst` ; ajouté par le bloc 50 : `frappe(x,y,ang,p,col,sol)`.
- `Match` : `shake(v)` (× `opts.shake`), `zoomPunch(v)`, `flash(a)`, `slowmo(f,k)`, `impact(frames, ...cibles)`, `hitstop(f)`. Styles de caméra et dose d'effets dans `93-cadre`.
- Toutes les particules utilisent `Math.random` (`rnd`, `pick`) : c'est purement visuel, sans effet sur la simulation.

### 3.5 Cosmétiques
- `COSMETICS` (l. 2943) : `{ id, slot, lvl, fr, en, apply: f => { … } }` ; préfixes `h_` (chapeau), `s_` (peau), etc. Ajouts via `COSMETICS.push(...)` et marque `c.__x = true` pour les pièces étendues.
- `COS_SLOTS` (l. 3015) : `hat face back aura skin` + ajoutés à l'exécution : `dance titre banniere depart entree trainee musique`.
- `cosmeticChar(char, forceEquip)` (l. 3066) : dérive le personnage par `Object.create`, copie `features` et `pal`, applique chaque pièce, **met le résultat en cache** (clé = id + équipement). `clearCosCache()` incrémente `COS_STAMP` ; `Fighter.updateAnim` relit si le tampon change.
- Pièces étendues : `apply` pose `f.hatX`, `f.faceX`, `f.backX`, `f.aura` (chaîne) → dessinées par `COS_TETE`, `COS_VISAGE`, `COS_DOS` (dans le rig) et `COS_AURA(f, kind, px, py)` (appelée par `Fighter.drawAura`, pour les particules).
- Autres tables : `COS_ICON`, `COS_RARITY`, `COS_PERKS`, `COS_NORMALISE`, `COS_CLES`.

---

## 4. Plan révisé proposé (à valider)

| Étape | Bloc | Contenu recalé sur l'existant |
|---|---|---|
| 2 | `102-hitlag.js` | Ne crée pas le hitlag : **unifie** attaquant et victime sur une seule formule (du type Smash : `(dmg*0.65 + 6) × h.hitlag`, avec plafond), applique `opts.hitstop` aux deux, garde le gel global intact. Enveloppe `takeHit`, sans réécriture. |
| 3 | `103-di.js` | Lit le stick **à la fin du gel** (`this.di / diY` déjà collectés), applique un DI **perpendiculaire** (projection du stick sur la normale de la trajectoire), borné à ±18°, sur les deux axes ; DI optionnel pour les bots selon leur niveau ; corrige l'orientation de `FX.frappe` sur `kbAngle`. |
| 4 | `104-juice.js` | Table `JUICE` en tête de bloc ; la « puissance » dépend de l'**éjection** et pas seulement des dégâts (un jab à 150 % tue) ; paliers jab / coup franc / smash chargé / K.O. ; **remplace** les deux tremblements empilés au lieu d'en ajouter un troisième ; respecte la dose d'effets. |
| 5 | `105-sprites.js` + `tools/blender/*.py` + `tools/spritesheet/pack.mjs` | Enveloppe `drawFighterRig` : un personnage déclaré dans `SPRITES` est dessiné depuis sa planche, les autres passent par le vectoriel **inchangé** ; les points d'ancrage (tête, dos) sont exportés dans le JSON pour continuer à appeler `COS_TETE`, `COS_VISAGE` et `COS_DOS` au bon endroit. |
| 6 | `106-silhouettes-fines.js` | Mesure des paires proches (famille + carrure + palette) sur les 63, puis ajustements `build` et `cosFit` ciblés, sans changer de famille aux personnages déjà réglés. |
