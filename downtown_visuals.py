"""Experimental, state-free terrain and downtown redesign for Followville."""

import math
import random

import bpy

from downtown_visual_plan import TERRAIN_BOUNDS, terrain_height


DISTRICT_NAME = "Downtown Core"


def _material(name, color, roughness=.86, metallic=0.0, alpha=1.0,
              transmission=0.0, coat=0.0, ior=1.45):
    material = bpy.data.materials.get(name)
    if not material:
        material = bpy.data.materials.new(name)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Alpha"].default_value = alpha
    transmission_input = (shader.inputs.get("Transmission Weight")
                          or shader.inputs.get("Transmission"))
    if transmission_input:
        transmission_input.default_value = transmission
    coat_input = shader.inputs.get("Coat Weight") or shader.inputs.get("Clearcoat")
    if coat_input:
        coat_input.default_value = coat
    if shader.inputs.get("IOR"):
        shader.inputs["IOR"].default_value = ior
    material.diffuse_color = (*color, alpha)
    if alpha < .999:
        material.surface_render_method = "DITHERED"
        material.use_transparency_overlap = False
    return material


def _emissive_material(name, color, strength=3.0):
    material = _material(name, color, .24, .08)
    shader = material.node_tree.nodes.get("Principled BSDF")
    emission = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
    if emission:
        emission.default_value = (*color, 1.0)
    emission_strength = shader.inputs.get("Emission Strength")
    if emission_strength:
        emission_strength.default_value = strength
    return material


def _tag(obj, role, district=DISTRICT_NAME, chunk="downtown-redesign"):
    obj["fv_visual_role"] = role
    obj["fv_district"] = district
    obj["fv_chunk_hint"] = chunk
    obj["fv_non_claimable"] = True
    return obj


