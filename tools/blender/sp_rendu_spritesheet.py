# -*- coding: utf-8 -*-
"""
SMASH PÉI — RENDU DES IMAGES D'UNE SPRITESHEET DANS BLENDER
=============================================================

Ce script transforme les poses du jeu (exportées depuis le navigateur) en
images PNG à fond transparent, une par pose, prêtes à être assemblées en
planche par `tools/spritesheet/sp_assembler.mjs`.

Il ne dépend de rien d'autre que de Blender (testé pour Blender 3.6 à 4.x ;
les noms de moteur de rendu qui ont changé entre versions sont gérés).


LA CHAÎNE COMPLÈTE, DANS L'ORDRE
--------------------------------

  1. EXPORTER LES POSES, depuis le jeu.
     Ouvrir `smash_pei (6).html` dans le navigateur, ouvrir la console
     (F12) et taper :

         SPRITES.exporterPoses('tijean')

     Le navigateur télécharge `tijean.poses.json`. Le ranger dans :

         rendus/tijean/tijean.poses.json

  2. CRÉER LE SQUELETTE DE RÉFÉRENCE (une seule fois par personnage) :

         blender -b --python tools/blender/sp_rendu_spritesheet.py -- \
             --poses rendus/tijean/tijean.poses.json --mode squelette --mannequin

     Produit `rendus/tijean/tijean_squelette.blend` : une armature `SP_Rig`
     dont les os ont EXACTEMENT les longueurs du squelette du jeu pour ce
     personnage, en pose de repos, plus (avec --mannequin) un mannequin de
     cylindres et une sphère de tête, pour vérifier la chaîne tout de
     suite. Modélisez votre personnage dans ce fichier, attachez-le à
     `SP_Rig` (Ctrl+P > With Automatic Weights), supprimez le mannequin,
     et enregistrez sous `rendus/tijean/tijean.blend`.

  3. RENDRE LES IMAGES :

         blender -b rendus/tijean/tijean.blend --python tools/blender/sp_rendu_spritesheet.py -- \
             --poses rendus/tijean/tijean.poses.json --mode rendu

     Produit :
         rendus/tijean/images/idle/idle_0000.png, idle_0001.png, ...
         rendus/tijean/images/attack_fsmash/attack_fsmash_0000.png, ...
         rendus/tijean/manifeste.json

  4. ASSEMBLER LA PLANCHE (Node, sans aucun paquet à installer) :

         node tools/spritesheet/sp_assembler.mjs rendus/tijean sprites

  5. ACTIVER LE PERSONNAGE dans le jeu : dans le bloc `105-sprites.js`,
     ajouter son identifiant à `SPRITES_CONFIG.ACTIFS`, ou taper dans la
     console `SPRITES.charger('tijean')`. Le dossier `sprites/` doit être
     à côté du fichier HTML.


CONVENTIONS
-----------

  * Dossiers :
        rendus/<perso>/<perso>.poses.json   (entrée, venue du jeu)
        rendus/<perso>/<perso>.blend        (votre modèle)
        rendus/<perso>/images/<anim>/<anim>_<NNNN>.png   (sortie)
        rendus/<perso>/manifeste.json                    (sortie)
  * <perso> est l'identifiant du jeu (`tijean`, `volkan`, ...), en minuscules.
  * <anim> : idle, walk, run, jump, hitstun, victory, et attack_<coup>
    (attack_jab1, attack_fsmash, ...). Le préfixe avant le premier « _ »
    est la FAMILLE que le jeu associe aux états du combattant.
  * <NNNN> : numéro de l'image sur quatre chiffres, à partir de 0000.

  * Repère du jeu : pieds en (0,0), x vers l'AVANT, y vers le BAS, angles
    en degrés, 0 = vers le haut, positif = vers l'avant (sens horaire à
    l'écran).
  * Repère Blender : le personnage regarde vers +X, les pieds sont à
    l'origine, Z vers le haut, la caméra est du côté -Y et regarde vers +Y.
    Un pixel du jeu vaut --unite mètres (0,01 par défaut : un personnage
    de 100 px mesure 1 m).
  * Côtés : le jeu appelle « L » le membre ARRIÈRE (loin de la caméra) et
    « R » le membre AVANT. On garde ces lettres : `bras.L` est le bras du
    fond, placé en +Y ; `bras.R` celui de devant, en -Y.

  * Os de `SP_Rig` (tous non connectés, pour être placés librement) :
        racine                         aux pieds, fixe
        torse                          bassin -> poitrine
        cou                            poitrine -> base de la tête
        tete                           centre de la tête, vers le haut du crâne
        bras.L  avantbras.L  main.L    (arrière)
        bras.R  avantbras.R  main.R    (avant)
        cuisse.L  tibia.L  pied.L      (arrière)
        cuisse.R  tibia.R  pied.R      (avant)
    Des os supplémentaires (queue, ailes, cape) peuvent exister : le
    script ne les touche pas, ils restent dans la pose que vous leur
    donnez.

  * Clés de forme facultatives, sur n'importe quel maillage :
        bouche        <- pose.mouth (0 = fermée, 1 = grande ouverte)
        yeux_fermes   <- 1 - pose.eye

  * NON RENDUS, appliqués par le jeu au dessin : hipX (glissement du
    bassin), hipRot (rotation du corps, vrille de chute), sx / sy
    (écrasement). Les poses exportées les ont déjà remis à zéro.

  * TÊTE VECTORIELLE (mode par défaut du jeu) : le jeu dessine lui-même la
    tête par-dessus le rendu, pour garder tous les chapeaux et visages du
    vestiaire. Dans ce cas, ne rendez PAS la tête : cachez-la au rendu
    (--sans-tete masque tout objet dont le nom commence par « tete »), le
    cou suffit. Pour une tête modélisée, passez --tete sprite ; les
    chapeaux classiques ne s'afficheront plus sur ce personnage (voir
    l'en-tête du bloc 105).


OPTIONS
-------
  --poses FICHIER     le .poses.json exporté par le jeu (obligatoire)
  --mode squelette|rendu
  --sortie DOSSIER    par défaut, le dossier du fichier de poses
  --unite M           mètres par pixel de jeu (0.01)
  --taille PX         côté de l'image rendue, en pixels (384)
  --marge K           marge autour du personnage, en hauteurs (2.2)
  --anims a,b,c       ne rendre que ces animations
  --mannequin         (mode squelette) ajoute un mannequin de test
  --sans-tete         (mode rendu) masque les objets « tete* »
  --tete vectorielle|sprite   écrit dans le manifeste (vectorielle)
  --contour           active Freestyle pour un trait de contour
  --style classique|ultimate
                      ultimate : principale chaude, fond froid, deux
                      contre-jours forts, rendu couleur AgX/Filmic
                      contraste moyen-fort, ombres douces, occlusion. Voir la
                      section 4 du script pour les réglages.
  --contre-jour K     multiplie la force du contre-jour (1.0)
  --vue plan|trois-quarts
                      (mode squelette) plan : le squelette plat du jeu, pour
                      des rendus qui collent au dessin vectoriel ;
                      trois-quarts : un vrai corps 3D, épaules et hanches en
                      profondeur, tourné de --lacet degrés vers la caméra.
                      C'est la vue des modèles de sp_modele.py. Le choix est
                      enregistré dans le .blend et relu au rendu.
  --lacet DEGRÉS      rotation du corps vers la caméra en vue trois-quarts (50)
  --max-images N      ne rend que les N premières images de chaque animation
                      (pour un essai rapide)
  --ouvrir FICHIER    ouvre ce .blend avant de travailler ; utile quand on
                      lance le script depuis le module Python `bpy` plutôt
                      que depuis l'exécutable blender

LES MATIÈRES SP_*
-----------------
Le mode squelette dépose dans le fichier une bibliothèque de matières aux
couleurs du personnage : SP_peau, SP_peau_ombre, SP_habit, SP_jean,
SP_accent, SP_cuir, SP_gants, SP_metal, SP_armure, SP_plumes, SP_ecorce.
Chacune porte son micro-relief procédural (trame du jean, grain du cuir,
écorce...). Affectez-les à votre modèle : c'est la moitié de l'aspect
« Ultimate », l'éclairage est l'autre moitié.
"""

