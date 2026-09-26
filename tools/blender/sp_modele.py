# -*- coding: utf-8 -*-
"""
SMASH PÉI — MODÈLES 3D DES COMBATTANTS, CONSTRUITS PAR LE CODE
================================================================

Ce script fabrique dans Blender un VRAI personnage 3D — maillage organique
lissé, vêtements, visage, cheveux, accessoires, peau pondérée sur le
squelette — à partir de la fiche du combattant dans le jeu. Le fichier
produit se rend ensuite comme n'importe quel modèle avec
`sp_rendu_spritesheet.py`.

Le but : l'ASPECT des rendus de Smash Bros Ultimate (proportions trapues,
grosse tête, grosses mains, matières lisibles, visage expressif, éclairage à
contre-jour), appliqué à NOS personnages. On reprend un style, jamais un
personnage existant.

UTILISATION
-----------
  1. Exporter les poses depuis le jeu (console du navigateur) :
         SPRITES.exporterPoses('tijean')
     et ranger le fichier dans rendus/tijean/tijean.poses.json

  2. Construire le modèle :
         blender -b --python tools/blender/sp_modele.py -- \\
             --poses rendus/tijean/tijean.poses.json
     -> rendus/tijean/tijean.blend  (armature SP_Rig en vue trois-quarts,
        le modèle attaché, les matières SP_*)

  3. Rendre les images, en style Ultimate, tête comprise :
         blender -b rendus/tijean/tijean.blend --python tools/blender/sp_rendu_spritesheet.py -- \\
             --poses rendus/tijean/tijean.poses.json --mode rendu --style ultimate --tete sprite \\
             --taille 448 --marge 1.6
     (131 images ; quelques minutes avec une carte graphique. Sans carte
     graphique, EEVEE tourne en logiciel : compter environ 40 s par image,
     et lancer deux Blender en parallèle sur des --anims différentes.)

  4. Assembler :  node tools/spritesheet/sp_assembler.mjs rendus/tijean sprites

  Le fichier .blend reste ouvert à la retouche : chaque pièce est un objet
  nommé (« TJ_tete », « TJ_gilet », « TJ_sabre_lame »...), chaque matière une
  SP_*. Un artiste peut sculpter par-dessus, repeindre, remplacer une pièce :
  le squelette et la chaîne de rendu ne changent pas.

PERSONNAGES DISPONIBLES
-----------------------
  tijean      Ti Jean, l'épéiste des contes créoles.
  Ajouter un personnage = écrire une fonction `recette_<id>` sur le modèle de
  `recette_tijean` et l'inscrire dans RECETTES.

OPTIONS
-------
  --poses FICHIER   le .poses.json exporté par le jeu (obligatoire)
  --sortie DOSSIER  par défaut, celui du fichier de poses
  --lacet DEGRÉS    rotation du corps vers la caméra (30 : presque de profil,
                    comme en jeu dans Smash ; le visage, lui, se tourne de
                    TETE_VERS_CAMERA degrés de plus vers le joueur)
  --unite M         mètres par pixel de jeu (0.01)
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_rendu_spritesheet as SP     # noqa: E402

try:
    import bpy
    import bmesh
    from mathutils import Vector
except ImportError:
    bpy = None


# ---------------------------------------------------------------------------
# 1) LE REPÈRE DU CORPS
#    Tout le modèle est décrit dans les unités du jeu (pixels), dans le repère
#    du corps : f vers l'avant, u vers le haut, l sur le côté (positif vers le
#    fond, loin de la caméra). `C.P` convertit en coordonnées Blender.
# ---------------------------------------------------------------------------

class Corps:
    def __init__(self, doc, arm, unite, lacet):
        self.doc, self.rig, self.arm, self.unite = doc, doc['rig'], arm, unite
        self.F, self.U, self.L = (Vector(v) for v in SP.repere_corps('trois-quarts', lacet))
        self.os = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local)
                   for b in arm.data.bones}

    def P(self, f, u, l=0.0):
        """Point du corps (pixels de jeu) -> Vector Blender (mètres)."""
        return (self.F * f + self.U * u + self.L * l) * self.unite

    def px(self, v):
        """Longueur en pixels de jeu -> mètres."""
        return v * self.unite

    def tourne(self, degres):
        """(F, L) pivotés autour de la verticale, vers la caméra."""
        a = math.atan2(-self.F.y, self.F.x) + math.radians(degres)
        return Vector((math.cos(a), -math.sin(a), 0.0)), Vector((math.sin(a), math.cos(a), 0.0))

    def long_os(self, nom, t):
        """Point à la fraction t de l'os `nom` (0 = tête de l'os, 1 = queue)."""
        a, b = self.os[nom]
        return a.lerp(b, t)


# Le visage se tourne davantage vers la caméra que le corps : c'est la pose
# des combattants de Smash en jeu (corps de profil, regard vers le joueur).
TETE_VERS_CAMERA = 30.0


# ---------------------------------------------------------------------------
# 2) LA FABRIQUE DE FORMES
#    Des anneaux elliptiques reliés en quadrilatères : la base de toute la
#    sculpture. Le modificateur Subdivision Surface les arrondit ensuite, ce
#    qui donne des volumes organiques (biceps, mollets, cage thoracique) à
#    partir de quelques anneaux seulement.
# ---------------------------------------------------------------------------

def _objet(nom, bm, lisse=True):
    me = bpy.data.meshes.new(nom)
    if lisse:
        for fa in bm.faces:
            fa.smooth = True
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def anneaux(nom, sections, n=16, fermer_debut=True, fermer_fin=True, boucle=False):
    """sections : liste de (centre, axe_a, axe_b, ra, rb) — un anneau elliptique
    par section, dans le plan (axe_a, axe_b). `boucle` referme le tube sur
    lui-même (ceinture, revers)."""
    bm = bmesh.new()
    rangs = []
    for c, a, b, ra, rb in sections:
        rang = []
        for k in range(n):
            t = 2 * math.pi * k / n
            rang.append(bm.verts.new(c + a * (math.cos(t) * ra) + b * (math.sin(t) * rb)))
        rangs.append(rang)
    nr = len(rangs)
    for i in range(nr if boucle else nr - 1):
        r0, r1 = rangs[i], rangs[(i + 1) % nr]
        for k in range(n):
            bm.faces.new((r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]))
    if not boucle:
        for rang, fermer, sens in ((rangs[0], fermer_debut, -1), (rangs[-1], fermer_fin, 1)):
            if not fermer:
                continue
            i0, i1 = (0, 1) if sens < 0 else (-1, -2)
            c0 = sum((v.co for v in rang), Vector()) / n
            vois = sum((v.co for v in rangs[i1]), Vector()) / n
            pole = bm.verts.new(c0 + (c0 - vois) * 0.18)
            for k in range(n):
                if sens < 0:
                    bm.faces.new((rang[(k + 1) % n], rang[k], pole))
                else:
                    bm.faces.new((rang[k], rang[(k + 1) % n], pole))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return _objet(nom, bm)


def tube(C, nom, points, rayons, n=16, axe_ref=None, **kw):
    """Un tube le long d'une ligne de points (Vector), rayons = [(ra, rb)] en
    pixels de jeu ; ra suit l'axe de référence (par défaut le côté du corps)."""
    ref = axe_ref or C.L
    sections = []
    for i, p in enumerate(points):
        if i == 0:
            t = points[1] - points[0]
        elif i == len(points) - 1:
            t = points[-1] - points[-2]
        else:
            t = points[i + 1] - points[i - 1]
        t.normalize()
        a = (ref - t * ref.dot(t))
        if a.length < 1e-6:
            a = C.F.copy()
        a.normalize()
        b = t.cross(a).normalized()
        ra, rb = rayons[i]
        sections.append((p, a, b, C.px(ra), C.px(rb)))
    return anneaux(nom, sections, n=n, **kw)