def _batch_boxes(collection, name, boxes, material, role):
    """Create axis-aligned boxes as one export-friendly mesh."""
    if not boxes:
        return None
    vertices, faces = [], []
    for x, y, z, width, depth, height in boxes:
        start = len(vertices)
        hw, hd = width*.5, depth*.5
        vertices.extend(((x-hw,y-hd,z),(x+hw,y-hd,z),(x+hw,y+hd,z),(x-hw,y+hd,z),
                         (x-hw,y-hd,z+height),(x+hw,y-hd,z+height),
                         (x+hw,y+hd,z+height),(x-hw,y+hd,z+height)))
        faces.extend(((start,start+1,start+2,start+3),(start+4,start+7,start+6,start+5),
                      (start,start+4,start+5,start+1),(start+1,start+5,start+6,start+2),
                      (start+2,start+6,start+7,start+3),(start+3,start+7,start+4,start)))
    mesh = bpy.data.meshes.new(name+"_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return _tag(obj, role)


def _bevel(obj, width=.08, segments=1):
    """Small real edge catches: the fastest way to stop boxes reading as beta primitives."""
    if not obj:
        return obj
    modifier = obj.modifiers.new("FV_edge_finish", "BEVEL")
    modifier.width = width
    modifier.segments = segments
    modifier.limit_method = "ANGLE"
    return obj


def _terrain_mesh(collection):
    grass = _material("FV_terrain_meadow", (.40,.62,.31), .98)
    high = _material("FV_terrain_highland", (.25,.39,.20), 1.0)
    rock = _material("FV_terrain_rock", (.38,.36,.32), 1.0)
    x0, x1, y0, y1 = TERRAIN_BOUNDS
    # Dense enough that browser-side analytic height sampling and the visible
    # mesh agree within a few centimetres on neighborhood grades.
    nx, ny = 129, 107
    vertices = []
    for iy in range(ny):
        y = y0+(y1-y0)*iy/(ny-1)
        for ix in range(nx):
            x = x0+(x1-x0)*ix/(nx-1)
            vertices.append((x,y,terrain_height(x,y)+.015))
    faces = []
    for iy in range(ny-1):
        for ix in range(nx-1):
            a=iy*nx+ix; b=a+1; c=a+nx+1; d=a+nx
            faces.append((a,b,c,d))
    mesh = bpy.data.meshes.new("regional_walkable_terrain_mesh")
    mesh.from_pydata(vertices, [], faces)
    # A single continuous ground color avoids artificial contour bands. The
    # elevation reads through real light, silhouette, and parallax instead.
    mesh.materials.append(grass)
    # Vertex color gives the continuous terrain natural variation without a
    # tiled bitmap or hard contour bands. It exports efficiently as COLOR_0.
    color_layer=mesh.color_attributes.new(name="fv_ground_color",type="BYTE_COLOR",domain="POINT")
    for index,(x,y,z) in enumerate(vertices):
        broad=.5+.5*math.sin(x*.017+math.sin(y*.011)*1.8)
        fine=.5+.5*math.sin(x*.071+y*.053)
        elevation=max(0,min(1,z/18.0))
        dry=max(0,min(1,.22*broad+.12*fine+.28*elevation))
        color_layer.data[index].color=(.26+.16*(1-dry),
                                       .40+.20*(1-dry),
                                       .20+.10*(1-dry),1.0)
    shader=grass.node_tree.nodes.get("Principled BSDF")
    vertex_node=grass.node_tree.nodes.get("FV Ground Color")
    if not vertex_node:
        vertex_node=grass.node_tree.nodes.new("ShaderNodeVertexColor")
        vertex_node.name="FV Ground Color"
    vertex_node.layer_name="fv_ground_color"
    grass.node_tree.links.new(vertex_node.outputs["Color"],shader.inputs["Base Color"])
    mesh.update()
    obj = bpy.data.objects.new("regional_walkable_terrain", mesh)
    collection.objects.link(obj)
    if hasattr(obj, "visible_shadow"):
        obj.visible_shadow = False
    return _tag(obj, "walkable-terrain", "Regional Terrain", "regional-terrain")


def _add_tree(collection, name, x, y, scale, trunk_mat, leaf_mat, seed):
    rng = random.Random(seed)
    trunk_boxes=[(x,y,.20,.34*scale,.34*scale,2.4*scale)]
    _batch_boxes(collection,name+"_trunk",trunk_boxes,trunk_mat,"street-tree")
    sides=8; vertices=[]; faces=[]
    # Three overlapping faceted lobes preserve the low-poly language while
    # avoiding the identical traffic-cone silhouette of the first pass.
    lobes=((0,0,1.18,2.45,4.35),(-.58,.06,.72,2.35,3.65),(.52,.18,.76,2.42,3.78))
    for lobe_index,(ox,oy,radius,z0,z1) in enumerate(lobes):
        start=len(vertices)
        rings=((radius*.52,z0),(radius,z0+(z1-z0)*.34),(radius*.72,z0+(z1-z0)*.76),(.08,z1))
        for ring_radius,z in rings:
            for i in range(sides):
                angle=math.tau*i/sides
                wobble=1+rng.uniform(-.065,.065)
                vertices.append((x+(ox+math.cos(angle)*ring_radius*wobble)*scale,
                                 y+(oy+math.sin(angle)*ring_radius*wobble)*scale,z*scale))
        for ring in range(len(rings)-1):
            for i in range(sides):
                j=(i+1)%sides;a=start+ring*sides;b=start+(ring+1)*sides
                faces.append((a+i,a+j,b+j,b+i))
    mesh=bpy.data.meshes.new(name+"_canopy_mesh");mesh.from_pydata(vertices,[],faces)
    mesh.materials.append(leaf_mat);mesh.update()
    obj=bpy.data.objects.new(name+"_canopy",mesh);collection.objects.link(obj)
    _tag(obj,"street-tree")


def _public_realm(collection, occupied, extent, block_n, lot, road, pitch):
    min_bx,max_bx,min_by,max_by=extent; block_size=block_n*lot
    sidewalk_mat=_material("FV_sidewalk_concrete",(.47,.46,.43),.98)
    furnishing_mat=_material("FV_sidewalk_furnishing_band",(.30,.30,.28),.98)
    apron_mat=_material("FV_sidewalk_building_apron",(.54,.51,.46),.97)
    curb_mat=_material("FV_curb_granite",(.35,.36,.35),.98)
    ramp_mat=_material("FV_curb_ramp",(.43,.42,.39),.98)
    tactile_mat=_material("FV_tactile_paver",(.58,.43,.16),.93)
    plaza_mat=_material("FV_plaza_pavers",(.42,.31,.24),.98)
    planter_mat=_material("FV_planter",(.20,.22,.21),.92)
    wood_mat=_material("FV_bench_wood",(.29,.15,.07),.90)
    metal_mat=_material("FV_street_metal",(.055,.07,.08),.64,.38)
    lamp_mat=_emissive_material("FV_streetlamp_glow",(.98,.72,.32),4.5)
    hydrant_mat=_material("FV_hydrant_red",(.55,.07,.045),.68,.22)
    bin_mat=_material("FV_litter_bin",(.09,.12,.11),.76,.28)
    trunk_mat=_material("FV_tree_trunk",(.25,.17,.10),1)
    leaf_mat=_material("FV_tree_leaf",(.15,.32,.17),1)
    block_paver=_material("FV_block_paver",(.34,.33,.31),.96)
    courtyard_paver=_material("FV_courtyard_paver",(.43,.40,.35),.95)
    service_mat=_material("FV_service_lane",(.235,.245,.25),.93)
    joint_mat=_material("FV_paving_joint",(.19,.19,.18),.99)
    hedge_mat=_material("FV_urban_hedge",(.12,.28,.13),1)
    soil_mat=_material("FV_planter_soil",(.13,.085,.05),1)
    crosswalk_mat=_material("FV_crosswalk",(.72,.72,.68),.94)
    bollard_mat=_material("FV_bollard",(.075,.085,.085),.58,.34)
    rack_mat=_material("FV_bike_rack",(.13,.15,.15),.50,.42)
    sign_mat=_material("FV_street_sign",(.055,.25,.17),.62,.18)
    shelter_glass=_material("FV_shelter_glass",(.08,.22,.29),.12,.10,.72,.34,.72,1.48)
    transit_mat=_material("FV_transit_marker",(.08,.28,.46),.56,.12)

    sidewalks=[];furnishing=[];aprons=[];curbs=[];ramps=[];tactile=[]
    tree_wells=[];plazas=[];planters=[];benches=[];poles=[];arms=[];lamp_heads=[]
    hydrants=[];bins=[];block_fills=[];courtyards=[];service_lanes=[]
    paving_joints=[];courtyard_planters=[];courtyard_soil=[];courtyard_hedges=[]
    crosswalks=[];bollards=[];bike_racks=[];street_signs=[];street_sign_poles=[]
    shelter_frames=[];shelter_glazing=[];shelter_roofs=[];shelter_seats=[];transit_markers=[]
    bus_stop_blocks={(-1,0),(0,-1)}
    walk=3.40; furniture_width=1.12; apron_width=.62
    for bx in range(min_bx,max_bx+1):
        for by in range(min_by,max_by+1):
            x0,y0=bx*pitch,by*pitch;cx,cy=x0+block_size/2,y0+block_size/2
            # Every downtown block gets a deliberate hardscape base. Previously
            # the regional meadow showed through between buildings and made the
            # core read as a suburban prototype instead of a finished city.
            inner=block_size-2*walk
            block_fills.append((cx,cy,.105,inner,inner,.055))
            courtyards.append((cx,cy,.162,inner*.46,inner*.46,.025))
            # A narrow service cross gives rear access and breaks the interior
            # into believable parcels without adding another vehicle street.
            service_lanes.extend(((cx,cy,.166,3.1,inner,.024),
                                  (cx,cy,.166,inner,3.1,.024)))
            for offset in (-inner*.23, inner*.23):
                paving_joints.extend(((cx+offset,cy,.188,.035,inner*.92,.012),
                                      (cx,cy+offset,.188,inner*.92,.035,.012)))

            # Designed green is kept inside raised planters rather than leaking
            # across the lot. This retains warmth while making every green patch
            # visibly intentional and maintainable.
            if (bx+by)%2:
                for sx,sy in ((-1,-1),(1,1)):
                    hx=cx+sx*inner*.29;hy=cy+sy*inner*.29
                    courtyard_planters.append((hx,hy,.19,3.2,1.35,.42))
                    courtyard_soil.append((hx,hy,.612,2.82,.98,.08))
                    courtyard_hedges.append((hx,hy,.69,2.48,.62,.62))
            sidewalks.extend(((cx,y0+walk/2,.12,block_size,walk,.16),
                              (cx,y0+block_size-walk/2,.12,block_size,walk,.16),
                              (x0+walk/2,cy,.12,walk,block_size,.16),
                              (x0+block_size-walk/2,cy,.12,walk,block_size,.16)))
            furnishing.extend(((cx,y0+furniture_width/2,.281,block_size,furniture_width,.028),
                               (cx,y0+block_size-furniture_width/2,.281,block_size,furniture_width,.028),
                               (x0+furniture_width/2,cy,.281,furniture_width,block_size,.028),
                               (x0+block_size-furniture_width/2,cy,.281,furniture_width,block_size,.028)))
            aprons.extend(((cx,y0+walk-apron_width/2,.282,block_size,apron_width,.026),
                           (cx,y0+block_size-walk+apron_width/2,.282,block_size,apron_width,.026),
                           (x0+walk-apron_width/2,cy,.282,apron_width,block_size,.026),
                           (x0+block_size-walk+apron_width/2,cy,.282,apron_width,block_size,.026)))
            curbs.extend(((cx,y0+.14,.12,block_size,.28,.26),(cx,y0+block_size-.14,.12,block_size,.28,.26),
                          (x0+.14,cy,.12,.28,block_size,.26),(x0+block_size-.14,cy,.12,.28,block_size,.26)))

            for ox,oy,sx,sy in ((1.05,1.05,1,1),(block_size-1.05,1.05,-1,1),
                                (1.05,block_size-1.05,1,-1),(block_size-1.05,block_size-1.05,-1,-1)):
                px,py=x0+ox,y0+oy
                ramps.extend(((px,py-sy*.48,.165,1.55,1.15,.09),(px-sx*.48,py,.165,1.15,1.55,.09)))
                tactile.extend(((px,py-sy*.72,.257,1.08,.42,.035),(px-sx*.72,py,.257,.42,1.08,.035)))

            # Short, low-poly zebra crossings sit only at the pedestrian desire
            # lines; unlike the rejected lane striping they clarify intersections
            # without turning every roadway into a field of white marks.
            for stripe in range(5):
                offset=(stripe-2)*.72
                crosswalks.extend(((x0+offset,y0-3.0,.173,.40,4.7,.022),
                                   (x0-3.0,y0+offset,.173,4.7,.40,.022)))

            for t in (block_size*.27,block_size*.73):
                fixtures=((x0+t,y0+.78,0,-1),(x0+t,y0+block_size-.78,0,1),
                          (x0+.78,y0+t,-1,0),(x0+block_size-.78,y0+t,1,0))
                for px,py,dx,dy in fixtures:
                    poles.append((px,py,.28,.14,.14,4.65))
                    poles.append((px,py,.20,.34,.34,.18))
                    arms.append((px+dx*.34,py+dy*.34,4.66,.82 if dx else .12,.82 if dy else .12,.12))
                    lamp_heads.append((px+dx*.72,py+dy*.72,4.55,.34,.34,.24))

            sx,sy=x0+.84,y0+.84
            street_sign_poles.append((sx,sy,.30,.11,.11,2.75))
            street_signs.extend(((sx+.45,sy,2.58,.98,.12,.28),
                                 (sx,sy+.45,2.25,.12,.98,.28)))

            tree_positions=((cx,y0+.72),(cx,y0+block_size-.72),(x0+.72,cy),(x0+block_size-.72,cy))
            for tree_index,(px,py) in enumerate(tree_positions):
                if ((bx+by+tree_index)%3 != 0
                        and not ((bx,by) in bus_stop_blocks and tree_index==0)):
                    _add_tree(collection,"street_tree_%d_%d_%d"%(bx,by,tree_index),px,py,.72,
                              trunk_mat,leaf_mat,13000+bx*127+by*59+tree_index)
                    tree_wells.append((px,py,.305,1.20,1.20,.055))

            if (bx+by)%2==0:
                bins.append((x0+block_size*.36,y0+.77,.30,.62,.62,1.12))
                benches.append((x0+block_size*.62,y0+.86,.31,2.25,.56,.55))
            if (bx-by)%3==0:
                hx,hy=x0+2.25,y0+.73
                hydrants.extend(((hx,hy,.29,.34,.34,.72),(hx,hy,.87,.54,.22,.17),(hx,hy,1.03,.42,.42,.16)))

            if (bx,by) in bus_stop_blocks:
                stop_x,stop_y=cx,y0+.72
                shelter_frames.extend(((stop_x-1.65,stop_y,.30,.10,.10,2.55),
                                       (stop_x+1.65,stop_y,.30,.10,.10,2.55),
                                       (stop_x,stop_y+.50,.30,3.40,.10,2.55)))
                shelter_glazing.extend(((stop_x,stop_y+.45,.48,3.15,.055,1.96),
                                        (stop_x-1.59,stop_y,.48,.055,.96,1.96),
                                        (stop_x+1.59,stop_y,.48,.055,.96,1.96)))
                shelter_roofs.append((stop_x,stop_y+.02,2.84,3.72,1.38,.18))
                shelter_seats.extend(((stop_x,stop_y+.18,.54,2.05,.40,.18),
                                      (stop_x,stop_y+.35,.30,2.05,.16,.54)))
                transit_markers.extend(((stop_x+2.00,stop_y,.30,.10,.10,2.80),
                                        (stop_x+2.00,stop_y,2.42,.42,.12,.52)))

    px,py=-pitch+block_size/2,-pitch+block_size/2
    plazas.append((px,py,.18,11.5,11.5,.18))
    for ox,oy in ((-4.5,-4.5),(4.5,-4.5),(-4.5,4.5),(4.5,4.5)):
        planters.append((px+ox,py+oy,.36,1.35,1.35,.72))
    benches.extend(((px,py-4.2,.37,3.5,.55,.58),(px,py+4.2,.37,3.5,.55,.58),
                    (px-4.2,py,.37,.55,3.5,.58),(px+4.2,py,.37,.55,3.5,.58)))
    for side in (-1,1):
        for index in range(4):
            bollards.append((px+side*5.1,py+(index-1.5)*1.55,.30,.18,.18,.82))
    for index in (-1,0,1):
        bike_racks.append((px-3.1+index*.72,py-5.15,.30,.12,.78,.78))
    for name,boxes,mat,role in (
        ("city_sidewalks",sidewalks,sidewalk_mat,"sidewalk"),
        ("city_block_hardscape",block_fills,block_paver,"block-hardscape"),
        ("city_courtyards",courtyards,courtyard_paver,"courtyard"),
        ("city_service_lanes",service_lanes,service_mat,"service-lane"),
        ("city_paving_joints",paving_joints,joint_mat,"paving-joint"),
        ("city_crosswalks",crosswalks,crosswalk_mat,"crosswalk"),
        ("city_furnishing_bands",furnishing,furnishing_mat,"furnishing-zone"),
        ("city_building_aprons",aprons,apron_mat,"building-apron"),
        ("city_curbs",curbs,curb_mat,"curb"),("city_curb_ramps",ramps,ramp_mat,"curb-ramp"),
        ("city_tactile_pavers",tactile,tactile_mat,"tactile-paving"),
        ("city_tree_wells",tree_wells,planter_mat,"tree-well"),
        ("city_courtyard_planters",courtyard_planters,planter_mat,"planter"),
        ("city_courtyard_soil",courtyard_soil,soil_mat,"planter-soil"),
        ("city_courtyard_hedges",courtyard_hedges,hedge_mat,"urban-hedge"),
        ("city_bollards",bollards,bollard_mat,"bollard"),
        ("city_bike_racks",bike_racks,rack_mat,"bike-rack"),
        ("city_street_sign_poles",street_sign_poles,metal_mat,"street-sign"),
        ("city_street_signs",street_signs,sign_mat,"street-sign"),
        ("city_shelter_frames",shelter_frames,metal_mat,"transit-shelter"),
        ("city_shelter_glazing",shelter_glazing,shelter_glass,"transit-shelter"),
        ("city_shelter_roofs",shelter_roofs,metal_mat,"transit-shelter"),
        ("city_shelter_seats",shelter_seats,wood_mat,"transit-shelter"),
        ("city_transit_markers",transit_markers,transit_mat,"transit-marker"),
        ("civic_square",plazas,plaza_mat,"plaza"),("city_planters",planters,planter_mat,"planter"),
        ("city_benches",benches,wood_mat,"bench"),("city_litter_bins",bins,bin_mat,"litter-bin"),
        ("city_hydrants",hydrants,hydrant_mat,"hydrant"),("city_lamp_posts",poles,metal_mat,"streetlight"),
        ("city_lamp_arms",arms,metal_mat,"streetlight"),("city_lamp_glow",lamp_heads,lamp_mat,"streetlight")):
        obj=_batch_boxes(collection,name,boxes,mat,role)
        if role in {"curb","planter","bench","litter-bin","hydrant"}:
            _bevel(obj,.055,1)


def _downtown_massing(collection, occupied, extent, block_n, lot, pitch):
    min_bx,max_bx,min_by,max_by=extent;block_size=block_n*lot
    stone=_material("FV_tower_limestone",(.54,.50,.43),.9)
    brick=_material("FV_tower_brick",(.34,.16,.11),.93)
    concrete=_material("FV_tower_concrete",(.32,.35,.36),.94)
    glass=_material("FV_tower_glass",(.075,.20,.28),.14,.18,1.0,0.0,.68,1.48)
    lit=_material("FV_window_warm",(.88,.55,.24),.34,.04,1.0,0.0,.32,1.45)
    roof=_material("FV_rooftop",(.10,.12,.13),.82,.25)
    copper=_material("FV_copper",(.28,.38,.34),.72,.38)
    frame=_material("FV_facade_frame",(.075,.09,.10),.48,.32)
    podium_glass=_material("FV_podium_glass",(.06,.16,.20),.12,.22,.76,.30,.72,1.48)
    masses={stone:[],brick:[],concrete:[],glass:[],lit:[],roof:[],copper:[],frame:[],podium_glass:[]}
    towers=0
    for bx in range(min_bx,max_bx+1):
        for by in range(min_by,max_by+1):
            center_cell=(bx*block_n+1,by*block_n+1)
            if center_cell in occupied or (bx,by)==(-1,-1):
                continue
            rng=random.Random(50000+bx*991+by*313)
            cx,cy=bx*pitch+block_size/2,by*pitch+block_size/2
            core_distance=abs(bx+.5)+abs(by+.5)
            height=max(16.0,52.0-core_distance*11+rng.uniform(-3,6))
            width=8.4+rng.uniform(-.7,1.1);depth=8.4+rng.uniform(-.7,1.1)
            facade=(stone,brick,concrete)[(bx*3+by)%3]
            masses[facade].append((cx,cy,.20,width+1.8,depth+1.8,4.2))
            setback_z=max(15.0,height*.68)
            upper_width=width*.82;upper_depth=depth*.82
            # Recess the opaque core behind the glazing. The first version put
            # transparent panes directly onto a solid wall, so transmission
            # could never read as depth in the browser.
            masses[facade].append((cx,cy,4.4,width-.56,depth-.56,setback_z-4.4))
            masses[facade].append((cx,cy,setback_z,upper_width-.48,upper_depth-.48,height-setback_z))
            # Transparent podium glazing and dark transoms make the bottom of
            # each tower read as occupied lobby/retail instead of a blank box.
            for lane in (-.29,0,.29):
                masses[podium_glass].extend(((cx+lane*width,cy-(depth+1.8)/2-.035,.68,width*.20,.09,2.55),
                                             (cx+lane*width,cy+(depth+1.8)/2+.035,.68,width*.20,.09,2.55)))
            masses[frame].extend(((cx,cy-(depth+1.8)/2-.07,3.25,width+1.25,.12,.18),
                                  (cx,cy+(depth+1.8)/2+.07,3.25,width+1.25,.12,.18)))
            # Strong masonry piers give the glass tower believable structure.
            pier=.42
            for sx in (-1,1):
                for sy in (-1,1):
                    masses[facade].append((cx+sx*(width/2-pier/2),cy+sy*(depth/2-pier/2),4.4,pier,pier,setback_z-4.4))
                    masses[facade].append((cx+sx*(upper_width/2-pier/2),cy+sy*(upper_depth/2-pier/2),setback_z,pier,pier,height-setback_z))
            floors=max(4,int((height-5)/3.05))
            for floor in range(floors):
                z=5.35+floor*3.05
                floor_width=upper_width if z>=setback_z else width
                floor_depth=upper_depth if z>=setback_z else depth
                for lane in (-.30,0,.30):
                    wx=cx+lane*floor_width
                    warm=lit if (floor+int(lane*10)+bx+by)%5==0 else glass
                    masses[warm].extend(((wx,cy-floor_depth/2-.025,z,floor_width*.20,.09,1.35),(wx,cy+floor_depth/2+.025,z,floor_width*.20,.09,1.35)))
                for lane in (-.30,0,.30):
                    wy=cy+lane*floor_depth
                    warm=lit if (floor+int(lane*10)+bx-by)%6==0 else glass
                    masses[warm].extend(((cx-floor_width/2-.025,wy,z,.09,floor_depth*.20,1.35),(cx+floor_width/2+.025,wy,z,.09,floor_depth*.20,1.35)))
                if floor and floor%3==0:
                    masses[frame].extend(((cx,cy-floor_depth/2-.07,z-.43,floor_width*.94,.12,.11),
                                          (cx,cy+floor_depth/2+.07,z-.43,floor_width*.94,.12,.11)))
            masses[roof].append((cx,cy,height,upper_width*.76,upper_depth*.76,1.0))
            masses[roof].append((cx+.8,cy-.4,height+1,2.0,1.5,1.15))
            masses[frame].extend(((cx-.85,cy+.40,height+2.15,.18,.18,2.4),
                                  (cx+.85,cy-.45,height+2.15,.18,.18,1.65)))
            if core_distance<1.2:
                masses[copper].append((cx,cy,height+2.15,.30,.30,5.2))
            towers+=1
    for material,boxes in masses.items():
        obj=_batch_boxes(collection,"downtown_"+material.name.lower(),boxes,material,"urban-building")
        if material not in {glass,lit}:
            _bevel(obj,.10,1)
    return towers


def build_downtown_visuals(collection, buildings, occupied, layout, render_mode=None):
    """Build a legible city center and one continuous walkable land surface."""
    extent=layout["block_extent"]
    _terrain_mesh(collection)
    _public_realm(collection,occupied,extent,layout["block_n"],layout["lot"],layout["road"],layout["pitch"])
    towers=_downtown_massing(collection,occupied,extent,layout["block_n"],layout["lot"],layout["pitch"])
    summary={"district":DISTRICT_NAME,"downtown_towers":towers,"walkable_terrain":1}
    print("DOWNTOWN_REDESIGN",summary)
    return summary
