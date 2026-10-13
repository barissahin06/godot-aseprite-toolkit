"""Original Ashguard mesh, rigid armature and authored pose keys. Run in Blender."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector


HERE = Path(__file__).resolve().parent
BRIEF = json.loads((HERE.parent / "brief.json").read_text(encoding="utf-8"))
MATERIALS = {}
RIG = None


def material(name: str, ramp: tuple[str, str, str]):
    value = bpy.data.materials.new(name)
    value.use_nodes = True
    nodes = value.node_tree.nodes
    nodes.clear()
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = (1, 1, 1, 1)
    rgb = nodes.new("ShaderNodeShaderToRGB")
    color = nodes.new("ShaderNodeValToRGB")
    color.color_ramp.interpolation = "CONSTANT"
    color.color_ramp.elements.remove(color.color_ramp.elements[1])
    for index, (position, label) in enumerate(zip((0, .25, .65), ramp)):
        element = color.color_ramp.elements[0] if index == 0 else color.color_ramp.elements.new(position)
        element.position = position
        raw = BRIEF["palette"][label].lstrip("#")
        srgb = [int(raw[i:i+2], 16) / 255 for i in (0, 2, 4)]
        linear = [v / 12.92 if v < .04045 else ((v + .055) / 1.055) ** 2.4 for v in srgb]
        element.color = (*linear, 1)
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    links = value.node_tree.links
    links.new(diffuse.outputs["BSDF"], rgb.inputs["Shader"])
    links.new(rgb.outputs["Color"], color.inputs["Fac"])
    links.new(color.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs[0], output.inputs["Surface"])
    MATERIALS[name] = value
    return value


def mesh(name: str, vertices: list, faces: list, mat: str, bone: str | None = None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(MATERIALS[mat])
    if bone:
        # Rigid weights retain the plate/boot facets while the editable armature moves.
        group = obj.vertex_groups.new(name=bone)
        group.add(list(range(len(vertices))), 1.0, "REPLACE")
        modifier = obj.modifiers.new("Ashguard armature", "ARMATURE")
        modifier.object = RIG
    return obj


def prism(name: str, profile: list[tuple[float, float]], depth: float, center_y: float, mat: str, bone: str):
    vertices = [(x, center_y-depth/2, z) for x, z in profile] + [(x, center_y+depth/2, z) for x, z in profile]
    count = len(profile)
    faces = [tuple(reversed(range(count))), tuple(range(count, count*2))]
    faces += [(i, (i+1) % count, (i+1) % count+count, i+count) for i in range(count)]
    return mesh(name, vertices, faces, mat, bone)


def box(name: str, center: tuple, size: tuple, mat: str, bone: str):
    x, y, z = center
    w, d, h = size
    return prism(name, [(x-w/2,z-h/2),(x+w/2,z-h/2),(x+w/2,z+h/2),(x-w/2,z+h/2)], d, y, mat, bone)


def ellipsoid(name: str, center: tuple, scale: tuple, mat: str, bone: str):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=5, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(MATERIALS[mat])
    # Keep world coordinates, matching the rigid mesh helper.
    for vertex in obj.data.vertices:
        vertex.co = obj.matrix_world @ vertex.co
    obj.location = (0, 0, 0)
    group = obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))), 1, "REPLACE")
    modifier = obj.modifiers.new("Ashguard armature", "ARMATURE")
    modifier.object = RIG
    return obj


def link_segment(name: str, a: tuple, b: tuple, width: float, depth: float, mat: str, bone: str):
    start, end = Vector(a), Vector(b)
    direction = end-start
    normal = Vector((direction.z, 0, -direction.x)).normalized() * width/2
    profile = [(start.x-normal.x,start.z-normal.z),(end.x-normal.x,end.z-normal.z),
               (end.x+normal.x,end.z+normal.z),(start.x+normal.x,start.z+normal.z)]
    return prism(name, profile, depth, (start.y+end.y)/2, mat, bone)


def matrix(a: tuple, b: tuple):
    start, end = Vector(a), Vector(b)
    rotation = (end-start).to_track_quat("Y", "Z")
    return Matrix.Translation(start) @ rotation.to_matrix().to_4x4()


REST = {
    "root": ((0,0,0),(0,0,.3),None),
    "hips": ((0,0,1.00),(0,0,1.20),"root"),
    "chest": ((0,0,1.20),(.015,0,1.62),"hips"),
    "head": ((.015,0,1.62),(.045,0,2.04),"chest"),
    "near_thigh": ((0,-.105,1.00),(.035,-.105,.53),"hips"),
    "near_shin": ((.035,-.105,.53),(.05,-.105,.08),"near_thigh"),
    "near_foot": ((.05,-.105,.08),(.31,-.105,.08),"near_shin"),
    "far_thigh": ((0,.105,1.00),(-.12,.105,.54),"hips"),
    "far_shin": ((-.12,.105,.54),(-.19,.105,.08),"far_thigh"),
    "far_foot": ((-.19,.105,.08),(.06,.105,.08),"far_shin"),
    "near_arm": ((.05,-.18,1.59),(.18,-.21,1.30),"chest"),
    "near_forearm": ((.18,-.21,1.30),(.47,-.23,1.30),"near_arm"),
    "near_hand": ((.47,-.23,1.30),(.62,-.23,1.38),"near_forearm"),
    "far_arm": ((-.04,.15,1.58),(-.22,.15,1.30),"chest"),
    "far_forearm": ((-.22,.15,1.30),(-.08,.15,1.06),"far_arm"),
    "far_hand": ((-.08,.15,1.06),(.02,.15,1.08),"far_forearm"),
    "tail_near": ((-.035,-.08,1.12),(-.23,-.08,.67),"hips"),
    "tail_far": ((-.08,.08,1.12),(-.39,.08,.71),"hips"),
    "scarf": ((-.01,0,1.68),(-.53,0,1.70),"chest"),
}


def rig():
    global RIG
    data = bpy.data.armatures.new("Ashguard skeleton")
    RIG = bpy.data.objects.new("Ashguard editable rig", data)
    bpy.context.collection.objects.link(RIG)
    bpy.context.view_layer.objects.active = RIG
    RIG.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent) in REST.items():
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        bone.matrix = matrix(head, tail)
        bone.length = (Vector(tail)-Vector(head)).length
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    RIG.show_in_front = True


def character():
    material("cloth", ("coat_shadow","coat","coat_light"))
    material("dark_cloth", ("outline","dark","neutral"))
    material("steel", ("steel_shadow","steel","steel_light"))
    material("polished", ("steel","steel_light","highlight"))
    material("leather", ("outline","bronze_shadow","bronze"))
    material("far_leather", ("outline","dark","bronze_shadow"))
    material("bronze", ("bronze_shadow","bronze","bronze_light"))
    material("scarf", ("scarf_shadow","scarf","scarf_light"))
    material("black", ("outline","outline","dark"))
    material("edge", ("steel_light","highlight","blade_edge"))
    rig()
    # Back objects remain real geometry and are shaded by the common camera.
    for side in ("far", "near"):
        leather = "far_leather" if side == "far" else "leather"
        a,b,_ = REST[side+"_thigh"]
        link_segment(side+" trouser thigh",a,b,.22,.19,"dark_cloth",side+"_thigh")
        a,b,_ = REST[side+"_shin"]
        link_segment(side+" lower trouser",a,b,.145,.16,"dark_cloth",side+"_shin")
        cuff = Vector(a).lerp(Vector(b),.56)
        link_segment(side+" tapered boot shaft",tuple(cuff),b,.135,.165,leather,side+"_shin")
        x,y,z = b
        prism(side+" shaped boot",[(x-.07,.02),(x+.17,.02),(x+.19,.065),(x+.11,.10),(x-.06,.13)],.175,y,leather,side+"_foot")
        prism(side+" raised sole and heel",[(x-.075,.015),(x+.18,.015),(x+.18,.04),(x-.075,.04)],.18,y,"black",side+"_foot")
        box(side+" boot cuff",tuple(cuff),(.16,.18,.055),"bronze",side+"_shin")
        box(side+" boot ankle strap",(x,y-.083,.18),(.135,.025,.025),"bronze",side+"_shin")
        box(side+" knee cap",(a[0]+.012,a[1]-.095,a[2]),(.16,.035,.14),"steel",side+"_shin")
    prism("fitted petrol coat",[(-.17,1.01),(.16,1.01),(.22,1.48),(.12,1.62),(-.14,1.57),(-.20,1.42)],.31,0,"cloth","chest")
    prism("near split coat tail",[(-.14,1.14),(.12,1.12),(-.02,.62),(-.29,.67)],.055,-.17,"cloth","tail_near")
    prism("far swept coat tail",[(-.16,1.13),(.03,1.13),(-.27,.65),(-.46,.73)],.05,.12,"cloth","tail_far")
    prism("coat gold piping",[(-.135,1.14),(-.105,1.14),(-.265,.68),(-.29,.68)],.06,-.197,"bronze","tail_near")
    box("leather belt",(-.015,0,1.14),(.37,.36,.08),"leather","hips")
    box("square belt clasp",(.035,-.195,1.15),(.09,.035,.095),"bronze","hips")
    prism("angular cuirass",[(-.135,1.25),(.11,1.22),(.19,1.47),(.09,1.61),(-.13,1.55),(-.17,1.42)],.055,-.187,"steel","chest")
    prism("cuirass central ridge",[(.01,1.26),(.055,1.26),(.11,1.53),(.062,1.56)],.018,-.223,"polished","chest")
    box("plate lower seam",(-.005,-.225,1.29),(.19,.023,.035),"black","chest")
    for z in (1.36,1.47):
        box("plate rivet",(-.1,-.222,z),(.025,.025,.025),"bronze","chest")
    ellipsoid("closed steel helmet",(.042,0,1.885),(.185,.165,.215),"steel","head")
    prism("helmet raised brow",[(-.10,1.965),(.18,1.975),(.22,1.91),(.08,1.93)],.018,-.159,"polished","head")
    prism("forward visor",[(.13,1.96),(.27,1.91),(.255,1.83),(.13,1.79)],.19,-.02,"steel","head")
    prism("visor dark eye slot",[(.08,1.914),(.235,1.908),(.236,1.88),(.08,1.886)],.012,-.167,"black","head")
    prism("helmet cheek plate",[(-.10,1.87),(.06,1.87),(.105,1.79),(-.02,1.73),(-.11,1.77)],.022,-.16,"steel","head")
    box("visor breathing slot",(.18,-.119,1.827),(.045,.016,.014),"black","head")
    box("helmet temple pin",(-.02,-.178,1.873),(.025,.025,.025),"bronze","head")
    ellipsoid("ochre wrapped scarf",(.02,0,1.68),(.17,.18,.095),"scarf","head")
    prism("trailing scarf ribbon",[(0,1.73),(-.36,1.76),(-.59,1.63),(-.47,1.60),(-.28,1.68),(-.02,1.66)],.055,.04,"scarf","scarf")
    for side in ("far","near"):
        a,b,_ = REST[side+"_arm"]
        link_segment(side+" cloth upper sleeve",a,b,.18,.18,"cloth",side+"_arm")
        ellipsoid(side+" faceted shoulder",a,(.19,.155,.155),"steel",side+"_arm")
        a,b,_ = REST[side+"_forearm"]
        link_segment(side+" steel vambrace",a,b,.155,.145,"steel",side+"_forearm")
        ellipsoid(side+" elbow joint",a,(.09,.087,.08),"bronze",side+"_forearm")
        a,b,_ = REST[side+"_hand"]
        link_segment(side+" leather glove",a,b,.105,.105,"leather",side+"_hand")
    # Sword points along the rest near-hand bone; no 2D stand-ins are used.
    origin = Vector(REST["near_hand"][0])
    direction = (Vector(REST["near_hand"][1])-origin).normalized()
    normal = Vector((direction.z,0,-direction.x)).normalized()
    def sword_point(length: float, width: float):
        value = origin + direction*length + normal*width
        return value.x,value.z
    prism("forged straight blade",[sword_point(.13,-.034),sword_point(.87,-.028),sword_point(.97,0),sword_point(.87,.029),sword_point(.13,.034)],.038,-.23,"steel","near_hand")
    prism("bright blade cutting edge",[sword_point(.14,.020),sword_point(.86,.018),sword_point(.97,0),sword_point(.87,.036),sword_point(.14,.042)],.01,-.257,"edge","near_hand")
    prism("blade dark fuller",[sword_point(.19,-.002),sword_point(.81,-.002),sword_point(.81,.008),sword_point(.19,.008)],.009,-.253,"polished","near_hand")
    cross = origin + direction*.115
    left, right = cross-normal*.125,cross+normal*.125
    link_segment("bronze crossguard",tuple(left),tuple(right),.05,.065,"bronze","near_hand")
    ellipsoid("sword pommel",tuple(origin-direction*.09),(.055,.045,.055),"bronze","near_hand")


def ik(a: Vector, target: Vector, upper: float, lower: float, bend: int):
    direction = target-a
    distance = min(direction.length, upper+lower-.001)
    assert distance > abs(upper-lower)+.001, "IK target too close"
    unit = direction.normalized()
    along = (upper*upper+distance*distance-lower*lower)/(2*distance)
    height = math.sqrt(max(0, upper*upper-along*along))
    perpendicular = Vector((-unit.z,0,unit.x)).normalized()*bend
    return a+unit*along+perpendicular*height


def pose(clip: str, index: int):
    phase = index / (8 if clip == "idle" else 12)*math.tau
    lean, hip_x, hip_z = .018, 0.0, 1.00
    feet = [(Vector((.13,-.105,.08)), Vector((-.25,.105,.08)))]
    near_wrist = Vector((.47,-.23,1.30))
    far_wrist = Vector((-.08,.15,1.06))
    sword_angle = .49
    tail_sway = math.sin(phase)*.035
    if clip == "idle":
        hip_z += math.sin(phase)*.018
        near_wrist.z += math.sin(phase+.4)*.026
        sword_angle += math.sin(phase+.8)*.025
    elif clip == "walk":
        hip_z -= .025*(1-math.cos(phase*2))
        lean = .035
        first = Vector((.02+.26*math.sin(phase),-.105,.08+.135*max(0,math.cos(phase))))
        second = Vector((-.06-.26*math.sin(phase),.105,.08+.135*max(0,-math.cos(phase))))
        feet = [(first,second)]
        near_wrist = Vector((.46+.03*math.sin(phase),-.23,1.29+.015*math.cos(phase*2)))
        far_wrist = Vector((-.08-.15*math.sin(phase),.15,1.17))
        sword_angle = .39+.07*math.sin(phase)
        tail_sway = .09*math.sin(phase-.7)
    else:
        # Slow load, four-frame accelerated cut, then a grounded recovery.
        keys = [
            (-.02, .99,-.03, .38,1.35,.65),
            (-.07, .97,-.09, .21,1.57,1.50),
            (-.10, .96,-.11, .07,1.71,2.25),
            (-.03, .98,-.02, .28,1.55,1.70),
            (.07, .93, .15, .64,1.55,.60),
            (.12, .90, .19, .69,1.32,-.18),
            (.12, .90, .17, .67,1.15,-.68),
            (.08, .92, .12, .55,1.10,-.74),
            (.04, .96, .06, .47,1.17,-.38),
            (.02, .98, .03, .45,1.25,.05),
            (.00,1.00, .02, .46,1.29,.38),
            (.00,1.00, .018,.47,1.30,.49),
        ]
        hip_x,hip_z,lean,wx,wz,sword_angle = keys[index]
        near_wrist = Vector((wx,-.23,wz))
        far_wrist = Vector((hip_x-.22,.15,1.29))
        feet = [(Vector((.22,-.105,.08)),Vector((-.27,.105,.08)))]
        tail_sway = -lean*.6
    hip = Vector((hip_x,0,hip_z))
    chest = hip+Vector((lean,0,.2))
    shoulder = chest+Vector((lean*.7,0,.42))
    head_top = shoulder+Vector((.03,0,.42))
    transforms = {"root":matrix((0,0,0),(0,0,.3)),"hips":matrix(tuple(hip),tuple(chest)),
                  "chest":matrix(tuple(chest),tuple(shoulder)),"head":matrix(tuple(shoulder),tuple(head_top))}
    for side,foot in zip(("near","far"),feet[0]):
        pelvis = hip+Vector((0,-.105 if side == "near" else .105,0))
        knee = ik(pelvis,foot,.471,.455,-1)
        transforms[side+"_thigh"] = matrix(tuple(pelvis),tuple(knee))
        transforms[side+"_shin"] = matrix(tuple(knee),tuple(foot))
        transforms[side+"_foot"] = matrix(tuple(foot),tuple(foot+Vector((.26,0,0))))
    for side,wrist in (("near",near_wrist),("far",far_wrist)):
        arm = shoulder+Vector((.035,-.18,-.03)) if side == "near" else shoulder+Vector((-.055,.15,-.04))
        elbow = ik(arm,wrist,.33,.295,1 if side == "near" else -1)
        transforms[side+"_arm"] = matrix(tuple(arm),tuple(elbow))
        transforms[side+"_forearm"] = matrix(tuple(elbow),tuple(wrist))
        direction = Vector((math.cos(sword_angle),0,math.sin(sword_angle))) if side == "near" else Vector((.7,0,-.3))
        transforms[side+"_hand"] = matrix(tuple(wrist),tuple(wrist+direction*.17))
    for side in ("near","far"):
        original = REST["tail_"+side]
        offset = hip-Vector((0,0,1))
        start = Vector(original[0])+offset
        end = Vector(original[1])+offset+Vector((tail_sway,0,-abs(tail_sway)*.2))
        transforms["tail_"+side] = matrix(tuple(start),tuple(end))
    scarf_root = shoulder+Vector((-.025,0,.06))
    transforms["scarf"] = matrix(tuple(scarf_root),tuple(scarf_root+Vector((-.52,0,.02+tail_sway*.7))))
    # Set parent bones before children so world-space IK matrices stay coherent.
    for name in REST:
        bone = RIG.pose.bones[name]
        bone.rotation_mode = "QUATERNION"
        bone.matrix = transforms[name]
        bpy.context.view_layer.update()
    return transforms


def scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = BRIEF["canvas"]
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.render.film_transparent = True
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.image_settings.color_mode = "RGBA"
    bpy.context.scene.render.image_settings.color_depth = "8"
    bpy.context.scene.view_settings.view_transform = "Standard"
    bpy.context.scene.view_settings.look = "None"
    bpy.context.scene.view_settings.exposure = 0
    bpy.context.scene.view_settings.gamma = 1
    bpy.context.scene.render.fps = 100
    bpy.context.scene.render.fps_base = 1
    # Native pixel renders, palette fixed after rendering; no high-res downsample.
    if hasattr(bpy.context.scene, "eevee"):
        bpy.context.scene.eevee.taa_render_samples = 1
    bpy.context.scene.world.color = (.22,.22,.22)
    bpy.ops.object.light_add(type="SUN", location=(2,-4,5))
    bpy.context.object.name = "Upper-front broad key"
    bpy.context.object.rotation_euler = Vector((3,4,-6)).to_track_quat("-Z","Y").to_euler()
    bpy.context.object.data.energy = 2
    bpy.context.object.data.angle = 0
    bpy.ops.object.camera_add(location=(3.155,-8,1.51))
    camera = bpy.context.object
    target = Vector((.155,0,1.15))
    camera.rotation_euler = (target-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3.67
    bpy.context.scene.camera = camera
    character()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args(__import__("sys").argv[__import__("sys").argv.index("--")+1:])
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    scene()
    timeline = []
    time = 1
    for clip, settings in BRIEF["clips"].items():
        start = time
        bpy.context.scene.timeline_markers.new(clip.upper()+" START",frame=time)
        for index,duration in enumerate(settings["durations_ms"]):
            bpy.context.scene.frame_set(time)
            pose(clip,index)
            for bone in RIG.pose.bones:
                for channel in ("location","rotation_quaternion","scale"):
                    bone.keyframe_insert(channel,frame=time,group=bone.name)
            timeline.append({"clip":clip,"index":index,"timeline_frame":time,"duration_ms":duration,
                             "file":f"{clip}_{index:02d}.png"})
            time += duration//10
        pose(clip,0 if settings["loop"] else len(settings["durations_ms"])-1)
        for bone in RIG.pose.bones:
            for channel in ("location","rotation_quaternion","scale"):
                bone.keyframe_insert(channel,frame=time,group=bone.name)
        bpy.context.scene.timeline_markers.new(clip.upper()+" END",frame=time)
        if "contact_seconds" in settings:
            bpy.context.scene.timeline_markers.new("contact",frame=start+round(settings["contact_seconds"]*100))
            bpy.context.scene.timeline_markers.new("chain_ready",frame=start+round(settings["chain_ready_seconds"]*100))
        time += 10
    bpy.context.scene.frame_end = time-10
    RIG["source_contract"] = "Editable geometry, rigid armature and keyed poses; Aseprite owns final pixel retouch."
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/"ashguard.blend"))
    selected = timeline[:1] if args.preview_only else timeline
    for item in selected:
        bpy.context.scene.frame_set(item["timeline_frame"])
        bpy.context.scene.render.filepath = str(output/item["file"])
        bpy.ops.render.render(write_still=True)
        anchors = {}
        for label,name in (("visor","visor dark eye slot"),("rivet","plate rivet"),("temple","helmet temple pin")):
            obj = bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
            vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
            point = sum(vertices,Vector())/len(vertices)
            pixel = world_to_camera_view(bpy.context.scene,bpy.context.scene.camera,point)
            anchors[label] = [round(pixel.x*96),round((1-pixel.y)*80)]
        item["retouch_anchors"] = anchors
    (output/"timeline.json").write_text(json.dumps(timeline,indent=2)+"\n",encoding="utf-8")
    assert len(timeline) == 32 and len(RIG.data.bones) == len(REST)
    print("BLENDER_DUELIST_AUTHORED")


if __name__ == "__main__":
    main()