def ellipsoide(C, nom, centre, rf, ru, rl, axes=None, seg=24, anneaux_=12, deforme=None):
    """Un ellipsoïde dans le repère (F, U, L) — ou dans `axes` = (a1, a2, a3).
    `deforme(x, y, z)` reçoit les coordonnées unitaires et renvoie un
    multiplicateur (fx, fy, fz) : c'est là qu'on sculpte mâchoire et crâne."""
    A1, A2, A3 = axes or (C.F, C.U, C.L)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=anneaux_, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co.x, v.co.z, v.co.y        # x avant, y haut, z côté
        kx = ky = kz = 1.0
        if deforme:
            kx, ky, kz = deforme(x, y, z)
        v.co = centre + A1 * (x * rf * kx) + A2 * (y * ru * ky) + A3 * (z * rl * kz)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return _objet(nom, bm)


def supprime_faces(ob, garde):
    """Retire les faces dont le centre ne passe pas garde(co) : sur un maillage
    fin, le bord de l'ouverture reste net (au lieu d'être déchiqueté)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[fa for fa in bm.faces if not garde(fa.calc_center_median())],
                     context='FACES')
    bm.to_mesh(ob.data)
    bm.free()


def supprime_sommets(ob, garde):
    """Retire les sommets pour lesquels garde(co) est faux (ouvertures)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not garde(v.co)], context='VERTS')
    bm.to_mesh(ob.data)
    bm.free()


# ---------------------------------------------------------------------------
# 3) LA PEAU : pondération sur le squelette
#    Chaque pièce déclare les os qui ont le droit de la déformer. Le poids d'un
#    os décroît avec la distance du sommet au segment de l'os : aux coudes et
#    aux genoux, deux os se partagent les sommets et la pliure est douce.
#    Restreindre les os par pièce évite l'erreur classique d'un bras qui
#    emporte un morceau de torse.
# ---------------------------------------------------------------------------