import json
import math
import os
import sys

try:
    import bpy
    from mathutils import Matrix, Vector
    from bpy_extras.object_utils import world_to_camera_view
except ImportError:          # hors de Blender : seules les fonctions de calcul servent (tests)
    bpy = None


# ---------------------------------------------------------------------------
# 1) LE SQUELETTE DU JEU, EN PYTHON PUR
#    Les formules sont celles de `drawFighterRig` (bloc 02-rig.js).
# ---------------------------------------------------------------------------

def fk_point(x, y, ang_deg, longueur):
    """fkPoint du jeu : 0° = vers le haut, positif = vers l'avant, y vers le bas."""
    a = math.radians(ang_deg - 90)
    return (x + math.cos(a) * longueur, y + math.sin(a) * longueur)


def points_du_squelette(pose, rig):
    """Toutes les articulations, dans le repère du jeu (pixels, y vers le bas).

    Renvoie un dictionnaire nom -> (x, y). hipX, hipRot, sx, sy sont ignorés :
    le jeu les applique au dessin."""
    g = lambda k, d=0.0: float(pose.get(k, d))
    torso, lean = g('torso'), g('lean')
    hip_y = -rig['legLen'] * 0.92 + g('hipY')
    hip = (0.0, hip_y)
    chest = fk_point(0.0, hip_y, torso + lean * 0.4, rig['torsoLen'])
    sa = math.radians(torso)
    sxo, syo = math.cos(sa) * rig['shoulderW'], math.sin(sa) * rig['shoulderW']
    sh_l = (chest[0] - sxo, chest[1] - syo)
    sh_r = (chest[0] + sxo, chest[1] + syo)
    hp_l = (-rig['hipW'], hip_y)
    hp_r = (rig['hipW'], hip_y)
    el_l = fk_point(*sh_l, 180 + torso + g('shL', 8), rig['upArm'])
    ha_l = fk_point(*el_l, 180 + torso + g('shL', 8) + g('elL', 10), rig['foreArm'])
    el_r = fk_point(*sh_r, 180 + torso + g('shR', -8), rig['upArm'])
    ha_r = fk_point(*el_r, 180 + torso + g('shR', -8) + g('elR', 10), rig['foreArm'])
    kn_l = fk_point(*hp_l, 180 + g('hpL', 6), rig['thigh'])
    ft_l = fk_point(*kn_l, 180 + g('hpL', 6) + g('knL', 6), rig['shin'])
    kn_r = fk_point(*hp_r, 180 + g('hpR', -6), rig['thigh'])
    ft_r = fk_point(*kn_r, 180 + g('hpR', -6) + g('knR', 6), rig['shin'])
    head_brut = fk_point(*chest, torso + g('head') * 0.35, rig['neck'] + rig['headR'] * 0.72)
    head = (head_brut[0] + g('headX'), head_brut[1] + g('headY'))
    neck_base = fk_point(*chest, torso, rig['neck'] * 0.25)
    return {
        'hip': hip, 'chest': chest, 'neck': neck_base, 'head': head, 'head_brut': head_brut,
        'sh_l': sh_l, 'el_l': el_l, 'ha_l': ha_l, 'sh_r': sh_r, 'el_r': el_r, 'ha_r': ha_r,
        'hp_l': hp_l, 'kn_l': kn_l, 'ft_l': ft_l, 'hp_r': hp_r, 'kn_r': kn_r, 'ft_r': ft_r,
        # angles utiles : rotation de la tête (drawHead) et des pieds (drawFoot)
        'head_rot': g('head') * 0.5 + torso * 0.3,
        'foot_l': 90 + g('hpL', 6) + g('knL', 6),
        'foot_r': 90 + g('hpR', -6) + g('knR', 6),
        'hand_l': 180 + torso + g('shL', 8) + g('elL', 10),
        'hand_r': 180 + torso + g('shR', -8) + g('elR', 10),
    }


