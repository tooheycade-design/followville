"""Generate four isolated North Crown apartment review models and renders.

Never imports the production generator, opens neighborhood.blend, or touches
world_state.json. Run in Blender with --background --factory-startup.
"""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "work" / "asset-review" / "north-crown-apartments"
FORBIDDEN = {"neighborhood.blend", "town.glb", "world_state.json"}


def get_output():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = DEFAULT_OUT
    if "--output-dir" in args:
        out = Path(args[args.index("--output-dir") + 1]).resolve()
    if out == ROOT or out.name.lower() in FORBIDDEN:
        raise RuntimeError("refusing canonical Followville output path")
    out.mkdir(parents=True, exist_ok=True)
    return out


def reset():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def mat(name, rgb, rough=.82, metal=0, emission=None):
    value = bpy.data.materials.new(name)
    value.diffuse_color = (*rgb, 1)
    value.use_nodes = True
    shader = value.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*rgb, 1)
    shader.inputs["Roughness"].default_value = rough
    shader.inputs["Metallic"].default_value = metal
    if emission:
        shader.inputs["Emission Color"].default_value = (*emission, 1)
        shader.inputs["Emission Strength"].default_value = .3
    return value


def materials():
    return {key: mat("NC_" + key, color, rough, metal, glow)
            for key, color, rough, metal, glow in (
        ("cream", (.86, .81, .70), .85, 0, None),
        ("peach", (.78, .52, .42), .84, 0, None),
        ("sage", (.43, .59, .49), .86, 0, None),
        ("blue", (.38, .55, .64), .78, 0, None),
        ("brick", (.56, .34, .27), .91, 0, None),
        ("slate", (.22, .27, .31), .72, .05, None),
        ("glass", (.12, .27, .34), .25, .04, None),
        ("warm", (.86, .62, .30), .30, 0, (.86, .45, .12)),
        ("white", (.91, .90, .85), .64, 0, None),
        ("concrete", (.62, .61, .57), .94, 0, None),
        ("plant", (.24, .44, .25), .98, 0, None),
    )}


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new(name + "_ROOT", None)
    root["review_asset"] = True
    col.objects.link(root)
    return col, root


def relink(obj, col):
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def box(col, root, name, dims, loc, material, bevel=0):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel:
        mod = obj.modifiers.new("low_poly_edge", "BEVEL")
        mod.width, mod.segments = bevel, 1
    if root:
        obj.parent = root
    return relink(obj, col)