def _dist_segment(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def lie(C, ob, os_permis, rigide=False, lisse=2, extras=()):
    """Attache `ob` à l'armature : poids par distance aux os permis (ou
    entièrement au premier os si `rigide`). Ajoute ensuite les modificateurs
    `extras` puis la subdivision : l'armature passe toujours en premier."""
    groupes = {n: ob.vertex_groups.new(name=n) for n in os_permis}
    for v in ob.data.vertices:
        if rigide:
            groupes[os_permis[0]].add([v.index], 1.0, 'REPLACE')
            continue
        d = sorted(((_dist_segment(v.co, *C.os[n]), n) for n in os_permis))[:2]
        eps = C.px(0.6)
        w = [(1.0 / (di + eps) ** 4, n) for di, n in d]
        s = sum(x for x, _ in w)
        for x, n in w:
            if x / s > 0.02:
                groupes[n].add([v.index], x / s, 'REPLACE')
    m = ob.modifiers.new('SP_Rig', 'ARMATURE')
    m.object = C.arm
    m.use_deform_preserve_volume = True
    for type_, reglages in extras:
        mm = ob.modifiers.new(type_.lower(), type_)
        for k, val in reglages.items():
            setattr(mm, k, val)
    if lisse:
        s = ob.modifiers.new('lisse', 'SUBSURF')
        s.levels = 1
        s.render_levels = lisse
    ob.parent = C.arm
    return ob


def habille(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob


# ---------------------------------------------------------------------------
# 4) MATIÈRES PROPRES AUX MODÈLES
# ---------------------------------------------------------------------------

def mat_cheveux(nom, hexa):
    m = SP.materiau(nom, hexa, 'cuir')
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    SP.entree(b, ('Roughness',), 0.36)
    SP.entree(b, ('Sheen Weight', 'Sheen'), 0.5)
    SP.entree(b, ('Coat Weight', 'Clearcoat'), 0.25)
    return m


def mat_oeil(nom, hexa, rugosite=0.2, vernis=0.0, emission=0.0):
    m = SP.materiau(nom, hexa, 'caoutchouc')
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    SP.entree(b, ('Roughness',), rugosite)
    SP.entree(b, ('Coat Weight', 'Clearcoat'), vernis)
    if emission:
        SP.entree(b, ('Emission Color', 'Emission'), (1.0, 1.0, 1.0, 1.0))
        SP.entree(b, ('Emission Strength',), emission)
    return m


# ---------------------------------------------------------------------------
# 5) TI JEAN
#    Le héros des contes créoles, sabre au clair. Fiche du jeu : peau
#    #c8875a, gilet bleu #2e5f8a à boutons dorés #e8c547, cape rouge
#    #9c2b34, cheveux #2b1d12, chaussures #4a3423, tête ovale, sabre.
#    Proportions à la manière de Smash : tête d'un tiers de la hauteur,
#    grosses mains, pieds solides, buste en tonneau court.
# ---------------------------------------------------------------------------

def recette_tijean(C):
    pal = C.doc.get('palette', {})
    u = C.unite
    M = {
        'peau': SP.materiau('SP_peau', pal.get('skin', '#c8875a'), 'peau', u),
        'mains': SP.materiau('SP_mains', pal.get('hand', '#d99a6c'), 'peau', u),
        'gilet': SP.materiau('SP_gilet', pal.get('cloth', '#2e5f8a'), 'tissu', u),
        'pantalon': SP.materiau('SP_pantalon', '#e6dcc4', 'tissu', u),
        'ceinture': SP.materiau('SP_ceinture', '#5a3a22', 'cuir', u),
        'chaussures': SP.materiau('SP_chaussures', '#6a4a30', 'cuir', u),
        'cape': SP.materiau('SP_cape', pal.get('cape', '#9c2b34'), 'tissu', u),
        'dore': SP.materiau('SP_dore', pal.get('accent', '#e8c547'), 'metal', u),
        'lame': SP.materiau('SP_lame', '#f4f8fc', 'metal', u),
        'poignee': SP.materiau('SP_poignee', '#6b3f1d', 'cuir', u),
        'cheveux': mat_cheveux('SP_cheveux', pal.get('hair', '#2b1d12')),
        'blanc_oeil': mat_oeil('SP_blanc_oeil', '#f3efe6', 0.3),
        'iris': mat_oeil('SP_iris', pal.get('eye', '#3a2414'), 0.12, 1.0),
        'pupille': mat_oeil('SP_pupille', '#070504', 0.1, 1.0),
        'reflet': mat_oeil('SP_reflet', '#ffffff', 0.1, 0.0, 6.0),
        'levres': SP.materiau('SP_levres', '#6a2c22', 'peau', u),
    }
    # une lame doit se lire de loin : un métal clair, un vernis qui accroche
    # le contre-jour
    b = next(n for n in M['lame'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    SP.entree(b, ('Roughness',), 0.22)
    SP.entree(b, ('Metallic',), 0.75)
    SP.entree(b, ('Coat Weight', 'Clearcoat'), 0.8)
    b = next(n for n in M['dore'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    SP.entree(b, ('Roughness',), 0.24)

    P, F, U, L = C.P, C.F, C.U, C.L
    hanche, poitrine = C.os['torse']
    h0 = hanche.dot(U) / u                     # hauteur de la hanche, en px
    h1 = poitrine.dot(U) / u
    H = lambda t: h0 + (h1 - h0) * t           # hauteur le long du buste

    # ---------------- le buste (peau, visible au col et aux épaules)
    profil = [  # (hauteur, demi-largeur, demi-profondeur, décalage avant) — un buste en tonneau
        (H(-0.20), 8.0, 7.0, 0.0), (H(-0.05), 11.4, 8.8, 0.3), (H(0.15), 11.8, 9.2, 0.7),
        (H(0.36), 10.8, 8.8, 1.2), (H(0.58), 12.6, 9.8, 1.8), (H(0.80), 13.8, 10.0, 1.6),
        (H(0.95), 13.0, 8.6, 0.5), (H(1.06), 8.4, 6.0, -0.4), (H(1.12), 4.8, 4.6, -0.3)]
    def sections_buste(gonfle=0.0, plage=None, pas=None):
        if pas:                      # rééchantillonné finement entre deux hauteurs
            out = []
            for k in range(pas + 1):
                hh = plage[0] + (plage[1] - plage[0]) * k / pas
                for (h_a, *va), (h_b, *vb) in zip(profil, profil[1:]):
                    if h_a <= hh <= h_b:
                        t = (hh - h_a) / (h_b - h_a)
                        lw, fd, off = (x + (y - x) * t for x, y in zip(va, vb))
                        out.append((P(off, hh), L, -F, u * (lw + gonfle), u * (fd + gonfle)))
                        break
            return out
        out = []
        for hh, lw, fd, off in profil:
            if plage and not (plage[0] <= hh <= plage[1]):
                continue
            out.append((P(off, hh), L, -F, u * (lw + gonfle), u * (fd + gonfle)))
        return out
    buste = anneaux('TJ_buste', sections_buste(), n=20)
    lie(C, habille(buste, M['peau']), ['torse'], rigide=True)

    # ---------------- le cou
    tete_c = C.os['tete'][0]
    cou = tube(C, 'TJ_cou', [P(-0.4, H(1.0)), P(-0.2, H(1.12)), tete_c - U * C.px(8.0)],
               [(4.6, 4.4), (4.2, 4.0), (4.0, 3.9)], n=12)
    lie(C, habille(cou, M['peau']), ['cou', 'tete', 'torse'])

    # ---------------- la tête : crâne ovale, mâchoire, joues
    # Le corps est presque de profil (le combat se lit mieux ainsi, comme en
    # jeu dans Smash) mais le VISAGE se tourne vers la caméra : on construit
    # toute la tête dans un repère pivoté de TETE_VERS_CAMERA degrés.
    F, L = C.tourne(TETE_VERS_CAMERA)
    r = C.rig['headR'] * 0.98
    rf, ru, rl = r * 1.0, r * 1.08, r * 0.93
    def crane(x, y, z):
        kx = ky = kz = 1.0
        if y < -0.2:                                # mâchoire qui se resserre
            k = (-y - 0.2) / 0.8
            kz -= 0.16 * k
            if x > 0:
                kx += 0.05 * k                      # menton en avant
        if x < -0.1 and y > -0.3:
            kx *= 1.05                              # arrière du crâne plus rond
        if -0.45 < y < 0.0 and x > 0.2:
            kz += 0.04                              # joues
        return kx, ky, kz
    tete = ellipsoide(C, 'TJ_tete', tete_c, C.px(rf), C.px(ru), C.px(rl), axes=(F, U, L), seg=40, anneaux_=24,
                      deforme=crane)
    lie(C, habille(tete, M['peau']), ['tete'], rigide=True)

    def surface(yu, zl, dehors=0.0):
        """Point de la surface du crâne (fractions haut / côté) + normale."""
        x = math.sqrt(max(0.0, 1.0 - yu * yu - zl * zl))
        p = tete_c + F * C.px(rf * x) + U * C.px(ru * yu) + L * C.px(rl * zl)
        n = (F * (x / rf) + U * (yu / ru) + L * (zl / rl)).normalized()
        return p + n * C.px(dehors), n

    pieces_tete = []
    # le nez
    pn, nn = surface(-0.10, 0.0)
    pieces_tete.append(habille(ellipsoide(C, 'TJ_nez', pn + nn * C.px(1.0), C.px(r * 0.21),
                                          C.px(r * 0.18), C.px(r * 0.17), axes=(F, U, L), seg=16, anneaux_=8),
                               M['peau']))
    # les yeux : grands, un peu tournés vers la caméra
    vers_camera = (F * 0.92 - L * 0.2).normalized()
    for cote, zl in (('av', -0.36), ('ar', 0.34)):
        po, no = surface(0.13, zl)
        dirn = (no * 0.5 + vers_camera * 0.5).normalized()
        cote_ax = U.cross(dirn).normalized()
        ax = (dirn, U, cote_ax)
        c0 = po - no * C.px(r * 0.03)
        pieces_tete.append(habille(ellipsoide(C, 'TJ_oeil_' + cote, c0, C.px(r * 0.13), C.px(r * 0.27),
                                              C.px(r * 0.19), axes=ax, seg=20, anneaux_=12), M['blanc_oeil']))
        ci = c0 + dirn * C.px(r * 0.115) + U * C.px(r * -0.02)
        pieces_tete.append(habille(ellipsoide(C, 'TJ_iris_' + cote, ci, C.px(r * 0.035), C.px(r * 0.17),
                                              C.px(r * 0.13), axes=ax, seg=16, anneaux_=8), M['iris']))
        cp = ci + dirn * C.px(r * 0.022)
        pieces_tete.append(habille(ellipsoide(C, 'TJ_pupille_' + cote, cp, C.px(r * 0.02), C.px(r * 0.09),
                                              C.px(r * 0.07), axes=ax, seg=12, anneaux_=6), M['pupille']))
        cr = cp + dirn * C.px(r * 0.02) + U * C.px(r * 0.07) - cote_ax * C.px(r * 0.05)
        pieces_tete.append(habille(ellipsoide(C, 'TJ_reflet_' + cote, cr, C.px(r * 0.03), C.px(r * 0.035),
                                              C.px(r * 0.03), seg=8, anneaux_=4), M['reflet']))
        # le sourcil : épais, arqué, déterminé
        pts = [surface(0.30 + dy, zl + dz, r * 0.03)[0] for dz, dy in ((-0.17, -0.02), (0.0, 0.05), (0.15, 0.02))]
        if zl > 0:
            pts.reverse()
        pieces_tete.append(habille(tube(C, 'TJ_sourcil_' + cote, pts, [(r * 0.045, r * 0.07)] * 3, n=8,
                                        axe_ref=U), M['cheveux']))
    # la bouche : un sourire en coin
    pts = [surface(yu, zl, r * 0.012)[0] for yu, zl in ((-0.40, -0.20), (-0.47, -0.04), (-0.45, 0.10), (-0.39, 0.18))]
    pieces_tete.append(habille(tube(C, 'TJ_bouche', pts, [(r * 0.035, r * 0.04)] * 4, n=8, axe_ref=U),
                               M['levres']))
    # les oreilles
    for s_ in (1, -1):
        c_ = tete_c + L * C.px(rl * 0.96 * s_) - F * C.px(r * 0.06) - U * C.px(r * 0.05)
        pieces_tete.append(habille(ellipsoide(C, 'TJ_oreille', c_, C.px(r * 0.2), C.px(r * 0.29),
                                              C.px(r * 0.09), axes=(F, U, L), seg=16, anneaux_=8), M['peau']))

    # ---------------- les cheveux : une calotte et des mèches épaisses
    calotte = ellipsoide(C, 'TJ_cheveux', tete_c + U * C.px(r * 0.04), C.px(rf * 1.07),
                         C.px(ru * 1.05), C.px(rl * 1.08), axes=(F, U, L), seg=40, anneaux_=24)
    def garde_cheveux(co):
        d = co - tete_c
        x, y = d.dot(F) / C.px(rf), d.dot(U) / C.px(ru)
        seuil = 0.42 if x > 0.35 else (0.16 if x > -0.25 else -0.55)
        if -0.25 < x <= 0.35:
            seuil = 0.16 + (x + 0.25) / 0.6 * 0.26
        return y > seuil
    supprime_sommets(calotte, garde_cheveux)
    # une épaisseur, pour que le bord de la calotte ne montre pas son envers
    ep = calotte.modifiers.new('epaisseur', 'SOLIDIFY')
    ep.thickness = C.px(1.2)
    ep.offset = -1.0
    pieces_tete.append(habille(calotte, M['cheveux']))
    meches = [  # (haut, côté, avant/arrière, direction (f, u, l), longueur, épaisseur), fractions de r
        (0.95, 0.00, 1, (-0.2, 1.0, 0.0), 0.55, 0.26), (0.85, -0.35, 1, (-0.1, 0.9, -0.5), 0.5, 0.24),
        (0.85, 0.35, -1, (-0.3, 0.9, 0.5), 0.5, 0.24), (0.66, -0.62, -1, (-0.6, 0.5, -0.6), 0.5, 0.24),
        (0.66, 0.62, -1, (-0.6, 0.5, 0.6), 0.5, 0.24), (0.50, 0.00, -1, (-1.0, 0.4, 0.0), 0.6, 0.28),
        (0.35, -0.45, -1, (-1.0, 0.0, -0.4), 0.55, 0.24), (0.35, 0.45, -1, (-1.0, 0.0, 0.4), 0.55, 0.24),
        (0.74, -0.18, 1, (0.8, 0.5, -0.2), 0.45, 0.22), (0.70, 0.18, 1, (0.8, 0.4, 0.3), 0.42, 0.2),
    ]
    for i, (yu, zl, sx, d, lg, ep) in enumerate(meches):
        x = sx * math.sqrt(max(0.0, 1 - yu * yu - zl * zl))
        base = tete_c + F * C.px(rf * 1.02 * x) + U * C.px(ru * 1.02 * yu) + L * C.px(rl * 1.02 * zl)
        dv = (F * d[0] + U * d[1] + L * d[2]).normalized()
        courbe = (dv - U * 0.35).normalized()
        pts = [base - dv * C.px(r * 0.12), base + dv * C.px(r * lg * 0.45),
               base + (dv * 0.6 + courbe * 0.4).normalized() * C.px(r * lg * 0.8), base + courbe * C.px(r * lg)]
        pieces_tete.append(habille(tube(C, 'TJ_meche_%d' % i, pts,
                                        [(r * ep, r * ep * 0.8), (r * ep * 0.85, r * ep * 0.7),
                                         (r * ep * 0.45, r * ep * 0.38), (r * 0.02, r * 0.02)], n=10), M['cheveux']))
    for ob in pieces_tete:
        lie(C, ob, ['tete'], rigide=True, lisse=1)
    F, L = C.F, C.L                              # retour au repère du corps

    # ---------------- le gilet : ouvert en V, sans manches
    # Une surface paramétrée plutôt qu'un tube découpé : chaque rangée ne
    # couvre que l'angle HORS du V, et le haut descend sous les bras pour
    # former les emmanchures. Les bords sont nets par construction.
    def profil_a(hh):
        for (h_a, *va), (h_b, *vb) in zip(profil, profil[1:]):
            if h_a <= hh <= h_b:
                t = (hh - h_a) / (h_b - h_a)
                return [x + (y - x) * t for x, y in zip(va, vb)]
        return profil[-1][1:] if hh > profil[-1][0] else profil[0][1:]

    bas, haut, emman = H(0.10), H(0.97), H(0.70)
    def v_col(hh):                               # demi-angle du V, en degrés
        t = (hh - H(0.50)) / (haut - H(0.50))
        return 4.0 + 58.0 * max(0.0, min(1.0, t)) ** 0.9

    def bretelle(phi):                           # 1 devant et dans le dos, 0 sous les bras
        a = abs((phi + 180.0) % 360.0 - 180.0)   # 0 = devant, 180 = dos
        devant = max(0.0, min(1.0, (82.0 - a) / 16.0))
        dos = max(0.0, min(1.0, (a - 112.0) / 16.0))
        return max(devant, dos)

    nx, ny = 56, 18
    bm = bmesh.new()
    grille = []
    for j in range(ny + 1):
        v = j / ny
        rang = []
        for i in range(nx + 1):
            s_ = i / nx
            h_nom = bas + (haut - bas) * v
            th = v_col(h_nom)
            phi = th + s_ * (360.0 - 2 * th)
            h_top = emman + (haut - emman) * bretelle(phi)
            hh = bas + (h_top - bas) * v
            th = v_col(hh)
            phi = th + s_ * (360.0 - 2 * th)
            lw, fd, off = profil_a(hh)
            g = 1.25
            ph = math.radians(phi)
            rang.append(bm.verts.new(P(off + (fd + g) * math.cos(ph), hh) + L * C.px((lw + g) * math.sin(ph))))
        grille.append(rang)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((grille[j][i], grille[j][i + 1], grille[j + 1][i + 1], grille[j + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    gilet = _objet('TJ_gilet', bm)
    lie(C, habille(gilet, M['gilet']), ['torse'], rigide=True,
        extras=[('SOLIDIFY', {'thickness': C.px(1.1), 'offset': 0.0})])

    # le passepoil doré : il souligne le V et l'ourlet, et accroche la lumière
    def point_gilet(hh, phi, g=1.9):
        lw, fd, off = profil_a(hh)
        ph = math.radians(phi)
        return P(off + (fd + g) * math.cos(ph), hh) + L * C.px((lw + g) * math.sin(ph))
    bords = []
    for sgn in (1, -1):
        bords.append([point_gilet(bas + (haut - bas) * k / 14, sgn * v_col(bas + (haut - bas) * k / 14))
                      for k in range(15)])
    bords.append([point_gilet(bas, v_col(bas) + (360 - 2 * v_col(bas)) * k / 40) for k in range(41)])
    for i, pts in enumerate(bords):
        pp = tube(C, 'TJ_passepoil_%d' % i, pts, [(0.5, 0.5)] * len(pts), n=6, axe_ref=U if i == 2 else L,
                  fermer_debut=True, fermer_fin=True)
        lie(C, habille(pp, M['dore']), ['torse'], rigide=True, lisse=1)
    for i, t in enumerate((0.18, 0.32, 0.46)):
        hh = H(t)
        lw, fd, off = profil_a(hh)
        bouton = ellipsoide(C, 'TJ_bouton_%d' % i, P(off + fd + 2.5, hh), C.px(0.7), C.px(1.2), C.px(1.2),
                            seg=12, anneaux_=6)
        lie(C, habille(bouton, M['dore']), ['torse'], rigide=True, lisse=1)

    # ---------------- le pantalon, la ceinture
    bassin = anneaux('TJ_bassin', [(P(0.2, H(-0.24)), L, -F, u * 8.9, u * 8.2),
                                   (P(0.3, H(-0.08)), L, -F, u * 12.6, u * 10.0),
                                   (P(0.7, H(0.12)), L, -F, u * 13.0, u * 10.4),
                                   (P(1.1, H(0.26)), L, -F, u * 12.3, u * 9.9)], n=20, fermer_fin=False)
    lie(C, habille(bassin, M['pantalon']), ['torse'], rigide=True)
    ceinture = anneaux('TJ_ceinture', [
        (P(0.6 + 10.7 * math.cos(t), H(0.07)) + L * C.px(13.2 * math.sin(t)),
         (F * -math.sin(t) + L * math.cos(t)).normalized().cross(U), U, u * 0.9, u * 1.4)
        for t in (2 * math.pi * k / 24 for k in range(24))], n=8, boucle=True)
    lie(C, habille(ceinture, M['ceinture']), ['torse'], rigide=True, lisse=1)
    boucle = anneaux('TJ_boucle', [
        (P(0.6 + 10.7 + 1.1, H(0.07)) + (U * math.cos(t) * 2.1 + L * math.sin(t) * 2.5) * u,
         F.cross(U * -math.sin(t) + L * math.cos(t)).normalized(), F, u * 0.45, u * 0.45)
        for t in (2 * math.pi * k / 16 for k in range(16))], n=6, boucle=True)
    lie(C, habille(boucle, M['dore']), ['torse'], rigide=True, lisse=1)

    # ---------------- bras (peau) et mains
    for cote in ('L', 'R'):
        e, c_ = C.os['bras.' + cote]
        _, poignet = C.os['avantbras.' + cote]
        pts = [e.lerp(c_, t) for t in (0.0, 0.3, 0.65, 1.0)] + \
              [c_.lerp(poignet, t) for t in (0.3, 0.65, 1.0)]
        k = C.rig['limbW'] / 5.6 * 1.15
        ray = [(5.2 * k, 5.0 * k), (5.0 * k, 5.1 * k), (4.5 * k, 4.6 * k), (3.8 * k, 3.9 * k),
               (4.4 * k, 4.2 * k), (3.9 * k, 3.6 * k), (3.2 * k, 2.9 * k)]
        bras = tube(C, 'TJ_bras.' + cote, pts, ray, n=12)
        lie(C, habille(bras, M['peau']), ['bras.' + cote, 'avantbras.' + cote])
        dedans = C.L * C.px(-1.4 if cote == 'L' else 1.4)          # rentrée vers le torse
        epaule = ellipsoide(C, 'TJ_epaule.' + cote, e + dedans - U * C.px(0.6), C.px(5.4 * k), C.px(5.2 * k),
                            C.px(5.2 * k), seg=16, anneaux_=8)
        lie(C, habille(epaule, M['peau']), ['bras.' + cote], rigide=True, lisse=1)
        # la main : un poing massif, des phalanges marquées, un pouce
        a, b = C.os['main.' + cote]
        d = (b - a).normalized()
        cote_ax = C.L if cote == 'L' else -C.L
        pouce_ax = (d.cross(cote_ax)).normalized()
        centre = a + d * C.px(3.2)
        poing = ellipsoide(C, 'TJ_poing.' + cote, centre, C.px(5.0), C.px(4.4), C.px(3.9),
                           axes=(d, pouce_ax, cote_ax), seg=16, anneaux_=10)
        pieces = [poing]
        for j in range(4):
            off = (j - 1.5) * 2.0
            pj = centre + d * C.px(3.0) - pouce_ax * C.px(2.1) + cote_ax * C.px(off)
            pieces.append(ellipsoide(C, 'TJ_phalange.' + cote, pj, C.px(1.7), C.px(1.7), C.px(1.15),
                                     axes=(d, pouce_ax, cote_ax), seg=10, anneaux_=6))
        pieces.append(tube(C, 'TJ_pouce.' + cote, [centre + pouce_ax * C.px(2.4) - d * C.px(0.5),
                                                    centre + pouce_ax * C.px(3.4) + d * C.px(1.8),
                                                    centre + pouce_ax * C.px(2.6) + d * C.px(3.6)],
                           [(1.4, 1.3), (1.3, 1.2), (1.0, 1.0)], n=8))
        for ob in pieces:
            lie(C, habille(ob, M['mains']), ['main.' + cote], rigide=True, lisse=1)

    # ---------------- jambes, pantalon retroussé, chaussures
    for cote in ('L', 'R'):
        hj, genou = C.os['cuisse.' + cote]
        _, cheville = C.os['tibia.' + cote]
        pts = [hj.lerp(genou, t) for t in (0.0, 0.4, 0.8, 1.0)] + [genou.lerp(cheville, t) for t in (0.3, 0.7, 1.0)]
        k = C.rig['limbW'] / 5.6 * 1.12
        jambe = tube(C, 'TJ_jambe.' + cote, pts,
                     [(5.8 * k, 5.6 * k), (5.4 * k, 5.4 * k), (4.4 * k, 4.4 * k), (4.0 * k, 4.0 * k),
                      (4.4 * k, 4.6 * k), (3.4 * k, 3.4 * k), (2.8 * k, 2.8 * k)], n=12)
        lie(C, habille(jambe, M['peau']), ['cuisse.' + cote, 'tibia.' + cote])
        pts = [hj.lerp(genou, t) for t in (-0.05, 0.4, 0.85)] + [genou.lerp(cheville, t) for t in (0.15, 0.36)]
        pant = tube(C, 'TJ_pantalon.' + cote, pts,
                    [(6.6 * k, 6.4 * k), (6.1 * k, 6.1 * k), (5.3 * k, 5.3 * k), (5.2 * k, 5.4 * k),
                     (5.3 * k, 5.5 * k)], n=14, fermer_debut=False, fermer_fin=False)
        lie(C, habille(pant, M['pantalon']), ['cuisse.' + cote, 'tibia.' + cote],
            extras=[('SOLIDIFY', {'thickness': C.px(0.7), 'offset': 1.0})])
        # le revers roulé du pantalon
        c0 = genou.lerp(cheville, 0.38)
        t_ = (cheville - genou).normalized()
        a_ = (C.L - t_ * C.L.dot(t_)).normalized()
        b_ = t_.cross(a_)
        revers = anneaux('TJ_revers.' + cote, [
            (c0 + (a_ * math.cos(t) * 5.9 * k + b_ * math.sin(t) * 6.1 * k) * u,
             t_.cross(a_ * -math.sin(t) + b_ * math.cos(t)).normalized(), t_, u * 1.2, u * 1.0)
            for t in (2 * math.pi * j / 20 for j in range(20))], n=8, boucle=True)
        lie(C, habille(revers, M['pantalon']), ['tibia.' + cote], rigide=True, lisse=1)
        # la chaussure : talon rond, bout large et relevé
        a, b = C.os['pied.' + cote]
        d = (b - a)
        d = (d - U * d.dot(U)).normalized()
        base = lambda av, hh: a + d * C.px(av) + U * C.px(hh)     # relatif à la cheville
        chaussure = tube(C, 'TJ_chaussure.' + cote,
                         [base(-4.6, 0.9), base(-1.6, 1.5), base(2.8, 0.9), base(7.4, 0.2), base(11.0, -0.2)],
                         [(4.3, 3.3), (4.9, 3.8), (5.1, 3.5), (4.8, 3.0), (3.4, 2.4)], n=16, axe_ref=C.L)
        lie(C, habille(chaussure, M['chaussures']), ['pied.' + cote], rigide=True)

    # ---------------- la cape : du haut des épaules au creux des genoux
    bm = bmesh.new()
    nx, ny = 14, 12
    grille = []
    for j in range(ny + 1):
        t = j / ny
        hh = H(1.02) + (8.0 - H(1.02)) * t
        larg = 12.5 + 8.5 * t
        rang = []
        for i in range(nx + 1):
            s = i / nx * 2 - 1
            dos = -(6.8 + 6.0 * t) - 3.2 * (1 - s * s) - 1.5 * math.sin(s * 3.0 + t * 2.0) * t
            rang.append(bm.verts.new(P(dos, hh, larg * s)))
        grille.append(rang)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((grille[j][i], grille[j][i + 1], grille[j + 1][i + 1], grille[j + 1][i]))
    cape = _objet('TJ_cape', bm)
    lie(C, habille(cape, M['cape']), ['torse'], rigide=True,
        extras=[('SOLIDIFY', {'thickness': C.px(0.8), 'offset': 0.0})])
    # l'attache de la cape : un col roulé sur les épaules
    col = anneaux('TJ_col_cape', [
        (P(-1.0 + 6.5 * math.cos(t), H(1.0)) + L * C.px(12.6 * math.sin(t)),
         (F * -math.sin(t) + L * math.cos(t)).normalized().cross(U), U, u * 1.3, u * 1.1)
        for t in (2 * math.pi * k / 24 for k in range(24))], n=8, boucle=True)
    lie(C, habille(col, M['cape']), ['torse'], rigide=True, lisse=1)

    # ---------------- le sabre, tenu dans la main avant
    a, b = C.os['main.R']
    lame_dir = -(b - a).normalized()            # comme dans le jeu : à l'opposé de l'avant-bras
    plat = (lame_dir.cross(C.L)).normalized()
    centre = a + (b - a).normalized() * C.px(3.2) + C.F * C.px(1.2) - C.L * C.px(1.4)
    sabre = []
    sabre.append(habille(tube(C, 'TJ_sabre_poignee', [centre - lame_dir * C.px(4.8), centre + lame_dir * C.px(3.2)],
                              [(1.1, 1.1), (1.1, 1.1)], n=10, axe_ref=C.L), M['poignee']))
    sabre.append(habille(ellipsoide(C, 'TJ_sabre_pommeau', centre - lame_dir * C.px(5.6), C.px(1.7), C.px(1.7),
                                    C.px(1.7), seg=12, anneaux_=6), M['dore']))
    garde = centre + lame_dir * C.px(3.8)
    sabre.append(habille(tube(C, 'TJ_sabre_garde', [garde - plat * C.px(6.2), garde, garde + plat * C.px(6.2)],
                              [(1.3, 1.1), (1.8, 1.6), (1.3, 1.1)], n=10, axe_ref=lame_dir), M['dore']))
    pts = [garde + lame_dir * C.px(d_) + plat * C.px(0.9 * (d_ / 50.0) ** 2 * 3.5) for d_ in (0.5, 14, 30, 43, 50)]
    sabre.append(habille(tube(C, 'TJ_sabre_lame', pts,
                              [(0.8, 4.3), (0.75, 4.2), (0.7, 3.9), (0.6, 3.1), (0.1, 0.4)], n=6,
                              axe_ref=C.L), M['lame']))
    for ob in sabre:
        lie(C, ob, ['main.R'], rigide=True, lisse=1)


RECETTES = {'tijean': recette_tijean}


# ---------------------------------------------------------------------------
# 6) PROGRAMME
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    o = {'poses': None, 'sortie': None, 'unite': 0.01, 'lacet': SP.LACET_DEFAUT}
    i = 0
    while i < len(args):
        cle = args[i][2:].replace('-', '_')
        if cle in o and i + 1 < len(args):
            o[cle] = float(args[i + 1]) if cle in ('unite', 'lacet') else args[i + 1]
            i += 1
        i += 1
    if not o['poses']:
        raise SystemExit('Smash Péi : --poses <fichier .poses.json> est obligatoire.')
    with open(o['poses'], encoding='utf-8') as f:
        doc = json.load(f)
    perso = doc['perso']
    if perso not in RECETTES:
        raise SystemExit('Smash Péi : pas encore de modèle pour « %s » (disponibles : %s).'
                         % (perso, ', '.join(sorted(RECETTES))))
    sortie = o['sortie'] or os.path.dirname(os.path.abspath(o['poses']))
    os.makedirs(sortie, exist_ok=True)
    arm = SP.cree_armature(doc, {'unite': o['unite'], 'vue': 'trois-quarts', 'lacet': o['lacet']})
    C = Corps(doc, arm, o['unite'], o['lacet'])
    RECETTES[perso](C)
    chemin = os.path.join(sortie, perso + '.blend')
    bpy.ops.wm.save_as_mainfile(filepath=chemin)
    n = sum(1 for ob in bpy.data.objects if ob.type == 'MESH')
    print('Smash Péi : modèle « %s » (%d pièces) enregistré -> %s' % (perso, n, chemin))


if __name__ == '__main__' and bpy is not None:
    main()
