#!/usr/bin/env node
/* ============================================================
   SMASH PÉI — ASSEMBLAGE D'UNE SPRITESHEET

   Prend les images rendues par Blender (tools/blender/
   sp_rendu_spritesheet.py) et les range dans UNE planche PNG, avec
   ses métadonnées.

   AUCUNE DÉPENDANCE : Node 18 ou plus, rien à installer. Le PNG est lu
   et écrit ici même, avec le module `zlib` fourni par Node.

   UTILISATION
       node tools/spritesheet/sp_assembler.mjs <dossier-rendu> <dossier-sortie> [options]

   Exemple, depuis la racine du dépôt :
       node tools/spritesheet/sp_assembler.mjs rendus/tijean sprites

   ENTRÉE — le dossier produit par Blender :
       rendus/tijean/manifeste.json
       rendus/tijean/images/<anim>/<anim>_<NNNN>.png

   SORTIE — à mettre à côté du fichier HTML du jeu :
       sprites/tijean.sprites.js   CE QUE LE JEU CHARGE : métadonnées ET
                                   image (en data:), dans un seul script.
       sprites/tijean.png          la planche, pour la regarder
       sprites/tijean.json         les métadonnées, lisibles

   POURQUOI TOUT DANS UN SCRIPT. Le jeu s'ouvre directement depuis le
   disque (file://). Dans ce cas le navigateur refuse de lire un .json,
   mais accepte un <script>. Et surtout : une image chargée depuis un
   fichier « contamine » tout canevas où on la dessine — le jeu ne peut
   plus en lire les pixels. Or il le fait : l'exposition automatique
   (bloc 94) mesure l'écran, et l'export des clips enregistre un
   canevas. Une image en data:, elle, ne contamine rien.

   OPTIONS
       --marge N        pixels transparents autour de chaque image (2)
       --largeur N      largeur maximale de la planche (2048)
       --seuil N        alpha en dessous duquel un pixel compte comme vide (1)
       --image-separee  le .sprites.js pointe vers le .png au lieu de le
                        contenir. Réservé à un jeu servi par un serveur
                        web (http://) ; en file://, le jeu refuse ce cas
                        et garde le personnage en vectoriel.

   LE FORMAT DES MÉTADONNÉES (smashpei-sprites/1)
       {
         "format": "smashpei-sprites/1",
         "perso": "tijean",
         "image": "tijean.png",
         "echelle": 2.1,          pixels de planche par pixel de jeu
         "tete": "vectorielle",   ou "sprite"
         "rig": { ... },          longueurs du squelette du jeu
         "taille": [w, h],        taille de la planche
         "animations": {
           "idle": { "boucle": true, "frames": [
             { "x":0, "y":0, "w":80, "h":190,   rectangle dans la planche
               "ox":40, "oy":186,               position des PIEDS dans ce
                                                rectangle (origine du jeu)
               "ancres": { hx, hy, cx, cy,      tête, poitrine, bassin, en
                           hipX, hipY },        pixels de jeu depuis les pieds
                                                (quand Blender les a mesurées)
               "pose": { ... } }                la pose qui a produit l'image
           ] }
         }
       }
   Les images sont ROGNÉES à leur contenu visible : `ox`/`oy` gardent la
   trace de l'origine, c'est ce qui permet au jeu de poser le personnage
   au pixel près quelle que soit la découpe.
   ============================================================ */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';
import { inflateSync, deflateSync } from 'node:zlib';

/* ---------------------------------------------------------------
   PNG : lecture (8 et 16 bits, RGBA / RGB / gris / gris+alpha,
   non entrelacé — ce que Blender écrit) et écriture (RGBA 8 bits)
   --------------------------------------------------------------- */
const SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