def direction(ang_deg):
    """Vecteur unitaire (x, y écran) d'un angle du jeu."""
    a = math.radians(ang_deg - 90)
    return (math.cos(a), math.sin(a))


def os_du_squelette(pose, rig):
    """Chaque os : (nom, parent, tête (x, y), queue (x, y), profondeur).

    La profondeur est en pixels de jeu, le long de Y dans Blender :
    positive = vers le fond (membres L), négative = vers la caméra (R)."""
    P = points_du_squelette(pose, rig)
    r, lw = rig['headR'], rig['limbW']
    dz_bras, dz_jambe = rig['shoulderW'] * 0.5, rig['hipW']

    def bout(pt, ang, longueur):
        d = direction(ang)
        return (pt[0] + d[0] * longueur, pt[1] + d[1] * longueur)

    tete_queue = bout(P['head'], P['head_rot'], r)
    return [
        ('racine', None, (0.0, 0.0), (0.0, -r), 0.0),
        ('torse', 'racine', P['hip'], P['chest'], 0.0),
        ('cou', 'torse', P['neck'], (P['neck'][0] * 0.3 + P['head'][0] * 0.7,
                                    P['neck'][1] * 0.3 + P['head'][1] * 0.7), 0.0),
        ('tete', 'cou', P['head'], tete_queue, 0.0),
        ('bras.L', 'torse', P['sh_l'], P['el_l'], dz_bras),
        ('avantbras.L', 'bras.L', P['el_l'], P['ha_l'], dz_bras),
        ('main.L', 'avantbras.L', P['ha_l'], bout(P['ha_l'], P['hand_l'], lw * 1.2), dz_bras),
        ('bras.R', 'torse', P['sh_r'], P['el_r'], -dz_bras),
        ('avantbras.R', 'bras.R', P['el_r'], P['ha_r'], -dz_bras),
        ('main.R', 'avantbras.R', P['ha_r'], bout(P['ha_r'], P['hand_r'], lw * 1.2), -dz_bras),
        ('cuisse.L', 'racine', P['hp_l'], P['kn_l'], dz_jambe),
        ('tibia.L', 'cuisse.L', P['kn_l'], P['ft_l'], dz_jambe),
        ('pied.L', 'tibia.L', P['ft_l'], bout(P['ft_l'], P['foot_l'], lw * 2.0), dz_jambe),
        ('cuisse.R', 'racine', P['hp_r'], P['kn_r'], -dz_jambe),
        ('tibia.R', 'cuisse.R', P['kn_r'], P['ft_r'], -dz_jambe),
        ('pied.R', 'tibia.R', P['ft_r'], bout(P['ft_r'], P['foot_r'], lw * 2.0), -dz_jambe),
    ]


def vers_blender(pt, profondeur, unite):
    """Repère du jeu (x avant, y bas, pixels) -> Blender (X avant, Y profondeur, Z haut, mètres)."""
    return (pt[0] * unite, profondeur * unite, -pt[1] * unite)


# ---------------------------------------------------------------------------
# 1 bis) LA VUE TROIS-QUARTS — pour un vrai modèle 3D
#
#    Le squelette du jeu est un pantin PLAT : les deux épaules sont écartées
#    dans le plan de l'écran (le « trois-quarts » est dessiné). Posé sur un
#    corps 3D, ce squelette ferait marcher le personnage en pas chassés : ses
#    jambes s'écarteraient sur le côté au lieu d'avancer.
#
#    En vue trois-quarts, on garde EXACTEMENT les angles du jeu, mais on les
#    applique dans le plan du corps (avant / haut), et on écarte épaules et
#    hanches en PROFONDEUR, comme sur un vrai corps. Puis on tourne le corps de
#    `lacet` degrés vers la caméra : c'est la pose de présentation des
#    personnages de Smash Bros, qui montre le torse et le visage tout en
#    regardant vers l'avant.
#
#    Le squelette 3D ne tombe plus exactement sur le dessin vectoriel : le
#    rendu enregistre donc, image par image, où sont vraiment la tête, la
#    poitrine et le bassin (les « ancres »), et c'est là que le jeu pose les
#    accessoires.
# ---------------------------------------------------------------------------

LACET_DEFAUT = 50.0          # degrés : le corps tourné vers la caméra (90 = de face)

# Le squelette du jeu place la cheville un peu SOUS le sol (le pied vectoriel
# le cache). Un pied 3D, lui, s'y enfoncerait : en vue trois-quarts, la chaîne
# de la jambe est raccourcie d'autant, ce qui pose la chaussure sur le sol —
# et donne au passage les jambes courtes des proportions « Smash ».
JAMBES_34 = 0.88


def repere_corps(vue, lacet):
    """Les axes du corps dans Blender : F avant, U haut, L côté (vers le fond)."""
    if vue != 'trois-quarts':
        return (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)
    a = math.radians(lacet)
    return (math.cos(a), -math.sin(a), 0.0), (0.0, 0.0, 1.0), (math.sin(a), math.cos(a), 0.0)


