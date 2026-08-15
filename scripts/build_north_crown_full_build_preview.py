"""Build and render an isolated full-build North Crown review scene.

Run only against a COPY of neighborhood.blend. The script imports production
builders with FOLLOWVILLE_IMPORT_ONLY, creates a separate preview collection,
and saves back to the explicitly supplied review Blend. It never writes state,
GLBs, manifests, the website, or the canonical Blend.
"""

import json
import math
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "work" / "asset-review" / "north-crown-full-build"
CANONICAL_BLEND = (ROOT / "neighborhood.blend").resolve()
PREVIEW_COLLECTION = "NORTH_CROWN_FULL_BUILD_PREVIEW"
DATUM = 5.0


def checkpoint(out, message):
    with (out / "build_progress.log").open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
    print("NORTH_CROWN_CHECKPOINT", message, flush=True)


def args():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = DEFAULT_OUT
    if "--output-dir" in raw:
        out = Path(raw[raw.index("--output-dir") + 1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    blend = Path(bpy.data.filepath).resolve()
    if blend == CANONICAL_BLEND or not blend.is_relative_to(out):
        raise RuntimeError("preview must run from a Blend copy inside output-dir")
    return out, blend


def import_production():
    os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"
    sys.path.insert(0, str(ROOT))
    import neighborhood_blender as nb
    import neighborhood_plan as np
    import metropolitan_plan as mp
    return nb, np, mp


def import_prototypes():
    path = ROOT / "scripts" / "build_north_crown_apartment_prototypes.py"
    spec = spec_from_file_location("north_crown_apartment_prototypes", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_preview():
    old = bpy.data.collections.get(PREVIEW_COLLECTION)
    if old:
        for obj in list(old.all_objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new(PREVIEW_COLLECTION)
    bpy.context.scene.collection.children.link(col)
    return col


def material(nb, name, color, rough=.9, metallic=0, emission=None):
    return nb.mat(name, color, rough, metallic=metallic)


def add_existing_plan_completion(nb, np, col, state, mats):
    active = max((int(b.get("plan_id", 0)) for b in state["buildings"]), default=0)
    created = []
    for item in np.PLAN["houses"]:
        if item["plan_id"] <= active:
            continue
        b = {
            "type": item["type"], "gx": 0, "gy": 0,
            "px": item["x"], "py": item["y"], "rot": item["rot"],
            "plan_id": item["plan_id"], "district": item["district"],
            "street": item["street"], "seed": 20000 + item["plan_id"],
        }
        created.append(nb.place_instance(col, b, "preview_reserved_%04d" % item["plan_id"]))

    # Only road pieces not present at today's reveal are added. The first new
    # vertex meets the standing road, so the preview has no detached stubs.
    shoulder = nb.mat("FV_preview_existing_shoulder", (.24,.27,.25), .99)
    path_mat = nb.mat("FV_preview_existing_path", (.52,.49,.42), .99)
    by_street = {}
    for segment in np.PLAN["roads"]:
        if segment["reveal_at"] > active:
            by_street.setdefault(segment["street_index"], []).append(segment)
    for street_index, segments in by_street.items():
        points2 = [np.transform_point_pair(segments[0])[0]]
        points2.extend(np.transform_point_pair(seg)[1] for seg in segments)
        points = [(x, y, nb.terrain_height(x, y)) for x, y in points2]
        nb._add_road_strip(col, "preview_reserved_shoulder_%02d" % street_index,
                           points, shoulder, width=7.35,
                           bottom_offset=.005, top_offset=.045,
                           terrain_conform=True)
        nb._add_road_strip(col, "preview_reserved_road_%02d" % street_index,
                           points, mats["road"], width=6.0,
                           bottom_offset=.015, top_offset=.085,
                           terrain_conform=True)
        side = 4.35 if street_index % 2 == 0 else -4.35
        path = nb._offset_terrain_path(points, side)
        nb._add_road_strip(col, "preview_reserved_path_%02d" % street_index,
                           path, path_mat, width=1.18,
                           bottom_offset=.005, top_offset=.035,
                           terrain_conform=True)
    for bulb in np.PLAN["turnarounds"]:
        if bulb["reveal_at"] <= active:
            continue
        x, y = np.transform_point_pair({"a": bulb["center"], "b": bulb["center"],
                                        "district": bulb.get("district")})[0]
        obj = nb._add_ellipse_pad(col, "preview_reserved_culdesac", x, y,
                                  8.2, 8.2, .012, .083, mats["road"], 32)
        obj.location.z = nb.terrain_height(x, y)
    return active, len(created)


def add_crown_quarter(nb, mp, col, mats):
    towers = []
    for slot in mp.TOWER_PLAN:
        b = {
            "type": "metrotower", "gx": 0, "gy": 0,
            "px": slot["x"], "py": slot["y"], "pz": slot["z"],
            "rot": slot["rot"], "seed": 30000 + slot["metro_id"],
            "metro_id": slot["metro_id"], "district": slot["district"],
            "street": slot["street"], "resident_capacity": 100,
            "residents": 100,
        }
        towers.append(b)
        nb.place_instance(col, b, "preview_metro_%02d" % slot["metro_id"])
    nb.build_metropolitan_district(col, towers, mats)
    return len(towers)


def add_terrain_extension(nb, col, m):
    grass = nb.mat("FV_north_crown_grass", (.34,.56,.29), 1.0)
    bank = nb.mat("FV_north_crown_bank", (.29,.47,.25), 1.0)
    water = nb.mat("FV_north_crown_river", (.12,.43,.59), .24)
    # Two continuous land plates leave a real lowered river channel. Their
    # tops meet the 5m Crown/West datum; no house gets an individual block.
    # Extend well beyond the authored blocks so low street cameras never see
    # the temporary planning terrain's far vertical edge on the horizon.
    nb.add_box(col, "north_crown_ground_west", 1305, 1300, .46,
               -307.5, 1568, DATUM-.46, grass)
    nb.add_box(col, "north_crown_ground_east", 415, 1300, .46,
               592.5, 1568, DATUM-.46, grass)
    nb.add_box(col, "north_crown_river_bed", 40, 1300, .42,
               365, 1568, DATUM-1.02, bank)
    nb.add_box(col, "north_crown_river_water", 29, 1300, .10,
               365, 1568, DATUM-.57, water)


def road_strip(nb, col, name, points2, width, mat, z=DATUM):
    points = [(x, y, z) for x, y in points2]
    return nb._add_road_strip(col, name, points, mat, width=width,
                              bottom_offset=.015, top_offset=.16)


def offset_flat(points2, offset, z=DATUM+.17):
    result=[]
    for index,(x,y) in enumerate(points2):
        before=points2[max(0,index-1)]; after=points2[min(len(points2)-1,index+1)]
        dx,dy=after[0]-before[0],after[1]-before[1]
        length=max(.001,math.hypot(dx,dy))
        result.append((x-dy/length*offset,y+dx/length*offset,z))
    return result


def add_street_lamp(nb,col,x,y,mat,pale,height=5.2):
    nb.add_box(col,"north_crown_lamp_post",.16,.16,height,x,y,DATUM+.18,mat)
    nb.add_box(col,"north_crown_lamp_arm",1.35,.14,.14,x+.58,y,DATUM+height+.10,mat)
    nb.add_box(col,"north_crown_lamp_head",.62,.42,.18,x+1.17,y,DATUM+height-.02,pale)


def add_parkway_and_local_roads(nb, col, mats):
    asphalt, pale = mats["road"], mats["dash"]
    curb = nb.mat("FV_north_crown_curb", (.55,.54,.50), .96)
    sidewalk = nb.mat("FV_north_crown_sidewalk", (.68,.66,.60), .94)
    median = nb.mat("FV_north_crown_median", (.30,.53,.28), 1.0)
    signal = nb.mat("FV_north_crown_signal", (.16,.20,.20), .72, metallic=.18)
    red = nb.mat("FV_north_crown_red", (.84,.12,.09), .42)
    amber = nb.mat("FV_north_crown_amber", (.96,.58,.08), .42)
    green = nb.mat("FV_north_crown_green", (.10,.65,.30), .42)
    tree = nb.mat("FV_north_crown_tree", (.22,.46,.23), .98)
    trunk = mats["trunk"]

    road_strip(nb,col,"north_crown_parkway",[(-766,930),(278,930)],16,asphalt)
    for yoff in (-11.1,11.1):
        road_strip(nb,col,"north_crown_parkway_walk",[(-766,930+yoff),(190,930+yoff)],3.2,sidewalk,z=DATUM+.02)
    # Median sections stop for every signalized junction.
    signals=(-680,-540,-400,-260,-120,20,160)
    limits=(-766,)+signals+(190,)
    for a,b in zip(limits,limits[1:]):
        if b-a>18:
            nb.add_box(col,"north_crown_median",b-a-12,2.7,.28,
                       (a+b)/2,930,DATUM+.16,median)
    for x in range(-750,181,24):
        if min(abs(x-s) for s in signals)<9: continue
        for y in (918.9,941.1):
            nb.add_ngon_cone(col,"north_crown_tree_trunk",.20,.17,2.2,7,x,y,DATUM+.20,trunk)
            nb.add_ngon_cone(col,"north_crown_tree",1.35,.42,2.8,8,x,y,DATUM+2.35,tree)
    # Four-lane markings and stop bars.
    for offset in (-5.0,5.0):
        for x in range(-750,180,15):
            nb.add_box(col,"north_crown_lane_dash",5.2,.13,.025,x,930+offset,DATUM+.18,pale)
    for x in signals:
        for y in (921.2,938.8):
            nb.add_box(col,"north_crown_stop_bar",.25,6.4,.035,x-5 if y<930 else x+5,y,DATUM+.19,pale)
        for dx in (-5.4,-4.2,-3.0,-1.8,-.6,.6,1.8,3.0,4.2,5.4):
            nb.add_box(col,"north_crown_crosswalk",.46,15.2,.028,
                       x+dx,930,DATUM+.205,pale)
        # Four mast arms with three physically separated signal lenses.
        for side in (-1,1):
            sy=930+side*11.8
            nb.add_box(col,"north_crown_signal_pole",.25,.25,6.2,x,sy,DATUM+.18,signal)
            nb.add_box(col,"north_crown_signal_arm",7.0,.20,.20,x,sy-side*3.4,DATUM+6.18,signal)
            nb.add_box(col,"north_crown_signal_head",.72,.30,1.72,
                       x,sy-side*5.62,DATUM+4.62,signal)
            for index,lens in enumerate((red,amber,green)):
                nb.add_box(col,"north_crown_signal_lens",.38,.12,.38,
                           x,sy-side*5.79,DATUM+5.80-index*.50,lens)

    collectors=(-680,-540,-400,-260,-120,20,160)
    for x in collectors:
        # x=-400 is the gated campus drive north of the parkway.
        north_end = 952 if x == -400 else 1404
        road_strip(nb,col,"north_crown_collector",[(x,826),(x,north_end)],8,asphalt)

    rows=(980,1030,1080,1130,1180,1230,1280,1330,1380)
    districts=(
        ("Harrow North",-766,-548), ("Forge Park",-548,-258),
        ("Crown Gardens",-258,-48), ("Maple North",-48,92),
        ("Anvil Meadows",92,190),
    )
    road_segments=[]
    for dindex,(name,x0,x1) in enumerate(districts):
        for rindex,y in enumerate(rows):
            segments=[(x0,x1)]
            if name == "Forge Park" and y <= 1180:
                segments=[(x0,-472)]
            for sx0,sx1 in segments:
                if sx1-sx0<24: continue
                # A restrained curve gives the streets character without
                # consuming the house setback at the inside of the bend.
                wiggle=1.0 if (rindex+dindex)%2==0 else -1.0
                pts=[(sx0,y),(sx0+(sx1-sx0)*.28,y+wiggle),
                     (sx0+(sx1-sx0)*.62,y-wiggle),(sx1,y)]
                road_strip(nb,col,"north_crown_local",pts,6,asphalt)
                # Continuous curbs and sidewalks make these read as finished
                # neighborhoods rather than house rows placed on grass.
                points3=[(x,yy,DATUM+.18) for x,yy in pts]
                for side in (-1,1):
                    curb_path=offset_flat(pts,side*3.22,DATUM+.17)
                    nb._add_road_strip(col,"north_crown_local_curb",curb_path,curb,
                                       width=.32,bottom_offset=.01,top_offset=.18)
                    walk_path=offset_flat(pts,side*4.72,DATUM+.18)
                    nb._add_road_strip(col,"north_crown_local_walk",walk_path,sidewalk,
                                       width=2.15,bottom_offset=.01,top_offset=.11)
                # Lamps alternate sides at a walkable residential interval.
                span=sx1-sx0
                lamp_count=max(1,int(span/72))
                for lamp_index in range(lamp_count+1):
                    lx=sx0+12+(span-24)*lamp_index/max(1,lamp_count)
                    ly=y+(5.95 if (lamp_index+rindex+dindex)%2 else -5.95)
                    add_street_lamp(nb,col,lx,ly,signal,pale,4.8)
                road_segments.append({"district":name,"row":y,"points":pts,"width":6})
    return districts, rows, road_segments


def evenly_sample(items, count):
    if len(items)<count:
        raise RuntimeError("not enough preview lots: %d < %d"%(len(items),count))
    return [items[int((i+.5)*len(items)/count)] for i in range(count)]


def point_polyline_distance(x,y,points):
    best=float("inf")
    for (ax,ay),(bx,by) in zip(points,points[1:]):
        dx,dy=bx-ax,by-ay
        denom=dx*dx+dy*dy
        t=0 if denom<=1e-9 else max(0,min(1,((x-ax)*dx+(y-ay)*dy)/denom))
        best=min(best,math.hypot(x-(ax+t*dx),y-(ay+t*dy)))
    return best


def add_north_crown_houses(nb, col, districts, rows, road_segments):
    # The district totals deliberately shift some density westward so the
    # apartment campus and every collector intersection retain real setbacks.
    targets={"Harrow North":250,"Forge Park":190,"Crown Gardens":230,
             "Maple North":175,"Anvil Meadows":155}
    collectors=(-680,-540,-400,-260,-120,20,160)
    driveway=nb.mat("FV_north_crown_driveway",(.24,.25,.24),.97)
    walk=nb.mat("FV_north_crown_front_walk",(.67,.65,.59),.94)
    hedge=nb.mat("FV_north_crown_hedge",(.20,.42,.20),.98)
    mailbox=nb.mat("FV_north_crown_mailbox",(.18,.22,.24),.72,metallic=.12)
    total=0
    min_local=float("inf"); min_collector=float("inf")
    for dindex,(name,x0,x1) in enumerate(districts):
        step=7.0 if name=="Anvil Meadows" else (9.0 if name=="Maple North" else 10.2)
        candidates=[]
        for rindex,y in enumerate(rows):
            n=max(1,int((x1-x0-18)/step))
            for ix in range(n+1):
                x=x0+9+(x1-x0-18)*ix/max(1,n)
                # Conservative exclusion: 4m collector half-width + the
                # widest production-house half-width + over 5m clear space.
                if min(abs(x-c) for c in collectors)<13.0: continue
                for side in (-1,1):
                    hy=y+side*13.5
                    if -480<x<-244 and 946<hy<1237: continue
                    candidates.append((rindex,ix,side,x,hy))
        # A stable spatial sort followed by an even sample fills every row.
        candidates.sort(key=lambda v:(v[0],v[1],v[2]))
        chosen=evenly_sample(candidates,targets[name])
        for local,(rindex,ix,side,x,y) in enumerate(chosen):
            plan_id=2200+total
            b={"type":"house","gx":0,"gy":0,"px":round(x,3),"py":round(y,3),
               "pz":DATUM+.18,"rot":0.0 if side>0 else math.pi,
               "plan_id":plan_id,"district":name,"street":"North Crown local",
               "seed":47000+dindex*1000+local}
            obj=nb.place_instance(col,b,"preview_north_crown_%04d"%total)
            # The tightest eastern neighborhood uses a modest compact-lot scale.
            if name=="Anvil Meadows": obj.scale=(.68,.68,.82); obj["nb_rest_scale"]=tuple(obj.scale)
            source=next(iter(obj.instance_collection.all_objects))
            half_x=source.dimensions.x*obj.scale.x/2
            half_y=source.dimensions.y*obj.scale.y/2
            own_roads=[item for item in road_segments
                       if item["district"]==name and item["row"]==rows[rindex]
                       and item["points"][0][0]-1<=x<=item["points"][-1][0]+1]
            if own_roads:
                center_distance=min(point_polyline_distance(x,y,item["points"])
                                    for item in own_roads)
                min_local=min(min_local,center_distance-3.0-half_y)
            min_collector=min(min_collector,
                              min(abs(x-c)-4.0-half_x for c in collectors))
            # A driveway intentionally bridges the curb/sidewalk; the house
            # itself remains more than 5m clear of all rendered road edges.
            road_y=rows[rindex]
            drive_len=7.0
            drive_center=road_y+side*(3.15+drive_len/2)
            nb.add_box(col,"north_crown_driveway",2.8,drive_len,.035,
                       x,drive_center,DATUM+.285,driveway)
            nb.add_box(col,"north_crown_front_walk",1.05,2.2,.04,
                       x+2.05,road_y+side*11.8,DATUM+.19,walk)
            if local%4==0:
                nb.add_box(col,"north_crown_mailbox_post",.12,.12,1.05,
                           x-2.1,road_y+side*6.05,DATUM+.27,mailbox)
                nb.add_box(col,"north_crown_mailbox",.55,.32,.38,
                           x-2.1,road_y+side*6.05,DATUM+1.27,mailbox)
            if local%5==0:
                nb.add_ngon_cone(col,"north_crown_yard_tree",1.15,.35,2.5,8,
                                 x+3.7,road_y+side*10.4,DATUM+.18,hedge)
            total+=1
    if total!=1000: raise AssertionError(total)
    clearance={"minimum_local_road_edge_m":round(min_local,3),
               "minimum_collector_road_edge_m":round(min_collector,3)}
    if min_local<4.5 or min_collector<4.5:
        raise RuntimeError("house-road clearance failed: %r"%clearance)
    return total,clearance


def add_apartment_campus(nb, col):
    pad=nb.mat("FV_north_crown_campus_paving",(.66,.64,.59),.93)
    fence=nb.mat("FV_north_crown_fence",(.18,.22,.22),.72,metallic=.18)
    water=nb.mat("FV_north_crown_pool",(.10,.54,.72),.18)
    deck=nb.mat("FV_north_crown_pool_deck",(.82,.76,.65),.92)
    green=nb.mat("FV_north_crown_campus_green",(.25,.50,.25),.98)
    parking=nb.mat("FV_north_crown_parking",(.20,.22,.22),.98)
    stripe=nb.mat("FV_north_crown_parking_stripe",(.92,.88,.69),.74)
    brick=nb.mat("FV_north_crown_gate_brick",(.46,.27,.20),.91)
    glass=nb.mat("FV_north_crown_gate_glass",(.12,.31,.38),.22,metallic=.05)
    lamp=nb.mat("FV_north_crown_gate_lamp",(.98,.68,.24),.26)
    # The campus is now a graded lawn with individual walks, parking courts
    # and building aprons—not a raised gray platform.
    nb.add_box(col,"north_crown_campus_lawn",200,275,.12,-370,1087.5,DATUM-.06,green)

    # Real perimeter fence: masonry piers, vertical posts and three rails. The
    # south side is broken only at the controlled 16m entrance.
    def fence_x(x0,x1,y,name):
        for z in (DATUM+.48,DATUM+1.05,DATUM+1.62):
            nb.add_box(col,name+"_rail",x1-x0,.12,.11,(x0+x1)/2,y,z,fence)
        count=max(1,int((x1-x0)/5.5))
        for i in range(count+1):
            x=x0+(x1-x0)*i/count
            nb.add_box(col,name+"_post",.16,.16,1.95,x,y,DATUM+.08,fence)
    def fence_y(x,y0,y1,name):
        for z in (DATUM+.48,DATUM+1.05,DATUM+1.62):
            nb.add_box(col,name+"_rail",.12,y1-y0,.11,x,(y0+y1)/2,z,fence)
        count=max(1,int((y1-y0)/5.5))
        for i in range(count+1):
            y=y0+(y1-y0)*i/count
            nb.add_box(col,name+"_post",.16,.16,1.95,x,y,DATUM+.08,fence)
    fence_x(-470,-378,950,"north_crown_fence_south_w")
    fence_x(-362,-270,950,"north_crown_fence_south_e")
    fence_x(-470,-270,1225,"north_crown_fence_north")
    fence_y(-470,950,1225,"north_crown_fence_west")
    fence_y(-270,950,1225,"north_crown_fence_east")
    for x in (-470,-378,-362,-270):
        nb.add_box(col,"north_crown_fence_pier",.72,.72,2.45,x,950,DATUM+.06,brick)
        nb.add_box(col,"north_crown_fence_pier_cap",.92,.92,.18,x,950,DATUM+2.51,pad)

    # Main drive, cross aisles, parking courts and walk network.
    road=nb.std_mats()["road"]
    road_strip(nb,col,"north_crown_campus_drive",[(-370,930),(-370,1216)],8.5,road,z=DATUM-.03)
    for x in (-376,-364):
        road_strip(nb,col,"north_crown_campus_spine_walk",[(x,958),(x,1216)],2.1,pad,z=DATUM-.04)
    for y in (1007,1123,1173):
        nb.add_box(col,"north_crown_parking_court",188,18,.07,-370,y,DATUM+.06,parking)
        for x in list(range(-458,-379,6))+list(range(-356,-277,6)):
            for side in (-1,1):
                nb.add_box(col,"north_crown_parking_stripe",.10,5.2,.025,
                           x,y+side*6.25,DATUM+.135,stripe)
        nb.add_box(col,"north_crown_parking_centerline",188,.10,.025,
                   -370,y,DATUM+.135,stripe)
        car_colors=((.18,.38,.62),(.68,.22,.17),(.22,.52,.36),
                    (.72,.66,.50),(.30,.31,.34),(.56,.38,.63))
        car_xs=(-451,-433,-415,-397,-343,-325,-307,-289)
        for car_index,x in enumerate(car_xs):
            side=-1 if (car_index+int(y))%2 else 1
            nb.build_lowpoly_car(col,
                style=("sedan","hatchback","pickup")[car_index%3],
                color=car_colors[(car_index+int(y))%len(car_colors)],
                px=x,py=y+side*5.7,pz=DATUM+.07)
    for y in (1007,1123,1173):
        road_strip(nb,col,"north_crown_campus_cross_aisle",[(-462,y),(-278,y)],6,road,z=DATUM-.03)
    # Gatehouse, illuminated sign pylons and two real swing-gate leaves.
    nb.add_box(col,"north_crown_gatehouse",8,5,3.45,-384.5,958,DATUM+.07,brick)
    nb.add_box(col,"north_crown_gatehouse_roof",9.2,6.2,.28,-384.5,958,DATUM+3.52,pad)
    nb.add_box(col,"north_crown_gatehouse_window",4,.16,1.6,-384.5,955.42,DATUM+1.12,glass)
    nb.add_box(col,"north_crown_gatehouse_side_window",.16,2.2,1.45,-380.42,958,DATUM+1.16,glass)
    nb.add_box(col,"north_crown_gatehouse_door",1.15,.14,2.3,-386.3,955.40,DATUM+.15,glass)
    nb.add_box(col,"north_crown_gatehouse_canopy",4.8,1.6,.20,-384.5,954.7,DATUM+2.98,pad)
    nb.add_box(col,"north_crown_entry_sign",10.5,.34,1.25,-370,952.4,DATUM+3.25,brick)
    for x,direction in ((-378,1),(-362,-1)):
        nb.add_box(col,"north_crown_gate_hinge",.28,.28,2.0,x,950,DATUM+.15,fence)
        nb.add_box(col,"north_crown_gate_toprail",7.7,.16,.12,x+direction*3.85,950,DATUM+1.75,fence)
        nb.add_box(col,"north_crown_gate_bottomrail",7.7,.16,.12,x+direction*3.85,950,DATUM+.48,fence)
        for i in range(9):
            gx=x+direction*(.45+i*.9)
            nb.add_box(col,"north_crown_gate_picket",.10,.12,1.33,gx,950,DATUM+.48,fence)
        nb.add_box(col,"north_crown_gate_lantern",.42,.42,.48,x,950,DATUM+2.72,lamp)

    # Append the four already-reviewed source collections from their isolated
    # asset library. Re-authoring hundreds of facade objects inside the full
    # city makes Blender recalculate the populated dependency graph for every
    # window; appending preserves the exact geometry without that penalty.
    library=(ROOT/"work"/"asset-review"/"north-crown-apartments-v2"/
             "North_Crown_Apartment_Prototypes.blend")
    source_names=("NC01_Parkline","NC02_Gable_Court",
                  "NC03_Terrace_House","NC04_Corner_Lodge")
    if not library.exists():
        raise RuntimeError("missing reviewed apartment library: %s"%library)
    with bpy.data.libraries.load(str(library),link=False) as (available,loaded):
        missing=[name for name in source_names if name not in available.collections]
        if missing:
            raise RuntimeError("apartment library missing: %s"%", ".join(missing))
        loaded.collections=list(source_names)
    sources=list(loaded.collections)
    for source in sources:
        # The prototype contact-sheet Blend hides three collections while it
        # renders each model in isolation. All four must render when instanced.
        source.hide_render=False
        source.hide_viewport=False
        # The review Blend spaces prototypes apart for inspection. Collection
        # instances need each source centered on its own local origin.
        for obj in source.objects:
            if obj.parent is None:
                obj.location=(0,0,0)
    xs=(-445,-397,-343,-295); ys=(982,1032,1098,1148,1198)
    roots=[]
    for row,y in enumerate(ys):
        for column,x in enumerate(xs):
            nb.add_box(col,"north_crown_building_apron",33,25,.06,x,y,DATUM+.06,pad)
            source=sources[(row+column)%4]
            instance=bpy.data.objects.new("NorthCrown_Apartment_%02d"%len(roots),None)
            instance.instance_type="COLLECTION"
            instance.instance_collection=source
            instance.location=(x,y,DATUM+.12)
            instance.rotation_euler.z=math.pi if row%2 else 0
            instance.scale=(.78,.78,.90)
            instance["nb_rest_scale"]=tuple(instance.scale)
            col.objects.link(instance)
            roots.append(instance)
    # Pool courtyard occupies the deliberate central gap between buildings.
    px,py=-421,1065
    nb.add_box(col,"north_crown_pool_deck",18,24,.12,px,py,DATUM+.06,deck)
    nb.add_box(col,"north_crown_pool_basin",14,11,.72,px,py,DATUM-.48,fence)
    nb.add_box(col,"north_crown_pool_water",13.4,10.4,.10,px,py,DATUM+.20,water)
    for side in (-1,1):
        nb.add_box(col,"north_crown_pool_fence_x",18,.10,.10,px,py+side*12,DATUM+1.43,fence)
        nb.add_box(col,"north_crown_pool_fence_y",.10,24,.10,px+side*9,py,DATUM+1.43,fence)
    for x in (px-9,px+9):
        for y in range(py-12,py+13,4):
            nb.add_box(col,"north_crown_pool_fence_post",.12,.12,1.48,x,y,DATUM+.08,fence)
    for y in (py-12,py+12):
        for x in range(int(px-9),int(px+10),4):
            nb.add_box(col,"north_crown_pool_fence_post",.12,.12,1.48,x,y,DATUM+.08,fence)
    for side in (-1,1):
        nb.add_box(col,"north_crown_pool_lounger",2.0,.72,.18,px+side*6.8,py-8,DATUM+.20,pad)
        nb.add_box(col,"north_crown_pool_lounger_back",.72,.72,.85,px+side*6.8,py-7.35,DATUM+.20,pad)
    for x in (px-6.4,px+6.4):
        nb.add_box(col,"north_crown_pool_bench",2.8,.62,.22,x,py+8.3,DATUM+.20,brick)
        nb.add_box(col,"north_crown_pool_bench_back",2.8,.16,.72,x,py+8.58,DATUM+.40,brick)
    # Planted parking islands break up asphalt and protect aisle ends.
    for x in (-459,-370,-281):
        for y in (1007,1123,1173):
            nb.add_box(col,"north_crown_parking_island",4.2,3.0,.18,x,y,DATUM+.13,green)
            nb.add_ngon_cone(col,"north_crown_parking_island_tree",.82,.25,2.3,8,
                             x,y,DATUM+.31,green)
    # Trees, shrubs, benches and pedestrian lighting complete the enclosure.
    for x in (-460,-280):
        for y in (975,1045,1115,1190):
            nb.add_ngon_cone(col,"north_crown_campus_tree_trunk",.22,.16,2.4,7,x,y,DATUM+.06,fence)
            nb.add_ngon_cone(col,"north_crown_campus_tree",1.55,.38,3.2,9,x,y,DATUM+2.42,green)
    for y in (985,1055,1135,1205):
        for x in (-379,-361):
            add_street_lamp(nb,col,x,y,fence,lamp,4.6)
    for y in ys:
        for x in xs:
            for dx in (-11,11):
                nb.add_box(col,"north_crown_apartment_shrub",2.1,.72,.62,
                           x+dx,y-10.8,DATUM+.12,green)
    return len(roots)


def add_expressway_extension(nb, col, mats):
    asphalt=mats["road"]
    concrete=nb.mat("FV_north_crown_highway_concrete",(.42,.43,.42),.97)
    rail=nb.mat("FV_north_crown_highway_rail",(.22,.25,.25),.78,metallic=.18)
    pale=mats["dash"]
    pts=[(222,y,14.0) for y in range(858,1466,3)]
    nb._add_road_strip(col,"north_crown_expressway_structure",pts,concrete,
                       width=25.8,bottom_offset=-1.05,top_offset=-.04)
    nb._add_road_strip(col,"north_crown_expressway_deck",pts,asphalt,
                       width=24,bottom_offset=-.03,top_offset=.18)
    for x in (210,222,234):
        nb.add_box(col,"north_crown_expressway_barrier",.38,607,.82,x,1161.5,14.18,rail)
    for y in range(880,1450,38):
        for x in (215.8,228.2):
            nb.add_ngon_cone(col,"north_crown_expressway_pier",.95,.72,8.0,8,x,y,DATUM,concrete)
        nb.add_box(col,"north_crown_expressway_cap",17,1.2,.75,222,y,12.28,concrete)
    for x in (214,218,226,230):
        for y in range(870,1455,12):
            nb.add_box(col,"north_crown_expressway_dash",.13,4,.025,x,y,14.185,pale)
    # Second diamond interchange centered on North Crown Parkway.
    ramps=(
      [(215.5,862,14),(205,880,12),(198,906,8),(188,930,5.18)],
      [(188,930,5.18),(198,954,8),(205,980,12),(215.5,1004,14)],
      [(228.5,1004,14),(240,980,12),(248,954,8),(258,930,5.18)],
      [(258,930,5.18),(248,906,8),(240,880,12),(228.5,862,14)],
    )
    for index,ramp in enumerate(ramps):
        nb._add_road_strip(col,"north_crown_interchange_shoulder_%d"%index,
                           ramp,concrete,width=6.5,bottom_offset=-.40,top_offset=.08)
        nb._add_road_strip(col,"north_crown_interchange_ramp_%d"%index,
                           ramp,asphalt,width=5.4,bottom_offset=-.34,top_offset=.14)
        for point_index,(x,y,z) in enumerate(ramp):
            if point_index in (0,len(ramp)-1): continue
            nb.add_box(col,"north_crown_ramp_delineator",.16,.16,.95,
                       x-3.0,y,z+.05,rail)
            nb.add_box(col,"north_crown_ramp_reflector",.22,.08,.16,
                       x-3.0,y,z+.94,pale)
    # Exit guide sign and gantry make the interchange legible at city scale.
    guide=nb.mat("FV_north_crown_guide_sign",(.04,.30,.17),.66)
    for x in (214,230):
        nb.add_box(col,"north_crown_sign_post",.22,.22,5.2,x,1038,14.20,rail)
    nb.add_box(col,"north_crown_sign_gantry",16.2,.22,.24,222,1038,19.15,rail)
    nb.add_box(col,"north_crown_exit_sign",8.8,.28,2.4,226,1038,17.25,guide)


def set_render_scene(nb, out):
    scene=bpy.context.scene
    # The guarded canonical Blend is already saved at its final frame (450 on
    # Day 44). Calling frame_set with that same value still forces Blender to
    # re-evaluate every historical growth animation and takes ~20 minutes in
    # this all-chapters preview, without changing the visible state.
    # Blender 5.1 filters the file-format enum by media type. The production
    # scene is configured for video, so return this isolated copy to stills.
    try:
        scene.render.image_settings.media_type="IMAGE"
    except (AttributeError,TypeError):
        pass
    for engine in ("BLENDER_EEVEE","BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine=engine
            break
        except Exception:
            continue
    scene.render.resolution_x=1920; scene.render.resolution_y=1080
    scene.render.resolution_percentage=100
    scene.render.use_sequencer=False
    scene.render.use_compositing=False
    scene.render.image_settings.file_format="PNG"
    scene.render.film_transparent=False
    scene.render.image_settings.color_mode="RGB"
    try: scene.render.image_settings.color_depth="8"
    except Exception: pass
    try: scene.render.image_settings.compression=18
    except Exception: pass
    for attr,value in (("taa_render_samples",96),("use_gtao",True),
                       ("gtao_distance",7.0),("use_soft_shadows",True),
                       ("shadow_cube_size","2048"),("shadow_cascade_size","2048")):
        try: setattr(scene.eevee,attr,value)
        except Exception: pass
    for transform in ("AgX","Filmic","Standard"):
        try: scene.view_settings.view_transform=transform; break
        except Exception: continue
    try: scene.view_settings.look="AgX - Medium High Contrast"
    except Exception: pass
    scene.view_settings.exposure=-.28
    scene.world.use_nodes=True
    background=scene.world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value=(.20,.32,.48,1)
        background.inputs["Strength"].default_value=.28
    # Disable inherited shot lights from the canonical animation. Review
    # lighting must be deterministic instead of stacking on whichever camera
    # setup happened to be saved last.
    for light_object in (obj for obj in bpy.data.objects if obj.type=="LIGHT"):
        light_object.hide_render=True
    # Purpose-built daylight and broad fill reveal real material, curb and
    # façade depth in the review renders.
    sun_data=bpy.data.lights.new("NorthCrown_Review_Sun","SUN")
    sun_data.energy=1.75; sun_data.angle=math.radians(8)
    sun=bpy.data.objects.new("NorthCrown_Review_Sun",sun_data)
    sun.rotation_euler=(math.radians(31),math.radians(-18),math.radians(-38))
    scene.collection.objects.link(sun)
    fill_data=bpy.data.lights.new("NorthCrown_Review_Fill","AREA")
    fill_data.energy=360; fill_data.shape="DISK"; fill_data.size=620
    fill=bpy.data.objects.new("NorthCrown_Review_Fill",fill_data)
    fill.location=(-220,800,620)
    fill.rotation_euler=(Vector((-220,1080,0))-fill.location).to_track_quat("-Z","Y").to_euler()
    scene.collection.objects.link(fill)
    bpy.ops.object.camera_add(); cam=bpy.context.object; cam.name="NorthCrown_FullBuild_Camera"
    cam.data.lens=48; cam.data.clip_end=6000; scene.camera=cam
    views={
      "01_full_city_aerial":((980,-1050,1050),(-140,570,55),46),
      "02_downtown_to_north_crown":((700,80,380),(-180,990,42),55),
      "03_highway_exit_and_parkway":((535,650,185),(40,955,22),50),
      "04_neighborhood_street":((-590,965,10.5),(-500,1030,6.5),55),
      "05_gated_campus_entry":((-315,875,28),(-370,963,7),52),
      "06_apartment_campus":((-155,860,128),(-375,1080,16),54),
      "07_pool_courtyard":((-540,1000,52),(-421,1065,7),58),
      "08_north_crown_overhead":((-220,780,1060),(-220,1050,0),58),
    }
    # Save the complete render-ready scenario and maintained cameras before
    # spending any time on screenshots.
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    for name,(eye,target,lens) in views.items():
        cam.location=eye; cam.data.lens=lens
        cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
        scene.render.filepath=str(out/(name+".png"))
        bpy.ops.render.render(write_still=True)
    return cam,views


def main():
    out,blend=args(); nb,np,mp=import_production()
    (out/"build_progress.log").write_text("START\n",encoding="utf-8")
    state=json.loads((ROOT/"world_state.json").read_text(encoding="utf-8"))
    col=clean_preview(); mats=nb.std_mats(); checkpoint(out,"BASE_READY")
    active,pending=add_existing_plan_completion(nb,np,col,state,mats)
    checkpoint(out,"RESERVED_COMPLETE_%d"%pending)
    towers=add_crown_quarter(nb,mp,col,mats); checkpoint(out,"CROWN_COMPLETE_%d"%towers)
    add_terrain_extension(nb,col,mats); checkpoint(out,"TERRAIN_COMPLETE")
    districts,rows,roads=add_parkway_and_local_roads(nb,col,mats)
    checkpoint(out,"ROADS_COMPLETE")
    houses,clearance=add_north_crown_houses(nb,col,districts,rows,roads)
    checkpoint(out,"HOUSES_COMPLETE_%d"%houses)
    checkpoint(out,"CLEARANCE_OK_LOCAL_%.3f_COLLECTOR_%.3f"%
               (clearance["minimum_local_road_edge_m"],
                clearance["minimum_collector_road_edge_m"]))
    apartments=add_apartment_campus(nb,col); checkpoint(out,"APARTMENTS_COMPLETE_%d"%apartments)
    add_expressway_extension(nb,col,mats); checkpoint(out,"EXPRESSWAY_COMPLETE")
    _cam,views=set_render_scene(nb,out); checkpoint(out,"RENDERS_COMPLETE")
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    checkpoint(out,"FINAL_BLEND_SAVED")
    manifest={"source_day":state["day"],"source_population":state["pop"],
              "active_plan_id":active,"remaining_reserved":pending,
              "crown_towers":towers,"north_crown_houses":houses,
              "apartment_buildings":apartments,"road_clearance":clearance,
              "renders":list(views)}
    (out/"preview_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("NORTH_CROWN_FULL_BUILD_OK",json.dumps(manifest,sort_keys=True))


if __name__=="__main__": main()