export function lisPNG(buf) {
  if (!buf.subarray(0, 8).equals(SIGNATURE)) throw new Error('pas un PNG');
  let p = 8, w = 0, h = 0, prof = 0, type = 0, entrelace = 0;
  const idat = [];
  while (p < buf.length) {
    const len = buf.readUInt32BE(p);
    const t = buf.toString('latin1', p + 4, p + 8);
    const d = buf.subarray(p + 8, p + 8 + len);
    if (t === 'IHDR') {
      w = d.readUInt32BE(0); h = d.readUInt32BE(4);
      prof = d[8]; type = d[9]; entrelace = d[12];
    } else if (t === 'IDAT') idat.push(d);
    else if (t === 'IEND') break;
    p += 12 + len;
  }
  if (entrelace) throw new Error('PNG entrelacé non pris en charge (désactivez l\'entrelacement)');
  const canaux = { 0: 1, 2: 3, 4: 2, 6: 4 }[type];
  if (!canaux || (prof !== 8 && prof !== 16)) throw new Error(`PNG non pris en charge (type ${type}, ${prof} bits)`);
  const oct = prof / 8, bpp = canaux * oct, ligne = w * bpp;
  const brut = inflateSync(Buffer.concat(idat));
  const px = Buffer.alloc(ligne * h);
  for (let y = 0; y < h; y++) {
    const f = brut[y * (ligne + 1)];
    const src = y * (ligne + 1) + 1, dst = y * ligne, prec = dst - ligne;
    for (let i = 0; i < ligne; i++) {
      const x = brut[src + i];
      const a = i >= bpp ? px[dst + i - bpp] : 0;
      const b = y > 0 ? px[prec + i] : 0;
      const c = (i >= bpp && y > 0) ? px[prec + i - bpp] : 0;
      let v;
      switch (f) {
        case 0: v = x; break;
        case 1: v = x + a; break;
        case 2: v = x + b; break;
        case 3: v = x + ((a + b) >> 1); break;
        case 4: { const q = a + b - c, pa = Math.abs(q - a), pb = Math.abs(q - b), pc = Math.abs(q - c);
                  v = x + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c); break; }
        default: throw new Error('filtre PNG inconnu ' + f);
      }
      px[dst + i] = v & 255;
    }
  }
  /* vers RGBA 8 bits */
  const out = Buffer.alloc(w * h * 4);
  for (let i = 0, n = w * h; i < n; i++) {
    const s = i * bpp, v = k => px[s + k * oct];      // octet de poids fort en 16 bits
    let r, g, b, al = 255;
    if (canaux === 4) { r = v(0); g = v(1); b = v(2); al = v(3); }
    else if (canaux === 3) { r = v(0); g = v(1); b = v(2); }
    else if (canaux === 2) { r = g = b = v(0); al = v(1); }
    else { r = g = b = v(0); }
    out[i * 4] = r; out[i * 4 + 1] = g; out[i * 4 + 2] = b; out[i * 4 + 3] = al;
  }
  return { w, h, px: out };
}

const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC[(c ^ buf[i]) & 255] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function morceau(type, data) {
  const l = Buffer.alloc(4); l.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type, 'latin1'), data]);
  const c = Buffer.alloc(4); c.writeUInt32BE(crc32(td));
  return Buffer.concat([l, td, c]);
}
export function ecrisPNG(w, h, px) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  /* Pour chaque ligne, on essaie les cinq filtres PNG et on garde celui
     dont la somme des écarts est la plus petite : l'heuristique que
     recommande la norme, et celle de la plupart des encodeurs. */
  const L = w * 4, brut = Buffer.alloc((L + 1) * h), essai = Buffer.alloc(L);
  for (let y = 0; y < h; y++) {
    const o = y * L, d = y * (L + 1);
    let meilleur = 0, score = Infinity;
    for (let f = 0; f < 5; f++) {
      let s = 0;
      for (let i = 0; i < L; i++) {
        const x = px[o + i], a = i >= 4 ? px[o + i - 4] : 0, b = y > 0 ? px[o - L + i] : 0;
        const c = (i >= 4 && y > 0) ? px[o - L + i - 4] : 0;
        let p;
        if (f === 0) p = 0; else if (f === 1) p = a; else if (f === 2) p = b;
        else if (f === 3) p = (a + b) >> 1;
        else { const q = a + b - c, pa = Math.abs(q - a), pb = Math.abs(q - b), pc = Math.abs(q - c);
               p = pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
        const v = (x - p) & 255;
        essai[i] = v; s += v < 128 ? v : 256 - v;
        if (s >= score) break;
      }
      if (s < score) { score = s; meilleur = f; essai.copy(brut, d + 1, 0, L); }
    }
    brut[d] = meilleur;
  }
  return Buffer.concat([SIGNATURE, morceau('IHDR', ihdr),
                        morceau('IDAT', deflateSync(brut, { level: 9 })), morceau('IEND', Buffer.alloc(0))]);
}