def os_du_squelette_34(pose, rig):
    """Comme os_du_squelette, mais épaules et hanches écartées en profondeur :
    (nom, parent, tête (x, y), queue (x, y), côté) ; `côté` est l'écart
    latéral, positif vers le fond (membres L), négatif vers la caméra (R)."""
    g = lambda k, d=0.0: float(pose.get(k, d))
    torso, lean = g('torso'), g('lean')
    r, lw = rig['headR'], rig['limbW']
    hip = (0.0, -rig['legLen'] * 0.92 + g('hipY'))
    chest = fk_point(*hip, torso + lean * 0.4, rig['torsoLen'])
    epaule = fk_point(*chest, 180 + torso, rig['torsoLen'] * 0.1)
    l_ep, l_ha = rig['shoulderW'] * 0.82, rig['hipW'] * 1.05

    def bras(sh, se):
        el = fk_point(*epaule, 180 + torso + sh, rig['upArm'])
        ha = fk_point(*el, 180 + torso + sh + se, rig['foreArm'])
        bout = fk_point(*ha, 180 + torso + sh + se, lw * 1.2)
        return el, ha, bout

    def jambe(hp, kn):
        k = fk_point(*hip, 180 + hp, rig['thigh'] * JAMBES_34)
        ft = fk_point(*k, 180 + hp + kn, rig['shin'] * JAMBES_34)
        bout = fk_point(*ft, 90 + hp + kn, lw * 2.0)
        return k, ft, bout

    el_l, ha_l, mn_l = bras(g('shL', 8), g('elL', 10))
    el_r, ha_r, mn_r = bras(g('shR', -8), g('elR', 10))
    kn_l, ft_l, pd_l = jambe(g('hpL', 6), g('knL', 6))
    kn_r, ft_r, pd_r = jambe(g('hpR', -6), g('knR', 6))
    head_brut = fk_point(*chest, torso + g('head') * 0.35, rig['neck'] + r * 0.72)
    head = (head_brut[0] + g('headX'), head_brut[1] + g('headY'))
    neck = fk_point(*chest, torso, rig['neck'] * 0.25)
    rot = g('head') * 0.5 + torso * 0.3
    return [
        ('racine', None, (0.0, 0.0), (0.0, -r), 0.0),
        ('torse', 'racine', hip, chest, 0.0),
        ('cou', 'torse', neck, (neck[0] * 0.3 + head[0] * 0.7, neck[1] * 0.3 + head[1] * 0.7), 0.0),
        ('tete', 'cou', head, fk_point(*head, rot, r), 0.0),
        ('bras.L', 'torse', epaule, el_l, l_ep),
        ('avantbras.L', 'bras.L', el_l, ha_l, l_ep),
        ('main.L', 'avantbras.L', ha_l, mn_l, l_ep),
        ('bras.R', 'torse', epaule, el_r, -l_ep),
        ('avantbras.R', 'bras.R', el_r, ha_r, -l_ep),
        ('main.R', 'avantbras.R', ha_r, mn_r, -l_ep),
        ('cuisse.L', 'racine', hip, kn_l, l_ha),
        ('tibia.L', 'cuisse.L', kn_l, ft_l, l_ha),
        ('pied.L', 'tibia.L', ft_l, pd_l, l_ha),
        ('cuisse.R', 'racine', hip, kn_r, -l_ha),
        ('tibia.R', 'cuisse.R', kn_r, ft_r, -l_ha),
        ('pied.R', 'tibia.R', ft_r, pd_r, -l_ha),
    ]


def corps_vers_monde(pt, cote, repere, unite):
    """(x avant, y bas) du jeu + écart latéral -> coordonnées Blender, en mètres."""
    F, U, L = repere
    x, h, l = pt[0], -pt[1], cote
    return tuple((x * F[i] + h * U[i] + l * L[i]) * unite for i in range(3))


def os_monde(pose, rig, vue='plan', lacet=LACET_DEFAUT, unite=0.01):
    """Chaque os, en coordonnées Blender : (nom, parent, tête, queue)."""
    rep = repere_corps(vue, lacet)
    liste = os_du_squelette_34(pose, rig) if vue == 'trois-quarts' else os_du_squelette(pose, rig)
    return [(n, p, corps_vers_monde(t, c, rep, unite), corps_vers_monde(q, c, rep, unite))
            for n, p, t, q, c in liste]


def cadre_camera(rig, marge):
    """Hauteur visible par la caméra (en pixels de jeu) et hauteur de son centre."""
    hauteur = rig['legLen'] + rig['torsoLen'] + rig['neck'] + rig['headR'] * 2.4
    cote = hauteur * marge
    return cote, hauteur * 0.5


def lit_arguments(argv):
    args = argv[argv.index('--') + 1:] if '--' in argv else []
    o = {'poses': None, 'mode': 'rendu', 'sortie': None, 'unite': 0.01, 'taille': 384,
         'marge': 2.2, 'anims': None, 'mannequin': False, 'sans_tete': False,
         'tete': 'vectorielle', 'contour': False, 'style': 'classique',
         'ouvrir': None, 'max_images': 0, 'vue': 'plan', 'lacet': LACET_DEFAUT,
         'contre_jour': 1.0}
    i = 0
    while i < len(args):
        a = args[i]
        if a in ('--mannequin', '--sans-tete', '--contour'):
            o[a[2:].replace('-', '_')] = True
        elif a.startswith('--') and i + 1 < len(args):
            cle = a[2:].replace('-', '_')
            val = args[i + 1]
            if cle in ('unite', 'marge', 'contre_jour', 'lacet'):
                val = float(val)
            elif cle in ('taille', 'max_images'):
                val = int(val)
            elif cle == 'anims':
                val = [s.strip() for s in val.split(',') if s.strip()]
            o[cle] = val
            i += 1
        i += 1
    if not o['poses']:
        raise SystemExit('Smash Péi : --poses <fichier .poses.json> est obligatoire.')
    if o['sortie'] is None:
        o['sortie'] = os.path.dirname(os.path.abspath(o['poses']))
    return o