def cyl(col, root, name, radius, depth, loc, material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=7, radius=radius, depth=depth,
                                       location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.parent = root
    return relink(obj, col)


def roof(col, root, name, width, depth, height, z, material, x=0):
    hx, hy = width / 2, depth / 2
    verts = [(-hx,-hy,0),(hx,-hy,0),(hx,hy,0),(-hx,hy,0),
             (0,-hy,height),(0,hy,height)]
    faces = [(0,1,4),(3,5,2),(0,4,5,3),(1,2,5,4),(0,3,2,1)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (x, 0, z)
    obj.parent = root
    col.objects.link(obj)
    return obj


def landscape(col, root, m, width, depth):
    box(col, root, "foundation", (width+1.4, depth+1.4, .24),
        (0,0,.12), m["concrete"])
    for x in (-width*.34, width*.34):
        box(col, root, "planter", (3.2,1.25,.55),
            (x,-depth/2-1,.52), m["brick"])
        for dx in (-.9,0,.9):
            cyl(col, root, "shrub", .46, 1.2,
                 (x+dx,-depth/2-1,1.25), m["plant"])


def windows(col, root, m, width, depth, floors, bays, balconies=(), z0=.35):
    """Glass, sills and rails are physically separated by 4-13 cm."""
    for floor in range(floors):
        z = z0 + floor*3.05 + 1.55
        for bay in range(bays):
            x = -width/2 + (bay+1)*width/(bays+1)
            glass = m["warm"] if (floor+bay)%5 == 0 else m["glass"]
            for side in (-1,1):
                box(col, root, "window_front", (1.65,.16,1.55),
                    (x,side*(depth/2+.09),z), glass, .03)
                # Four-piece projected trim reads clearly in Eevee and keeps
                # every visible face physically separated from the glazing.
                trim_y=side*(depth/2+.19)
                for dx in (-.96,.96):
                    box(col,root,"window_jamb",(.16,.10,1.92),
                        (x+dx,trim_y,z),m["white"],.025)
                for dz in (-.88,.88):
                    box(col,root,"window_trim",(2.08,.10,.14),
                        (x,trim_y,z+dz),m["white"],.025)
                box(col, root, "window_sill", (1.95,.18,.13),
                    (x,side*(depth/2+.13),z-.91), m["white"])
                if floor and bay in balconies and side == -1:
                    box(col, root, "balcony_slab", (3.25,1.7,.18),
                        (x,-depth/2-.88,z-1), m["concrete"])
                    box(col, root, "balcony_top_rail", (3.15,.10,.12),
                        (x,-depth/2-1.73,z-.18), m["slate"])
                    for rx in (-1.42,-.95,-.48,0,.48,.95,1.42):
                        box(col, root, "balcony_picket", (.07,.08,.76),
                            (x+rx,-depth/2-1.73,z-.56), m["slate"])
                    for dx in (-1.48,1.48):
                        box(col, root, "balcony_side", (.1,1.62,.88),
                            (x+dx,-depth/2-.88,z-.55), m["slate"])
        for side in (-1,1):
            for y in (-depth*.23, depth*.23):
                box(col, root, "window_side", (.16,1.55,1.55),
                    (side*(width/2+.09),y,z), m["glass"], .03)
                trim_x=side*(width/2+.19)
                for dy in (-.96,.96):
                    box(col,root,"side_window_jamb",(.10,.16,1.92),
                        (trim_x,y+dy,z),m["white"],.025)
                for dz in (-.88,.88):
                    box(col,root,"side_window_trim",(.10,2.08,.14),
                        (trim_x,y,z+dz),m["white"],.025)


def facade_bands(col,root,m,width,depth,floors):
    """Ground-floor stonework and projecting floor lines add readable scale."""
    box(col,root,"stone_base_front",(width+.45,.24,.78),
        (0,-depth/2-.13,.74),m["concrete"],.035)
    box(col,root,"stone_base_rear",(width+.45,.24,.78),
        (0,depth/2+.13,.74),m["concrete"],.035)
    for floor in range(1,floors):
        z=.35+floor*3.05
        for side in (-1,1):
            box(col,root,"floor_band_front",(width+.5,.18,.18),
                (0,side*(depth/2+.12),z),m["white"],.025)
        for side in (-1,1):
            box(col,root,"floor_band_side",(.18,depth+.5,.18),
                (side*(width/2+.12),0,z),m["white"],.025)


def roof_details(col,root,m,width,depth,z):
    """Parapets, screened mechanical units, vents and a roof access bulkhead."""
    # ``z`` is the finished roof surface, not the vertical centre of these
    # pieces.  Centering them on the surface buried half of every parapet,
    # access bulkhead and HVAC cabinet inside the building, which read as
    # dark roof fragments hanging below the eaves in oblique renders.
    for y in (-depth/2+.25,depth/2-.25):
        box(col,root,"roof_parapet",(width-.5,.38,.72),(0,y,z+.36),m["slate"],.04)
    for x in (-width/2+.25,width/2-.25):
        box(col,root,"roof_parapet",(.38,depth-.5,.72),(x,0,z+.36),m["slate"],.04)
    box(col,root,"roof_access",(4.2,3.6,2.45),
        (-width*.22,0,z+1.225),m["sage"],.08)
    for index,x in enumerate((-width*.04,width*.18,width*.34)):
        box(col,root,"roof_hvac",(2.2,1.55,.88),
            (x,depth*.12,z+.44),m["concrete"],.06)
        for side in (-1,1):
            box(col,root,"hvac_louver",(1.45,.04,.10),
                (x,depth*.12+side*.79,z+.44),m["slate"])


def entry(col, root, m, face, x=0, width=5.4):
    box(col, root, "entry_recess", (4.4,.22,3.15),
        (x,face-.03,1.94), m["slate"])
    box(col, root, "entry_glass", (3.4,.18,2.55),
        (x,face-.18,1.62), m["warm"], .04)
    box(col, root, "entry_canopy", (width,2.2,.24),
        (x,face-1.08,3.35), m["white"])
    box(col,root,"entry_step",(width+1.1,2.45,.16),(x,face-1.18,.08),m["concrete"],.03)
    for dx in (-1.52,1.52):
        box(col,root,"entry_sidelight",(.42,.10,2.35),
            (x+dx,face-.32,1.55),m["glass"],.025)
    box(col,root,"entry_transom",(3.4,.10,.42),(x,face-.32,2.95),m["glass"],.025)
    for dx in (-width/2+.3,width/2-.3):
        box(col, root, "canopy_post", (.16,.16,3.05),
            (x+dx,face-1.9,1.875), m["slate"])


def parkline(m):
    col, root = collection("NC01_Parkline")
    w,d,f = 31,18,4
    landscape(col,root,m,w,d)
    box(col,root,"body",(w,d,f*3.05),(0,0,.35+f*3.05/2),m["cream"],.1)
    box(col,root,"center",(8.4,d+.55,f*3.05+1.2),
        (0,0,.35+(f*3.05+1.2)/2),m["sage"],.1)
    windows(col,root,m,w,d,f,7,(1,5)); facade_bands(col,root,m,w,d,f)
    entry(col,root,m,-d/2-.12)
    box(col,root,"roof_cap",(w-1,d-1,.28),(0,0,.35+f*3.05+.14),m["slate"])
    box(col,root,"lantern",(5.6,4.4,2),(0,.8,.63+f*3.05+1),m["glass"],.08)
    roof_details(col,root,m,w-1,d-1,.63+f*3.05)
    return col,root


def gable(m):
    col, root = collection("NC02_Gable_Court")
    w,d,f = 32,19.5,4
    landscape(col,root,m,w,d)
    box(col,root,"body",(w,d,f*3),(0,0,.35+f*1.5),m["peach"],.08)
    for x in (-8,8):
        box(col,root,"projecting_bay",(8.2,d+.75,f*3),(x,-.12,.35+f*1.5),m["brick"],.07)
        roof(col,root,"gable_roof",9,d+1.7,2.8,.35+f*3+.06,m["slate"],x)
    windows(col,root,m,w,d+.75,f,7); facade_bands(col,root,m,w,d+.75,f)
    entry(col,root,m,-(d+.75)/2-.12)
    for x in (-8,8):
        cyl(col,root,"gable_finial",.16,2.1,(x,0,.35+f*3+3.0),m["slate"])
    return col,root


def terrace(m):
    col, root = collection("NC03_Terrace_House")
    w,d = 36,21
    landscape(col,root,m,w,d)
    box(col,root,"low",(w,d,4*3.05),(0,0,.35+4*3.05/2),m["blue"],.1)
    box(col,root,"high",(21,d-2,2*3.05),(-4,.7,.35+4*3.05+3.05),m["cream"],.1)
    windows(col,root,m,w,d,4,8,(1,6)); facade_bands(col,root,m,w,d,4)
    entry(col,root,m,-d/2-.12,9)
    for floor in (4,5):
        z=.35+floor*3.05+1.55
        for x in (-10,-5,0,5):
            box(col,root,"upper_window",(1.65,.16,1.55),
                (x,-d/2+.91,z),m["glass"],.03)
    for x in (7.5,11,14):
        box(col,root,"roof_planter",(2.3,1.15,.62),
            (x,-2,.35+4*3.05+.35),m["brick"])
        cyl(col,root,"roof_shrub",.58,1.4,
             (x,-2,.35+4*3.05+1.05),m["plant"])
    box(col,root,"high_cap",(20.2,d-2.8,.28),
        (-4,.7,.35+6*3.05+.14),m["slate"])
    roof_details(col,root,m,19.4,d-3,.63+6*3.05)
    return col,root


def corner(m):
    col, root = collection("NC04_Corner_Lodge")
    w,d,f = 34,26,5
    landscape(col,root,m,w,d)
    box(col,root,"long_wing",(w,11,f*3.05),(0,6.5,.35+f*3.05/2),m["sage"],.1)
    box(col,root,"side_wing",(12,d,f*3.05),(-11,0,.35+f*3.05/2),m["cream"],.1)
    for floor in range(f):
        z=.35+floor*3.05+1.55
        for x in (-13,-7,-1,5,11):
            box(col,root,"front_window",(1.7,.16,1.55),(x,.91,z),m["glass"],.03)
        for y in (-8,-2,4,10):
            box(col,root,"side_window",(.16,1.7,1.55),(-4.91,y,z),m["glass"],.03)
            box(col,root,"outer_side_window",(.16,1.7,1.55),(-17.09,y,z),m["glass"],.03)
        for x in (-5,1,7,13):
            box(col,root,"rear_wing_window",(1.7,.16,1.55),(x,12.09,z),m["glass"],.03)
        for x in (-14,-10,-6):
            box(col,root,"south_wing_window",(1.7,.16,1.55),(x,-13.09,z),m["glass"],.03)
    facade_bands(col,root,m,w,11,f)
    entry(col,root,m,.88,10,6.2)
    box(col,root,"lobby_lantern",(7,3.2,5.4),(10,2.2,3.05),m["warm"],.08)
    box(col,root,"long_roof",(w-.8,10.2,.28),(0,6.5,.35+f*3.05+.14),m["slate"])
    box(col,root,"side_roof",(11.2,d-.8,.3),(-11,0,.35+f*3.05+.16),m["slate"])
    roof_details(col,root,m,10.6,d-.8,.65+f*3.05)
    return col,root


def setup_review(m):
    scene=bpy.context.scene
    scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=scene.render.resolution_y=720
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value=(.58,.70,.82,1); bg.inputs["Strength"].default_value=.55
    # Wide enough for the four-model layout saved into the combined Blend.
    box(scene.collection,None,"review_ground",(200,70,.18),(0,0,-.12),m["concrete"])
    for kind,loc,energy,size in (("AREA",(-14,-18,26),1200,10),
                                  ("AREA",(18,5,18),700,14)):
        bpy.ops.object.light_add(type=kind,location=loc)
        bpy.context.object.data.energy=energy; bpy.context.object.data.shape="DISK"
        bpy.context.object.data.size=size
    bpy.ops.object.light_add(type="SUN",location=(0,0,30))
    bpy.context.object.rotation_euler=(math.radians(28),math.radians(-18),math.radians(-32))
    bpy.context.object.data.energy=2
    bpy.ops.object.camera_add(); cam=bpy.context.object; cam.data.lens=52; scene.camera=cam
    return scene,cam


def aim(cam,eye,target=(0,0,6.5)):
    cam.location=eye
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()


def export(col,root,path):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in col.all_objects: obj.select_set(True)
    root.select_set(True); bpy.context.view_layer.objects.active=root
    bpy.ops.export_scene.gltf(filepath=str(path),export_format="GLB",
        use_selection=True,export_apply=True,export_cameras=False,export_lights=False)


def render(scene,cam,col,out,name):
    for other in bpy.data.collections:
        if other.name.startswith("NC0"): other.hide_render = other != col
    for label,eye in (("front",(0,-56,24)),
                      ("left_oblique",(-42,-44,25)),
                      ("right_oblique",(42,-44,25))):
        aim(cam,eye); scene.render.filepath=str(out/f"{name}_{label}.png")
        bpy.ops.render.render(write_still=True)


def main():
    out=get_output(); reset(); m=materials()
    assets=[("NC01_Parkline",*parkline(m)),("NC02_Gable_Court",*gable(m)),
            ("NC03_Terrace_House",*terrace(m)),("NC04_Corner_Lodge",*corner(m))]
    scene,cam=setup_review(m)
    for name,col,root in assets:
        export(col,root,out/f"{name}.glb"); render(scene,cam,col,out,name)
    for index,(_,_,root) in enumerate(assets): root.location.x=(index-1.5)*48
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"North_Crown_Apartment_Prototypes.blend"))
    (out/"README.txt").write_text(
        "North Crown apartment review pack\nFour GLBs, three QA angles each, and combined Blend.\n"
        "Canonical city and state were not opened or changed.\n",encoding="utf-8")
    print("NORTH_CROWN_PROTOTYPES_OK",out)


if __name__ == "__main__": main()