/* ---------------------------------------------------------------
   ROGNAGE ET RANGEMENT
   --------------------------------------------------------------- */
function rogne(img, seuil) {
  let x0 = img.w, y0 = img.h, x1 = -1, y1 = -1;
  for (let y = 0; y < img.h; y++)
    for (let x = 0; x < img.w; x++)
      if (img.px[(y * img.w + x) * 4 + 3] >= seuil) {
        if (x < x0) x0 = x; if (x > x1) x1 = x;
        if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
  if (x1 < 0) return { x0: 0, y0: 0, w: 1, h: 1 };     // image vide : un pixel
  return { x0, y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
}

/* Rangement en étagères, les plus hautes d'abord. Simple, déterministe,
   et largement suffisant pour quelques centaines d'images de même
   gabarit. */
function range(boites, largeurMax, marge) {
  const ordre = boites.map((b, i) => i).sort((a, b) => boites[b].h - boites[a].h || boites[b].w - boites[a].w);
  let x = marge, y = marge, hEtagere = 0, larg = 0;
  for (const i of ordre) {
    const b = boites[i];
    if (x + b.w + marge > largeurMax && x > marge) { x = marge; y += hEtagere + marge; hEtagere = 0; }
    b.px0 = x; b.py0 = y;
    x += b.w + marge;
    if (b.h > hEtagere) hEtagere = b.h;
    if (x > larg) larg = x;
  }
  return { w: Math.max(1, larg), h: Math.max(1, y + hEtagere + marge) };
}

/* ---------------------------------------------------------------
   PROGRAMME
   --------------------------------------------------------------- */
function options(argv) {
  const o = { entree: null, sortie: null, marge: 2, largeur: 2048, seuil: 1, integrer: true };
  const pos = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--image-separee') o.integrer = false;
    else if (a === '--integrer') o.integrer = true;
    else if (a.startsWith('--')) o[a.slice(2)] = Number(argv[++i]);
    else pos.push(a);
  }
  [o.entree, o.sortie] = pos;
  if (!o.entree || !o.sortie) {
    console.error('usage : node tools/spritesheet/sp_assembler.mjs <dossier-rendu> <dossier-sortie> [--marge 2] [--largeur 2048] [--image-separee]');
    process.exit(1);
  }
  return o;
}

export function assemble(o) {
  const cheminManifeste = join(o.entree, 'manifeste.json');
  if (!existsSync(cheminManifeste)) throw new Error('manifeste introuvable : ' + cheminManifeste);
  const man = JSON.parse(readFileSync(cheminManifeste, 'utf8'));
  if (man.format !== 'smashpei-rendu/1') throw new Error('manifeste inconnu : ' + man.format);
  const perso = man.perso;

  const boites = [];
  for (const [nom, anim] of Object.entries(man.animations)) {
    for (const im of anim.images) {
      const img = lisPNG(readFileSync(join(o.entree, im.fichier)));
      const r = rogne(img, o.seuil);
      boites.push({ nom, im, img, ...r });
    }
  }
  if (!boites.length) throw new Error('aucune image dans le manifeste');

  const taille = range(boites, o.largeur, o.marge);
  const px = Buffer.alloc(taille.w * taille.h * 4);
  for (const b of boites) {
    for (let y = 0; y < b.h; y++) {
      const src = ((b.y0 + y) * b.img.w + b.x0) * 4;
      b.img.px.copy(px, ((b.py0 + y) * taille.w + b.px0) * 4, src, src + b.w * 4);
    }
  }
  const png = ecrisPNG(taille.w, taille.h, px);

  const animations = {};
  for (const [nom, anim] of Object.entries(man.animations)) animations[nom] = { boucle: !!anim.boucle, frames: [] };
  for (const b of boites) {
    const [ox, oy] = b.im.origine;
    const fr = {
      x: b.px0, y: b.py0, w: b.w, h: b.h,
      ox: +(ox - b.x0).toFixed(2), oy: +(oy - b.y0).toFixed(2),
      pose: b.im.pose, _i: b.im.fichier
    };
    /* Les ancres mesurées par Blender (tête, poitrine, bassin), ramenées
       en pixels de JEU, relatives aux pieds : le jeu y pose les
       accessoires du vestiaire. Indispensables en vue trois-quarts, où le
       squelette 3D ne tombe plus exactement sur le dessin vectoriel. */
    const A = b.im.ancres;
    if (A && A.tete && A.poitrine && A.bassin) {
      const e = man.echelle || 1, jeu = p => [+((p[0] - ox) / e).toFixed(2), +((p[1] - oy) / e).toFixed(2)];
      const [hx, hy] = jeu(A.tete), [cx, cy] = jeu(A.poitrine), [bx, by] = jeu(A.bassin);
      fr.ancres = { hx, hy, cx, cy, hipX: bx, hipY: by };
    }
    animations[b.nom].frames.push(fr);
  }
  /* on remet les images dans l'ordre de l'animation */
  for (const a of Object.values(animations)) {
    a.frames.sort((p, q) => (p._i < q._i ? -1 : 1));
    for (const f of a.frames) delete f._i;
  }

  const meta = {
    format: 'smashpei-sprites/1', perso, image: perso + '.png',
    echelle: man.echelle, tete: man.tete || 'vectorielle', rig: man.rig,
    taille: [taille.w, taille.h], animations
  };
  mkdirSync(o.sortie, { recursive: true });
  writeFileSync(join(o.sortie, perso + '.png'), png);
  writeFileSync(join(o.sortie, perso + '.json'), JSON.stringify(meta, null, 1));
  const pourJs = o.integrer ? Object.assign({}, meta, { imageData: 'data:image/png;base64,' + png.toString('base64') }) : meta;
  const js = '/* Smash Péi — planche « ' + perso + ' », générée par tools/spritesheet/sp_assembler.mjs. Ne pas modifier à la main. */\n' +
    '(function (M) { if (window.SPRITES && SPRITES.enregistrer) SPRITES.enregistrer(M);\n' +
    '  else (window.SPRITES_EN_ATTENTE = window.SPRITES_EN_ATTENTE || []).push(M); })(' +
    JSON.stringify(pourJs) + ');\n';
  writeFileSync(join(o.sortie, perso + '.sprites.js'), js);
  return { perso, images: boites.length, taille, octets: png.length };
}

if (process.argv[1] && basename(process.argv[1]) === basename(new URL(import.meta.url).pathname)) {
  const o = options(process.argv.slice(2));
  try {
    const r = assemble(o);
    console.log(`Smash Péi : ${r.images} images -> ${join(o.sortie, r.perso + '.png')} (${r.taille.w}×${r.taille.h}, ${(r.octets / 1024).toFixed(0)} Ko)`);
  } catch (e) {
    console.error('Smash Péi : ' + e.message);
    process.exit(1);
  }
}