# ---------------------------------------------------------------------------
# 2) BLENDER
# ---------------------------------------------------------------------------

AXE_CAMERA = (0.0, -1.0, 0.0)      # l'axe Z des os regarde la caméra


def matrice_os(tete, queue, axe_z=AXE_CAMERA):
    """Matrice d'os (espace armature) : Y le long de l'os, Z vers la caméra."""
    y = Vector(queue) - Vector(tete)
    if y.length < 1e-9:
        y = Vector((0.0, 0.0, 1.0))
    y.normalize()
    z = Vector(axe_z)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    m = Matrix((
        (x.x, y.x, z.x, tete[0]),
        (x.y, y.y, z.y, tete[1]),
        (x.z, y.z, z.z, tete[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))
    return m


def axe_roulis(vue, lacet):
    """L'axe Z des os : vers la caméra, perpendiculaire au plan du corps."""
    L = repere_corps(vue, lacet)[2]
    return (-L[0], -L[1], -L[2])


def cree_squelette(doc, o):
    obj = cree_armature(doc, o)
    unite = o['unite']
    bibliotheque_materiaux(doc, unite)
    if o['mannequin']:
        cree_mannequin(obj, doc, unite)

    chemin = os.path.join(o['sortie'], doc['perso'] + '_squelette.blend')
    bpy.ops.wm.save_as_mainfile(filepath=chemin)
    print('Smash Péi : squelette enregistré ->', chemin)


def cree_armature(doc, o):
    """Une scène vide et l'armature SP_Rig, en pose de repos (idle, image 0)."""
    rig, unite = doc['rig'], o['unite']
    repos = doc['animations']['idle']['poses'][0] if 'idle' in doc['animations'] else {}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm = bpy.data.armatures.new('SP_Rig')
    obj = bpy.data.objects.new('SP_Rig', arm)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    axe_z = axe_roulis(o['vue'], o['lacet'])
    for nom, parent, t, q in os_monde(repos, rig, o['vue'], o['lacet'], unite):
        eb = arm.edit_bones.new(nom)
        eb.head = t
        eb.tail = q
        if (eb.tail - eb.head).length < 1e-6:
            eb.tail = eb.head + Vector((0, 0, 0.01))
        eb.align_roll(Vector(axe_z))
        eb.use_connect = False
        if parent:
            eb.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    obj['smashpei_perso'] = doc['perso']
    obj['smashpei_unite'] = unite
    obj['smashpei_vue'] = o['vue']
    obj['smashpei_lacet'] = float(o['lacet'])
    return obj


# ---------------------------------------------------------------------------
# 3) LES MATIÈRES
#    Une bibliothèque de matières « SP_* » posée dans chaque fichier : l'artiste
#    les affecte à son modèle au lieu de régler chaque shader à la main. C'est
#    une grande part de l'aspect « Ultimate » : chaque matière se reconnaît au
#    premier regard (la trame d'un jean, le grain d'un cuir, le vernis d'une
#    armure), sans aucune texture peinte.
# ---------------------------------------------------------------------------

def hexa_rgb(hexa, defaut=(0.8, 0.8, 0.8)):
    h = (hexa or '').lstrip('#')
    if len(h) < 6:
        return defaut
    # sRGB -> linéaire : les couleurs de la palette du jeu sont en sRGB
    return tuple(((int(h[i:i + 2], 16) / 255.0 + 0.055) / 1.055) ** 2.4 for i in (0, 2, 4))


def entree(noeud, noms, valeur):
    """Règle la première entrée qui existe : les noms changent entre Blender 3 et 5
    (« Subsurface » / « Subsurface Weight », « Clearcoat » / « Coat Weight »...)."""
    for n in noms:
        if n in noeud.inputs:
            try:
                noeud.inputs[n].default_value = valeur
                return True
            except (TypeError, ValueError):
                pass
    return False


# nom : (rugosité, métal, [(entrées, valeur)], relief)
#   relief : None, ou (type de texture, échelle, force)
MATIERES = {
    'peau':        (0.48, 0.0, [(('Subsurface Weight', 'Subsurface'), 0.18), (('Subsurface Scale',), 0.02)], None),
    'tissu':       (0.86, 0.0, [(('Sheen Weight', 'Sheen'), 0.35)], ('NOISE', 900.0, 0.12)),
    'jean':        (0.80, 0.0, [(('Sheen Weight', 'Sheen'), 0.2)], ('WAVE', 420.0, 0.25)),
    'cuir':        (0.42, 0.0, [(('Coat Weight', 'Clearcoat'), 0.15)], ('NOISE', 260.0, 0.18)),
    'metal':       (0.28, 1.0, [], None),
    'metal_peint': (0.32, 0.35, [(('Coat Weight', 'Clearcoat'), 0.7), (('Coat Roughness', 'Clearcoat Roughness'), 0.08)], None),
    'plumes':      (0.72, 0.0, [(('Sheen Weight', 'Sheen'), 0.6)], ('NOISE', 520.0, 0.10)),
    'ecorce':      (0.90, 0.0, [], ('VORONOI', 60.0, 0.6)),
    'caoutchouc':  (0.62, 0.0, [], None),
    'verre':       (0.05, 0.0, [(('Transmission Weight', 'Transmission'), 0.9)], None),
}


def materiau(nom, hexa, genre='tissu', unite=0.01):
    """Une matière SP_<nom>, de couleur `hexa`, du genre donné (voir MATIERES).
    L'échelle du relief est exprimée en pixels de jeu, pour rester la même quelle
    que soit l'unité choisie."""
    rug, metal, extra, relief = MATIERES.get(genre, MATIERES['tissu'])
    rgb = hexa_rgb(hexa)
    m = bpy.data.materials.get(nom) or bpy.data.materials.new(nom)
    m.use_fake_user = True          # gardée dans le fichier même non affectée
    m.diffuse_color = (*rgb, 1.0)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    arbre = m.node_tree
    bsdf = next((n for n in arbre.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = arbre.nodes.new('ShaderNodeBsdfPrincipled')
    entree(bsdf, ('Base Color',), (*rgb, 1.0))
    entree(bsdf, ('Roughness',), rug)
    entree(bsdf, ('Metallic',), metal)
    for noms, v in extra:
        entree(bsdf, noms, v)
    if genre == 'peau':
        entree(bsdf, ('Subsurface Radius',), (1.0, 0.35, 0.2))
    if relief:
        sorte, echelle, force = relief
        coord = arbre.nodes.new('ShaderNodeTexCoord')
        if sorte == 'WAVE':
            tex = arbre.nodes.new('ShaderNodeTexWave')
            try:
                tex.wave_type = 'BANDS'
                tex.bands_direction = 'DIAGONAL'
            except (AttributeError, TypeError):
                pass
        elif sorte == 'VORONOI':
            tex = arbre.nodes.new('ShaderNodeTexVoronoi')
        else:
            tex = arbre.nodes.new('ShaderNodeTexNoise')
        entree(tex, ('Scale',), echelle * unite)
        bosse = arbre.nodes.new('ShaderNodeBump')
        entree(bosse, ('Strength',), force)
        entree(bosse, ('Distance',), 0.002)
        arbre.links.new(coord.outputs['Object'], tex.inputs['Vector'])
        sortie = tex.outputs.get('Fac') or tex.outputs.get('Distance') or tex.outputs[0]
        arbre.links.new(sortie, bosse.inputs['Height'])
        arbre.links.new(bosse.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def bibliotheque_materiaux(doc, unite):
    """Les matières SP_* du personnage, aux couleurs de sa palette."""
    pal = doc.get('palette', {})
    peau = pal.get('skin', '#d9a066')
    return {
        'peau': materiau('SP_peau', peau, 'peau', unite),
        'peau_ombre': materiau('SP_peau_ombre', pal.get('skin2', peau), 'peau', unite),
        'habit': materiau('SP_habit', pal.get('cloth', peau), 'tissu', unite),
        'jean': materiau('SP_jean', pal.get('cloth', '#3a5f9e'), 'jean', unite),
        'accent': materiau('SP_accent', pal.get('accent', '#e94f37'), 'tissu', unite),
        'cuir': materiau('SP_cuir', pal.get('shoe', '#5a3a22'), 'cuir', unite),
        'gants': materiau('SP_gants', pal.get('hand', peau), 'tissu', unite),
        'metal': materiau('SP_metal', '#c9ccd2', 'metal', unite),
        'armure': materiau('SP_armure', pal.get('accent', '#d8742a'), 'metal_peint', unite),
        'plumes': materiau('SP_plumes', pal.get('wing', pal.get('skin', '#f2f2f2')), 'plumes', unite),
        'ecorce': materiau('SP_ecorce', pal.get('cloth', '#6b4a2e'), 'ecorce', unite),
    }


def cree_mannequin(arm_obj, doc, unite):
    """Un mannequin en gélules : un cylindre par os, une sphère à chaque
    articulation, une tête. De quoi tester la chaîne et juger l'éclairage."""
    mats = bibliotheque_materiaux(doc, unite)
    rig = doc['rig']
    vue = bpy.context.view_layer

    def attache(ob, os_nom, mat):
        ob.data.materials.append(mat)
        vue.update()
        mw = ob.matrix_world.copy()
        ob.parent = arm_obj
        ob.parent_type = 'BONE'
        ob.parent_bone = os_nom
        ob.matrix_world = mw
        try:
            bpy.ops.object.shade_smooth()
        except RuntimeError:
            pass

    for pb in arm_obj.data.bones:
        if pb.name == 'racine':
            continue
        debut = arm_obj.matrix_world @ pb.head_local
        if pb.name == 'tete':
            bpy.ops.mesh.primitive_uv_sphere_add(radius=rig['headR'] * unite, segments=32, ring_count=16,
                                                 location=debut)
            ob = bpy.context.active_object
            ob.name = 'tete_mannequin'
            attache(ob, pb.name, mats['peau'])
            continue
        longueur = pb.length
        epais = rig['limbW'] * unite * (1.7 if pb.name == 'torse' else 0.5)
        bpy.ops.mesh.primitive_cylinder_add(radius=epais, depth=longueur, vertices=20)
        ob = bpy.context.active_object
        ob.name = 'mannequin_' + pb.name
        ob.matrix_world = arm_obj.matrix_world @ pb.matrix_local @ Matrix.Translation((0, longueur / 2, 0)) \
            @ Matrix.Rotation(math.radians(90), 4, 'X')
        if pb.name == 'torse':
            mat = mats['habit']
        elif pb.name.startswith(('cuisse', 'tibia')):
            mat = mats['jean']
        elif pb.name.startswith('pied'):
            mat = mats['cuir']
        elif pb.name.startswith('main'):
            mat = mats['gants']
        else:
            mat = mats['peau']
        attache(ob, pb.name, mat)
        # l'articulation : une sphère au départ de l'os, qui bouche le raccord
        bpy.ops.mesh.primitive_uv_sphere_add(radius=epais * 1.02, segments=16, ring_count=8, location=debut)
        rot = bpy.context.active_object
        rot.name = 'articulation_' + pb.name
        attache(rot, pb.name, mat)


def vue_de(arm_obj):
    """La vue et le lacet avec lesquels ce squelette a été construit."""
    return arm_obj.get('smashpei_vue', 'plan'), float(arm_obj.get('smashpei_lacet', LACET_DEFAUT))


def pose_armature(arm_obj, pose, rig, unite):
    """Place chaque os à sa position et à son orientation exactes (espace armature)."""
    vue, lacet = vue_de(arm_obj)
    axe_z = axe_roulis(vue, lacet)
    for nom, parent, t, q in os_monde(pose, rig, vue, lacet, unite):   # parents d'abord
        pb = arm_obj.pose.bones.get(nom)
        if pb is None:
            continue
        pb.matrix = matrice_os(t, q, axe_z)
        bpy.context.view_layer.update()
    # clés de forme
    for ob in bpy.data.objects:
        cles = ob.data.shape_keys.key_blocks if getattr(ob, 'data', None) is not None \
            and getattr(ob.data, 'shape_keys', None) else None
        if not cles:
            continue
        if 'bouche' in cles:
            cles['bouche'].value = max(0.0, min(1.0, float(pose.get('mouth', 0))))
        if 'yeux_fermes' in cles:
            cles['yeux_fermes'].value = max(0.0, min(1.0, 1.0 - float(pose.get('eye', 1))))


# ---------------------------------------------------------------------------
# 4) LE STYLE « ULTIMATE »
#    Ce qui donne son air aux rendus de Smash Bros Ultimate, appliqué à nos
#    personnages (on reprend un STYLE, pas un personnage) :
#      * une lumière principale chaude en avant et en haut, un fond froid et
#        doux de l'autre côté, et DEUX contre-jours puissants, de dos, qui
#        posent un liseré clair sur les deux bords — c'est lui qui détache le
#        personnage du décor ;
#      * un rendu couleur filmique (AgX, ou Filmic avant Blender 4) au contraste
#        moyen-fort : des couleurs saturées qui ne brûlent pas ;
#      * des ombres douces et de l'occlusion ambiante dans les creux ;
#      * les matières SP_* (section 3), qui portent le micro-relief.
#    Des soleils plutôt que des lampes : leur intensité ne dépend pas de la
#    distance, le réglage vaut donc pour un colosse comme pour un oiseau.
# ---------------------------------------------------------------------------

STYLE_ULTIMATE = {
    # (nom, couleur, force, rotation en degrés (x, y, z), douceur en degrés)
    # Un soleil éclaire le long de son axe -Z local. Avec la caméra en -Y et
    # le personnage tourné vers +X : x > 0 fait venir la lumière de l'avant
    # (côté caméra), x < 0 de derrière ; z > 0 la place du côté du visage.
    # Réglages choisis sur rendus comparés dans Blender 5.0 (principale 1,6 à
    # 4,2, contre-jour 6 à 25) : au-delà de 2 pour la principale, AgX délave
    # la peau ; en dessous de 14 pour les contre-jours, le liseré disparaît.
    'lumieres': [
        ('SP_Principale',  (1.00, 0.90, 0.78), 2.0, (50.0, 0.0, 40.0), 9.0),     # avant, haut, côté visage
        ('SP_Fond',        (0.70, 0.80, 1.00), 0.5, (65.0, 0.0, -60.0), 25.0),   # avant, côté nuque, froide
        ('SP_ContreJour',  (0.95, 0.97, 1.00), 25.0, (-85.0, 0.0, 40.0), 2.0),   # dos, liseré côté visage
        ('SP_ContreJour2', (1.00, 0.93, 0.85), 18.0, (-85.0, 0.0, -40.0), 2.0),  # dos, liseré côté nuque
    ],
    # l'ambiance : assez claire pour que les métaux aient quelque chose à
    # refléter (une lame dans un monde noir paraît noire), assez faible pour
    # ne pas aplatir le modelé
    'monde': ((0.42, 0.46, 0.52), 0.32),
    'rendu': ('AgX', ('AgX - Medium High Contrast', 'Medium High Contrast')),
    'echantillons': 64,
}


def essaie(objet, attribut, valeur):
    """Pose un réglage s'il existe dans cette version de Blender."""
    try:
        setattr(objet, attribut, valeur)
        return True
    except (AttributeError, TypeError, ValueError):
        return False


def applique_style_ultimate(scene, force_contre_jour=1.0):
    S = STYLE_ULTIMATE
    # les lumières du style remplacent les autres au rendu (on ne supprime rien)
    for ob in scene.objects:
        if ob.type == 'LIGHT' and not ob.name.startswith('SP_'):
            ob.hide_render = True
    for nom, couleur, force, rot, douceur in S['lumieres']:
        ob = bpy.data.objects.get(nom)
        if ob is None:
            ob = bpy.data.objects.new(nom, bpy.data.lights.new(nom, 'SUN'))
            scene.collection.objects.link(ob)
        ob.hide_render = False
        ob.data.color = couleur
        ob.data.energy = force * (force_contre_jour if nom.startswith('SP_ContreJour') else 1.0)
        ob.rotation_euler = tuple(math.radians(a) for a in rot)
        essaie(ob.data, 'angle', math.radians(douceur))

    monde = scene.world or bpy.data.worlds.new('SP_Monde')
    scene.world = monde
    couleur, force = S['monde']
    essaie(monde, 'color', couleur)
    try:
        monde.use_nodes = True
        fond = next(n for n in monde.node_tree.nodes if n.type == 'BACKGROUND')
        entree(fond, ('Color',), (*couleur, 1.0))
        entree(fond, ('Strength',), force)
    except (AttributeError, StopIteration):
        pass

    vue, looks = S['rendu']
    if not essaie(scene.view_settings, 'view_transform', vue):
        essaie(scene.view_settings, 'view_transform', 'Filmic')
    for look in looks:
        if essaie(scene.view_settings, 'look', look):
            break

    ee = getattr(scene, 'eevee', None)
    if ee is not None:
        essaie(ee, 'taa_render_samples', S['echantillons'])
        essaie(ee, 'use_gtao', True)             # occlusion ambiante (EEVEE 3.x - 4.1)
        essaie(ee, 'gtao_distance', 0.25)
        essaie(ee, 'use_soft_shadows', True)
        essaie(ee, 'use_raytracing', True)       # EEVEE 4.2 et plus
        essaie(ee, 'use_shadows', True)
    cy = getattr(scene, 'cycles', None)
    if cy is not None:
        essaie(cy, 'samples', 96)


def prepare_scene(doc, o):
    scene = bpy.context.scene
    rig = doc['rig']
    for moteur in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES'):
        try:
            scene.render.engine = moteur
            break
        except TypeError:
            continue
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.resolution_x = o['taille']
    scene.render.resolution_y = o['taille']
    scene.render.resolution_percentage = 100
    if o['contour']:
        scene.render.use_freestyle = True
        try:
            scene.view_layers[0].freestyle_settings.linesets[0].linestyle.thickness = max(1.0, o['taille'] / 180)
        except (IndexError, AttributeError):
            pass

    cote, centre = cadre_camera(rig, o['marge'])
    cam = scene.camera
    if cam is None:
        cam = bpy.data.objects.new('SP_Camera', bpy.data.cameras.new('SP_Camera'))
        scene.collection.objects.link(cam)
        scene.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = cote * o['unite']
    cam.location = (0.0, -10.0, centre * o['unite'])
    cam.rotation_euler = (math.radians(90), 0.0, 0.0)

    if o['style'] == 'ultimate':
        applique_style_ultimate(scene, o.get('contre_jour', 1.0))
    elif not any(ob.type == 'LIGHT' for ob in scene.objects):
        soleil = bpy.data.objects.new('SP_Soleil', bpy.data.lights.new('SP_Soleil', 'SUN'))
        soleil.data.energy = 3.0
        soleil.rotation_euler = (math.radians(50), math.radians(-20), math.radians(-30))
        scene.collection.objects.link(soleil)

    if o['sans_tete']:
        for ob in scene.objects:
            if ob.name.lower().startswith('tete'):
                ob.hide_render = True
    # pixels de planche par pixel de jeu
    return o['taille'] / cote


def rend(doc, o):
    arm_obj = bpy.data.objects.get('SP_Rig')
    if arm_obj is None or arm_obj.type != 'ARMATURE':
        raise SystemExit('Smash Péi : aucune armature « SP_Rig » dans ce fichier (voir --mode squelette).')
    rig, unite = doc['rig'], o['unite']
    scene = bpy.context.scene
    echelle = prepare_scene(doc, o)
    dossier = os.path.join(o['sortie'], 'images')
    manifeste = {
        'format': 'smashpei-rendu/1', 'perso': doc['perso'], 'echelle': echelle,
        'tete': o['tete'], 'rig': rig, 'taille': o['taille'], 'animations': {}
    }
    for nom, anim in doc['animations'].items():
        if o['anims'] and nom not in o['anims']:
            continue
        sous = os.path.join(dossier, nom)
        os.makedirs(sous, exist_ok=True)
        images = []
        poses = anim['poses'][:o['max_images']] if o['max_images'] else anim['poses']
        for i, pose in enumerate(poses):
            pose_armature(arm_obj, pose, rig, unite)
            fichier = '%s_%04d.png' % (nom, i)
            scene.render.filepath = os.path.join(sous, fichier)
            bpy.ops.render.render(write_still=True)
            # l'origine du jeu (les pieds) projetée dans l'image
            def px(p):
                u = world_to_camera_view(scene, scene.camera, Vector(p))
                return [round(u.x * o['taille'], 2), round((1.0 - u.y) * o['taille'], 2)]
            mw = arm_obj.matrix_world
            os_ = arm_obj.pose.bones
            ancres = {}
            if 'tete' in os_ and 'torse' in os_:
                ancres = {'tete': px(mw @ os_['tete'].head), 'poitrine': px(mw @ os_['torse'].tail),
                          'bassin': px(mw @ os_['torse'].head)}
            images.append({
                'fichier': 'images/%s/%s' % (nom, fichier),
                'origine': px((0.0, 0.0, 0.0)),
                'ancres': ancres,
                'pose': pose
            })
            print('Smash Péi :', nom, i + 1, '/', len(poses))
        manifeste['animations'][nom] = {'boucle': anim.get('boucle', False), 'images': images}
    with open(os.path.join(o['sortie'], 'manifeste.json'), 'w', encoding='utf-8') as f:
        json.dump(manifeste, f, ensure_ascii=False, indent=1)
    print('Smash Péi : manifeste écrit ->', os.path.join(o['sortie'], 'manifeste.json'))


def main():
    o = lit_arguments(sys.argv)
    with open(o['poses'], encoding='utf-8') as f:
        doc = json.load(f)
    if doc.get('format') != 'smashpei-poses/1':
        raise SystemExit('Smash Péi : ce fichier ne vient pas de SPRITES.exporterPoses().')
    os.makedirs(o['sortie'], exist_ok=True)
    if o['ouvrir']:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(o['ouvrir']))
    if o['mode'] == 'squelette':
        cree_squelette(doc, o)
    else:
        rend(doc, o)


if __name__ == '__main__' and bpy is not None:
    main()
