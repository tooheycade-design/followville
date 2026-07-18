# Followville local quality campaign

This is a local experimental critique log. It does not change canon, claims, addresses, population, or `world_state.json`.

## Loop 1 — Urban ground

- City designer: exposed meadow between downtown buildings made the core feel unfinished.
- City planner: paving must preserve clear walking and service access.
- Customer experience: entrances need a continuous, legible approach.
- CEO: fix the ground hierarchy before spending geometry on decoration.
- Built: block hardscape, courtyards, service crosses, paving joints, and contained planting.

## Loop 2 — Architectural hierarchy

- City designer: towers were repeated straight extrusions.
- City planner: a credible center needs podium, shaft, crown, and height hierarchy.
- Customer experience: tower bases need to read as occupied places.
- CEO: stronger massing provides more value than more disconnected props.
- Built: setbacks, transparent podium glazing, façade frames, transoms, and roof silhouettes.

## Loop 3 — Human-scale sightlines

- City designer: the original audit camera hid the street behind a wall and lamp.
- City planner: intersections needed pedestrian cues rather than lane clutter.
- Customer experience: walking views must stay readable and unobstructed.
- CEO: visual QA is invalid when the camera is badly placed.
- Built: corrected road-level camera, crosswalks, bollards, racks, and civic-square protection.

## Loop 4 — Operational street life

- City designer: empty carriageways made the center feel staged.
- City planner: curb activity must stay clear of ramps and intersections.
- Customer experience: vehicles and signs provide intuitive scale and orientation.
- CEO: repeatable batched assets keep the added life economical.
- Built: parking bays, restrained parked cars, tires, glazing, and street-sign hardware.

## Loop 5 — Regional ground

- City designer: one flat green material weakened aerial depth.
- City planner: terrain variation must remain continuous and not fake contour zoning.
- Customer experience: hills should read before the player reaches them.
- CEO: vertex color adds detail without texture downloads.
- Built: smooth terrain vertex-color variation tied to broad, fine, and elevation signals.

## Loop 6 — Glass and finish

- City designer: windows read as painted blue rectangles.
- City planner: transparent surfaces need restraint to avoid visual noise.
- Customer experience: reflections, interior tint, and highlight response make façades feel inhabited.
- CEO: one shared physical-glass system improves the entire world.
- Built: transmissive, clear-coated glass for downtown, suburbs, feature homes, vehicles, water, and shelters.

## Loop 7 — Roofscape

- City designer: repeated blank rooftops weakened the skyline.
- City planner: mechanical and energy elements should be organized, not random clutter.
- Customer experience: aerial exploration should reveal authored details.
- CEO: roof variety raises perceived quality across many camera angles.
- Built: solar arrays, vents, tanks, penthouses, antenna forms, and projecting business signs.

## Loop 8 — Transit and usability

- City designer: decorated streets still lacked evidence of civic use.
- City planner: shelters require protected curb space and conflict removal.
- Customer experience: seating and route markers make the city feel navigable.
- CEO: two strong transit moments are better than dozens of weak props.
- Built: two glass shelters, seats, roofs, markers, and explicit tree/parking clearance.

## Loop 9 — Website material response

- City designer: glass needs a believable sky and ground to reflect.
- City planner: browser effects must respect performance modes.
- Customer experience: web visuals must match the quality promised by Blender stills.
- CEO: generated environment lighting adds no network asset weight.
- Built: procedural equirectangular reflection environment and tuned glass response.

## Loop 10 — Final integration

- City designer: Chrome exposed road shadow banding that Blender stills did not.
- City planner: whole-world shadow coverage wastes resolution as districts expand.
- Customer experience: the player needs crisp, stable local shadows and glass with visible depth.
- CEO: a moving local shadow budget scales better than increasing the global shadow map indefinitely.
- Built: player-focused 250 m shadow region, corrected bias, ground self-shadow suppression, road-center spawn, recessed tower cores, and final multi-angle/invariant QA.
