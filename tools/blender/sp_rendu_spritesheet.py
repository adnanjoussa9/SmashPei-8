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


def cadre_camera(rig, marge):
    """Hauteur visible par la caméra (en pixels de jeu) et hauteur de son centre."""
    hauteur = rig['legLen'] + rig['torsoLen'] + rig['neck'] + rig['headR'] * 2.4
    cote = hauteur * marge
    return cote, hauteur * 0.5


def lit_arguments(argv):
    args = argv[argv.index('--') + 1:] if '--' in argv else []
    o = {'poses': None, 'mode': 'rendu', 'sortie': None, 'unite': 0.01, 'taille': 384,
         'marge': 2.2, 'anims': None, 'mannequin': False, 'sans_tete': False,
         'tete': 'vectorielle', 'contour': False}
    i = 0
    while i < len(args):
        a = args[i]
        if a in ('--mannequin', '--sans-tete', '--contour'):
            o[a[2:].replace('-', '_')] = True
        elif a.startswith('--') and i + 1 < len(args):
            cle = a[2:].replace('-', '_')
            val = args[i + 1]
            if cle in ('unite', 'marge'):
                val = float(val)
            elif cle == 'taille':
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


def matrice_os(tete, queue):
    """Matrice d'os (espace armature) : Y le long de l'os, Z vers la caméra."""
    y = Vector(queue) - Vector(tete)
    if y.length < 1e-9:
        y = Vector((0.0, 0.0, 1.0))
    y.normalize()
    z = Vector(AXE_CAMERA)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    m = Matrix((
        (x.x, y.x, z.x, tete[0]),
        (x.y, y.y, z.y, tete[1]),
        (x.z, y.z, z.z, tete[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))
    return m


def cree_squelette(doc, o):
    rig, unite = doc['rig'], o['unite']
    repos = doc['animations']['idle']['poses'][0] if 'idle' in doc['animations'] else {}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm = bpy.data.armatures.new('SP_Rig')
    obj = bpy.data.objects.new('SP_Rig', arm)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    for nom, parent, t, q, dz in os_du_squelette(repos, rig):
        eb = arm.edit_bones.new(nom)
        eb.head = vers_blender(t, dz, unite)
        eb.tail = vers_blender(q, dz, unite)
        if (eb.tail - eb.head).length < 1e-6:
            eb.tail = eb.head + Vector((0, 0, 0.01))
        eb.align_roll(Vector(AXE_CAMERA))
        eb.use_connect = False
        if parent:
            eb.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    obj['smashpei_perso'] = doc['perso']
    obj['smashpei_unite'] = unite

    if o['mannequin']:
        cree_mannequin(obj, doc, unite)

    chemin = os.path.join(o['sortie'], doc['perso'] + '_squelette.blend')
    bpy.ops.wm.save_as_mainfile(filepath=chemin)
    print('Smash Péi : squelette enregistré ->', chemin)


def materiau(nom, hexa):
    h = hexa.lstrip('#')
    rgb = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) if len(h) >= 6 else (0.8, 0.8, 0.8)
    m = bpy.data.materials.new(nom)
    m.diffuse_color = (*rgb, 1.0)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    return m


def cree_mannequin(arm_obj, doc, unite):
    """Des cylindres sur chaque os, une sphère pour la tête : de quoi tester la chaîne."""
    pal = doc.get('palette', {})
    peau = materiau('SP_peau', pal.get('skin', '#d9a066'))
    habit = materiau('SP_habit', pal.get('cloth', pal.get('skin', '#3a6ea5')))
    rig = doc['rig']
    for pb in arm_obj.data.bones:
        if pb.name == 'racine':
            continue
        longueur = pb.length
        if pb.name == 'tete':
            bpy.ops.mesh.primitive_uv_sphere_add(radius=rig['headR'] * unite, segments=24, ring_count=12)
            ob = bpy.context.active_object
            ob.name = 'tete_mannequin'
            ob.location = arm_obj.matrix_world @ pb.head_local
        else:
            rayon = rig['limbW'] * unite * (1.6 if pb.name == 'torse' else 0.55)
            bpy.ops.mesh.primitive_cylinder_add(radius=rayon, depth=longueur, vertices=12)
            ob = bpy.context.active_object
            ob.name = 'mannequin_' + pb.name
            ob.matrix_world = arm_obj.matrix_world @ pb.matrix_local @ Matrix.Translation((0, longueur / 2, 0)) \
                @ Matrix.Rotation(math.radians(90), 4, 'X')
        ob.data.materials.append(habit if pb.name in ('torse', 'cuisse.L', 'cuisse.R') else peau)
        mw = ob.matrix_world.copy()
        ob.parent = arm_obj
        ob.parent_type = 'BONE'
        ob.parent_bone = pb.name
        ob.matrix_world = mw


def pose_armature(arm_obj, pose, rig, unite):
    """Place chaque os à sa position et à son orientation exactes (espace armature)."""
    liste = os_du_squelette(pose, rig)
    for nom, parent, t, q, dz in liste:            # parents d'abord : l'ordre de la liste
        pb = arm_obj.pose.bones.get(nom)
        if pb is None:
            continue
        pb.matrix = matrice_os(vers_blender(t, dz, unite), vers_blender(q, dz, unite))
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

    if not any(ob.type == 'LIGHT' for ob in scene.objects):
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
        for i, pose in enumerate(anim['poses']):
            pose_armature(arm_obj, pose, rig, unite)
            fichier = '%s_%04d.png' % (nom, i)
            scene.render.filepath = os.path.join(sous, fichier)
            bpy.ops.render.render(write_still=True)
            # l'origine du jeu (les pieds) projetée dans l'image
            u = world_to_camera_view(scene, scene.camera, Vector((0.0, 0.0, 0.0)))
            images.append({
                'fichier': 'images/%s/%s' % (nom, fichier),
                'origine': [u.x * o['taille'], (1.0 - u.y) * o['taille']],
                'pose': pose
            })
            print('Smash Péi :', nom, i + 1, '/', len(anim['poses']))
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
    if o['mode'] == 'squelette':
        cree_squelette(doc, o)
    else:
        rend(doc, o)


if __name__ == '__main__' and bpy is not None:
    main()
