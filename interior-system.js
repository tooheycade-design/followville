import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const ASSET_ROOT = "assets/interiors/quaternius";
const ROOM = Object.freeze({ x: 10000, y: 500, z: 10000, width: 18, depth: 14, height: 4.2 });
const GRID = 0.25;
const MAX_ITEMS = 48;

export const INTERIOR_CATALOG = Object.freeze([
  { id:"couch_l", label:"Corner sofa", category:"Living", size:[3.8,1.15,2.45], footprint:[3.55,2.25] },
  { id:"couch_large", label:"Three-seat sofa", category:"Living", size:[3.35,1.15,1.15], footprint:[3.2,1.05] },
  { id:"fireplace", label:"Fireplace", category:"Living", size:[1.55,2.15,.72], footprint:[1.45,.65] },
  { id:"shelf_large", label:"Bookcase", category:"Living", size:[1.75,2.1,.52], footprint:[1.65,.48] },
  { id:"rug", label:"Area rug", category:"Living", size:[3.8,.06,2.8], footprint:[3.8,2.8], solid:false },
  { id:"light_floor", label:"Floor lamp", category:"Living", size:[.62,2.05,.62], footprint:[.5,.5] },
  { id:"table_round_large", label:"Dining table", category:"Dining", size:[2.15,.82,2.15], footprint:[2.05,2.05] },
  { id:"chair", label:"Dining chair", category:"Dining", size:[.72,1.0,.72], footprint:[.62,.62] },
  { id:"stool", label:"Counter stool", category:"Dining", size:[.58,.74,.58], footprint:[.5,.5] },
  { id:"kitchen_sink", label:"Kitchen counter", category:"Kitchen", size:[1.7,1.0,.72], footprint:[1.6,.65] },
  { id:"fridge", label:"Refrigerator", category:"Kitchen", size:[1.15,2.25,.92], footprint:[1.05,.85] },
  { id:"oven", label:"Range oven", category:"Kitchen", size:[1.05,1.05,.9], footprint:[.98,.84] },
  { id:"drawer", label:"Kitchen cabinet", category:"Kitchen", size:[1.35,.95,.64], footprint:[1.28,.58] },
  { id:"bed_king", label:"King bed", category:"Bedroom", size:[2.65,1.15,2.45], footprint:[2.55,2.35] },
  { id:"bed_single", label:"Single bed", category:"Bedroom", size:[1.25,1.05,2.25], footprint:[1.15,2.15] },
  { id:"nightstand", label:"Nightstand", category:"Bedroom", size:[.72,.72,.62], footprint:[.65,.56] },
  { id:"table_lamp", label:"Table lamp", category:"Bedroom", size:[.42,.72,.42], footprint:[.35,.35], solid:false },
  { id:"bathroom_sink", label:"Vanity", category:"Bathroom", size:[1.2,1.0,.68], footprint:[1.12,.62] },
  { id:"toilet", label:"Toilet", category:"Bathroom", size:[.78,1.0,.92], footprint:[.7,.84] },
  { id:"bathtub", label:"Bathtub", category:"Bathroom", size:[1.45,1.0,3.1], footprint:[1.35,3.0] },
  { id:"washing_machine", label:"Washer", category:"Bathroom", size:[1.05,1.18,.95], footprint:[.98,.88] },
  { id:"houseplant", label:"Houseplant", category:"Decor", size:[.85,1.45,.85], footprint:[.7,.7] },
  { id:"curtains_double", label:"Curtains", category:"Decor", size:[2.4,2.45,.35], footprint:[2.3,.25], solid:false },
  { id:"light_ceiling", label:"Ceiling light", category:"Decor", size:[.75,.42,.75], footprint:[.4,.4], solid:false, ceiling:true },
  { id:"door_double", label:"Double doors", category:"Decor", size:[2.65,2.75,.25], footprint:[2.55,.2], solid:false }
]);

const CATALOG_BY_ID = new Map(INTERIOR_CATALOG.map(item => [item.id, item]));
const CATEGORIES = ["Living", "Dining", "Kitchen", "Bedroom", "Bathroom", "Decor"];

export const DEFAULT_INTERIOR_LAYOUT = Object.freeze([
  {item:"rug",x:4.25,z:-3.55,r:0},
  {item:"couch_l",x:4.25,z:-4.7,r:0},
  {item:"fireplace",x:8.15,z:-3.25,r:3},
  {item:"shelf_large",x:1.15,z:-6.55,r:0},
  {item:"light_floor",x:7.15,z:-5.8,r:0},
  {item:"houseplant",x:7.75,z:-6.0,r:0},
  {item:"table_round_large",x:3.0,z:2.2,r:0},
  {item:"chair",x:1.65,z:2.2,r:3},
  {item:"chair",x:4.35,z:2.2,r:1},
  {item:"chair",x:3.0,z:.85,r:0},
  {item:"chair",x:3.0,z:3.55,r:2},
  {item:"kitchen_sink",x:8.5,z:4.65,r:1},
  {item:"drawer",x:8.5,z:3.1,r:1},
  {item:"oven",x:8.5,z:1.75,r:1},
  {item:"fridge",x:8.5,z:.25,r:1},
  {item:"stool",x:5.0,z:5.25,r:0},
  {item:"stool",x:3.9,z:5.25,r:0},
  {item:"bed_king",x:-5.55,z:-4.45,r:0},
  {item:"nightstand",x:-7.25,z:-5.75,r:0},
  {item:"nightstand",x:-3.85,z:-5.75,r:0},
  {item:"table_lamp",x:-7.25,z:-5.75,r:0},
  {item:"table_lamp",x:-3.85,z:-5.75,r:0},
  {item:"shelf_large",x:-7.85,z:-1.1,r:3},
  {item:"bathtub",x:-8.1,z:3.25,r:0},
  {item:"toilet",x:-7.35,z:6.5,r:2},
  {item:"bathroom_sink",x:-5.45,z:6.5,r:2},
  {item:"washing_machine",x:-3.9,z:6.5,r:2},
  {item:"houseplant",x:-2.25,z:5.75,r:0},
  {item:"curtains_double",x:5.8,z:6.3,r:0},
  {item:"curtains_double",x:-5.8,z:6.3,r:0},
  {item:"light_ceiling",x:4.5,z:-3.5,r:0},
  {item:"light_ceiling",x:3.5,z:3.5,r:0},
  {item:"light_ceiling",x:-5.5,z:-3.5,r:0},
  {item:"light_ceiling",x:-5.5,z:4.3,r:0}
]);

function snap(value){ return Math.round(Number(value) / GRID) * GRID; }
function cloneLayout(layout){ return layout.map(item => ({item:item.item,x:item.x,z:item.z,r:item.r})); }

export function normalizeInteriorLayout(value){
  if (!Array.isArray(value)) return null;
  const out=[];
  for (const raw of value.slice(0,MAX_ITEMS)){
    if (!raw || typeof raw!=="object" || !CATALOG_BY_ID.has(raw.item)) continue;
    const x=snap(raw.x),z=snap(raw.z),r=Math.trunc(Number(raw.r));
    if (!Number.isFinite(x)||!Number.isFinite(z)||!Number.isFinite(r)) continue;
    if (Math.abs(x)>8.55||Math.abs(z)>6.55||r<0||r>3) continue;
    out.push({item:raw.item,x,z,r});
  }
  return out;
}

function createWoodTexture(){
  const canvas=document.createElement("canvas");canvas.width=512;canvas.height=512;
  const ctx=canvas.getContext("2d");ctx.fillStyle="#9a6a42";ctx.fillRect(0,0,512,512);
  for(let row=0;row<8;row++){
    const y=row*64;ctx.fillStyle=row%2?"rgba(255,234,196,.055)":"rgba(60,24,8,.04)";ctx.fillRect(0,y,512,62);
    ctx.strokeStyle="rgba(61,32,17,.24)";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(512,y);ctx.stroke();
    for(let x=(row%2)*96-96;x<512;x+=192){ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x,y+64);ctx.stroke();}
    ctx.strokeStyle="rgba(255,255,255,.045)";ctx.lineWidth=1;
    for(let k=0;k<4;k++){const gy=y+13+k*11;ctx.beginPath();ctx.moveTo(0,gy);ctx.bezierCurveTo(140,gy+4,330,gy-5,512,gy+1);ctx.stroke();}
  }
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
  texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(2.25,1.75);texture.anisotropy=4;
  return texture;
}

function box(group,name,size,position,material){
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),material);mesh.name=name;mesh.position.set(...position);
  mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);return mesh;
}

function makeCollider(x,z,w,d,r=0,label="interior"){
  const angle=-r*Math.PI/2,ux=Math.cos(angle),uz=Math.sin(angle),vx=-uz,vz=ux;
  return {kind:"box",x:ROOM.x+x,z:ROOM.z+z,ux,uz,vx,vz,hx:w/2,hz:d/2,label};
}

export function createInteriorSystem({scene,renderer,camera,getPlayerPosition,resolveCollision,showToast,saveLayout}){
  const group=new THREE.Group();group.name="followville-interior";group.position.set(ROOM.x,ROOM.y,ROOM.z);scene.add(group);
  const shell=new THREE.Group();shell.name="interior-architecture";group.add(shell);
  const furnishings=new THREE.Group();furnishings.name="interior-furnishings";group.add(furnishings);
  const loader=new GLTFLoader(),templates=new Map(),loads=new Map();
  const colliders=[];let records=cloneLayout(DEFAULT_INTERIOR_LAYOUT);let savedRecords=cloneLayout(records);
  let itemRoots=[],active=false,editable=false,building=false,saving=false,category="Living",selected=-1;
  let placementId=null,placementGhost=null,placementRecord=null,history=[];let currentHouseId=null;

  const floorMat=new THREE.MeshStandardMaterial({color:0xffffff,map:createWoodTexture(),roughness:.62,metalness:0});
  const wallMat=new THREE.MeshStandardMaterial({color:0xf2eadc,roughness:.88});
  const accentWallMat=new THREE.MeshStandardMaterial({color:0xcbd4ca,roughness:.88});
  const trimMat=new THREE.MeshStandardMaterial({color:0xf8f3e8,roughness:.72});
  const ceilingMat=new THREE.MeshStandardMaterial({color:0xfffbf2,roughness:.9});
  const glassMat=new THREE.MeshPhysicalMaterial({color:0xbad8e4,transparent:true,opacity:.34,roughness:.18,metalness:0,depthWrite:false});
  const metalMat=new THREE.MeshStandardMaterial({color:0x3a4248,roughness:.34,metalness:.55});
  const doorMat=new THREE.MeshStandardMaterial({color:0x31516a,roughness:.58});
  const hardwareMat=new THREE.MeshStandardMaterial({color:0xc3a45d,roughness:.28,metalness:.7});

  function buildShell(){
    box(shell,"interior-floor",[ROOM.width,.16,ROOM.depth],[0,-.08,0],floorMat);
    box(shell,"interior-ceiling",[ROOM.width,.16,ROOM.depth],[0,ROOM.height+.08,0],ceilingMat);
    box(shell,"interior-back-wall",[ROOM.width,ROOM.height,.18],[0,ROOM.height/2,-ROOM.depth/2],accentWallMat);
    box(shell,"interior-left-wall",[.18,ROOM.height,ROOM.depth],[-ROOM.width/2,ROOM.height/2,0],wallMat);
    box(shell,"interior-right-wall",[.18,ROOM.height,ROOM.depth],[ROOM.width/2,ROOM.height/2,0],wallMat);
    box(shell,"interior-front-left",[7.55,ROOM.height,.18],[-5.23,ROOM.height/2,ROOM.depth/2],wallMat);
    box(shell,"interior-front-right",[7.55,ROOM.height,.18],[5.23,ROOM.height/2,ROOM.depth/2],wallMat);
    box(shell,"interior-front-header",[2.9,1.35,.18],[0,3.525,ROOM.depth/2],wallMat);
    // Bedroom divider with a broad cased opening.
    box(shell,"interior-bedroom-divider-a",[.16,ROOM.height,5.15],[-1.55,ROOM.height/2,-4.425],wallMat);
    box(shell,"interior-bedroom-divider-b",[.16,ROOM.height,.95],[-1.55,ROOM.height/2,.525],wallMat);
    box(shell,"interior-bedroom-divider-head",[.16,1.35,1.9],[-1.55,3.525,-1.0],wallMat);
    // Bathroom enclosure; two pieces leave a real doorway at the hall.
    box(shell,"interior-bath-wall-a",[4.15,ROOM.height,.16],[-6.925,ROOM.height/2,1.35],wallMat);
    box(shell,"interior-bath-wall-b",[1.2,ROOM.height,.16],[-2.15,ROOM.height/2,1.35],wallMat);
    box(shell,"interior-bath-wall-head",[1.55,1.35,.16],[-3.525,3.525,1.35],wallMat);

    for(const [name,w,d,x,z] of [
      ["back",17.7,.08,0,-6.86],["left",.08,13.7,-8.86,0],["right",.08,13.7,8.86,0],
      ["front-left",7.45,.08,-5.25,6.86],["front-right",7.45,.08,5.25,6.86]
    ]) box(shell,`interior-baseboard-${name}`,[w,.18,d],[x,.09,z],trimMat);
    box(shell,"interior-door-top-trim",[3.05,.16,.22],[0,2.86,6.87],trimMat);
    box(shell,"interior-door-left-trim",[.16,2.8,.22],[-1.45,1.4,6.87],trimMat);
    box(shell,"interior-door-right-trim",[.16,2.8,.22],[1.45,1.4,6.87],trimMat);
    for(const x of [-.66,.66]){
      box(shell,"interior-door-leaf",[1.26,2.7,.12],[x,1.35,6.84],doorMat);
      for(const y of [.7,1.55,2.3])box(shell,"interior-door-panel",[.92,.58,.055],[x,y,6.765],trimMat);
    }
    box(shell,"interior-door-handle-left",[.08,.28,.12],[-.12,1.18,6.72],hardwareMat);
    box(shell,"interior-door-handle-right",[.08,.28,.12],[.12,1.18,6.72],hardwareMat);

    // Two inset windows with deep frames. Their planes are separated from the wall.
    for(const x of [-5.85,5.85]){
      box(shell,"interior-window-reveal",[2.65,2.35,.16],[x,2.15,6.88],metalMat);
      box(shell,"interior-window-glass",[2.38,2.08,.035],[x,2.15,6.77],glassMat);
      box(shell,"interior-window-mullion-v",[.07,2.08,.055],[x,2.15,6.74],trimMat);
      box(shell,"interior-window-mullion-h",[2.38,.07,.055],[x,2.15,6.74],trimMat);
    }

    const ambient=new THREE.HemisphereLight(0xfff5e6,0x384454,1.18);ambient.position.set(0,4,0);shell.add(ambient);
    for(const [x,z,intensity] of [[4.4,-3.4,5.0],[3.6,3.6,4.2],[-5.5,-3.7,4.1],[-5.5,4.2,3.8],[0,5.3,3.0]]){
      const light=new THREE.PointLight(0xffd9ad,intensity,9,1.6);light.position.set(x,3.65,z);light.castShadow=false;shell.add(light);
    }

    colliders.push(
      makeCollider(0,-6.92,18,.16),makeCollider(-8.92,0,.16,14),makeCollider(8.92,0,.16,14),
      makeCollider(-5.23,6.92,7.55,.16),makeCollider(5.23,6.92,7.55,.16),
      makeCollider(-1.55,-4.425,.16,5.15),makeCollider(-1.55,.525,.16,.95),
      makeCollider(-6.925,1.35,4.15,.16),makeCollider(-2.15,1.35,1.2,.16),makeCollider(0,6.84,2.65,.18)
    );
  }
  buildShell();

  function themeFor(building){
    const type=building?.type||"house",seed=Math.abs(Number(building?.seed||0));
    if(["mushroomhouse","flowerhouse","cottagehouse"].includes(type))return {wall:0xf4ead8,accent:0xd5c9b7,floor:0xa87549};
    if(["castlehouse","eiffelhouse","burjhouse","casinohouse"].includes(type))return {wall:0xf0eee9,accent:0xd6dce1,floor:0x8c6748};
    const themes=[
      {wall:0xf2eadc,accent:0xcbd4ca,floor:0x9a6a42},{wall:0xeee9df,accent:0xc8d0d7,floor:0x815a3b},
      {wall:0xf1e8dc,accent:0xd8c8bd,floor:0x9a704d},{wall:0xeee9df,accent:0xc9c3b4,floor:0x755037}
    ];return themes[seed%themes.length];
  }

  function applyTheme(building){const theme=themeFor(building);wallMat.color.setHex(theme.wall);accentWallMat.color.setHex(theme.accent);floorMat.color.setHex(theme.floor);}

  async function loadTemplate(id){
    if(templates.has(id))return templates.get(id);if(loads.has(id))return loads.get(id);
    const def=CATALOG_BY_ID.get(id);if(!def)throw new Error(`unknown interior item ${id}`);
    const promise=loader.loadAsync(`${ASSET_ROOT}/${id}.glb`).then(gltf=>{
      const root=gltf.scene;root.updateMatrixWorld(true);const bounds=new THREE.Box3().setFromObject(root);
      const size=bounds.getSize(new THREE.Vector3());const scale=Math.min(def.size[0]/Math.max(size.x,.001),def.size[1]/Math.max(size.y,.001),def.size[2]/Math.max(size.z,.001));
      root.scale.setScalar(scale);root.updateMatrixWorld(true);const scaled=new THREE.Box3().setFromObject(root);const center=scaled.getCenter(new THREE.Vector3());
      root.position.x-=center.x;root.position.z-=center.z;root.position.y-=scaled.min.y;
      root.traverse(obj=>{if(!obj.isMesh)return;obj.castShadow=true;obj.receiveShadow=true;const mats=Array.isArray(obj.material)?obj.material:[obj.material];for(const mat of mats){if(mat){mat.roughness=Math.max(.45,mat.roughness??.7);mat.metalness=Math.min(.45,mat.metalness??0);}}});
      const template=new THREE.Group();template.name=`template-${id}`;template.add(root);templates.set(id,template);loads.delete(id);return template;
    });loads.set(id,promise);return promise;
  }

  function disposeRoot(root){root.traverse(obj=>{const mats=Array.isArray(obj.material)?obj.material:[obj.material];for(const mat of mats){if(mat?.userData?.interiorInstance)mat.dispose();}});}
  function clearFurnishings(){for(const root of itemRoots){furnishings.remove(root);disposeRoot(root);}itemRoots=[];furnishings.clear();}

  async function makeItem(record,index,{ghost=false}={}){
    const def=CATALOG_BY_ID.get(record.item),template=await loadTemplate(record.item),root=template.clone(true);root.name=`interior-item-${record.item}`;
    root.position.set(record.x,def.ceiling?ROOM.height-def.size[1]-.08:0,record.z);root.rotation.y=-record.r*Math.PI/2;
    root.userData.interiorIndex=index;root.traverse(obj=>{obj.userData.interiorIndex=index;if(obj.isMesh){obj.material=Array.isArray(obj.material)?obj.material.map(mat=>mat.clone()):obj.material.clone();const mats=Array.isArray(obj.material)?obj.material:[obj.material];for(const mat of mats){mat.userData.interiorInstance=true;if(ghost){mat.transparent=true;mat.opacity=.55;mat.depthWrite=false;mat.userData.interiorGhost=true;}}}});
    return root;
  }

  async function renderLayout(next=records){
    clearFurnishings();records=cloneLayout(next);const roots=await Promise.all(records.map((record,index)=>makeItem(record,index)));
    for(const root of roots){furnishings.add(root);itemRoots.push(root);}
    document.body.dataset.interiorItems=String(records.length);document.body.dataset.interiorLoaded="true";
    updateSelection();
  }

  // Furniture remains selectable and overlap-checked in build mode, but it is
  // intentionally non-blocking during play. Only walls and closed doors keep
  // the player/camera inside the room.
  function currentColliders(){return active?colliders:[];}
  function resolvePlayer(position){for(const collider of currentColliders())resolveCollision(position,collider);}
  function cameraColliders(){return currentColliders();}

  const style=document.createElement("style");style.textContent=`
    #interiorBuildToggle{position:fixed;right:20px;bottom:84px;z-index:12;display:none;min-height:46px;padding:0 22px;border:1px solid rgba(255,255,255,.55);border-radius:4px;background:#1c2b45;color:#fff;font:700 13px Georgia,serif;box-shadow:0 12px 32px rgba(8,19,34,.28)}
    #interiorBuildToggle:hover{background:#263957}#interiorBuildToggle.visible{display:block}
    #interiorBuildPanel{position:fixed;z-index:30;right:16px;top:16px;bottom:16px;width:min(390px,calc(100vw - 32px));display:none;grid-template-rows:auto auto 1fr auto;background:#fbf8f1;color:#1c2b45;border:1px solid rgba(28,43,69,.2);box-shadow:0 24px 70px rgba(6,17,31,.38);font-family:Arial,sans-serif}
    #interiorBuildPanel.open{display:grid}.ib-head{padding:22px 22px 17px;border-bottom:1px solid #d8d2c6}.ib-kicker{color:#bf5a42;font-size:10px;font-weight:800;letter-spacing:.14em;text-transform:uppercase}.ib-head h2{margin:5px 0 5px;font:700 25px/1.1 Georgia,serif}.ib-head p{margin:0;color:#70767b;font-size:11px;line-height:1.45}
    .ib-tabs{display:flex;gap:0;overflow:auto;padding:0 14px;border-bottom:1px solid #ddd7cb}.ib-tabs button{flex:0 0 auto;padding:14px 10px 12px;border:0;border-bottom:2px solid transparent;background:none;color:#69727d;font-size:10px;font-weight:800}.ib-tabs button.active{color:#b64f3b;border-color:#c25a43}
    .ib-catalog{overflow:auto;padding:15px;display:grid;grid-template-columns:repeat(3,1fr);align-content:start;gap:10px}.ib-item{position:relative;padding:0 0 9px;border:1px solid #d8d2c6;background:#fffdf8;color:#1c2b45;text-align:left}.ib-item:hover{border-color:#7f8b94}.ib-item img{display:block;width:100%;aspect-ratio:1/1;object-fit:cover;background:#e3e3df}.ib-item span{display:block;padding:8px 8px 0;font-size:10px;font-weight:800;line-height:1.2}
    .ib-actions{padding:14px;border-top:1px solid #d8d2c6;background:#f6f1e8}.ib-toolrow,.ib-saverow{display:grid;gap:8px}.ib-toolrow{grid-template-columns:repeat(4,1fr);margin-bottom:9px}.ib-saverow{grid-template-columns:1fr 1.4fr}.ib-actions button{min-height:40px;border:1px solid #c9c4ba;background:#fffdf8;color:#26364c;font-weight:800;font-size:10px}.ib-actions button:hover{border-color:#6c7884}.ib-actions button:disabled{opacity:.4}.ib-actions .primary{background:#1c2b45;color:#fff;border-color:#1c2b45}.ib-status{min-height:17px;margin:0 0 9px;color:#6d747a;font-size:10px}.ib-status strong{color:#b64f3b}
    body.interior-build-mode #hint,body.interior-build-mode #houseEnterPrompt,body.interior-build-mode #joystickZone,body.interior-build-mode #runBtn,body.interior-build-mode #jumpBtn{display:none!important}
    @media(max-width:760px){#interiorBuildToggle{right:12px;bottom:76px}.ib-catalog{grid-template-columns:repeat(4,1fr)}#interiorBuildPanel{inset:8px;width:auto}.ib-head{padding:14px 16px 11px}.ib-head h2{font-size:20px}.ib-catalog{padding:10px;gap:7px}.ib-item span{font-size:9px}.ib-actions{padding:10px}}
    @media(max-height:600px) and (min-width:761px){#interiorBuildPanel{inset:6px 6px 6px auto;width:370px}.ib-head{padding:10px 14px 8px}.ib-head h2{margin:2px 0;font-size:19px}.ib-head p{display:none}.ib-tabs button{padding:9px 8px 7px}.ib-catalog{padding:8px;gap:7px}.ib-item span{padding-top:5px;font-size:9px}.ib-actions{padding:8px}.ib-actions button{min-height:34px}.ib-status{margin-bottom:5px}}
  `;document.head.appendChild(style);
  const toggle=document.createElement("button");toggle.id="interiorBuildToggle";toggle.type="button";toggle.textContent="Furnish my home";document.body.appendChild(toggle);
  const panel=document.createElement("aside");panel.id="interiorBuildPanel";panel.setAttribute("aria-label","Interior furnishing mode");document.body.appendChild(panel);

  function renderPanel(){
    panel.innerHTML=`<header class="ib-head"><div class="ib-kicker">Homeowner build mode</div><h2>Furnish your home</h2><p>Choose an item, move it across the floor, and click to place. Rotate in quarter turns. Your saved layout appears for every visitor.</p></header>
      <nav class="ib-tabs">${CATEGORIES.map(name=>`<button type="button" data-category="${name}" class="${name===category?"active":""}">${name}</button>`).join("")}</nav>
      <div class="ib-catalog">${INTERIOR_CATALOG.filter(item=>item.category===category).map(item=>`<button type="button" class="ib-item" data-item="${item.id}"><img src="${ASSET_ROOT}/${item.id}.webp" alt="" loading="lazy"><span>${item.label}</span></button>`).join("")}</div>
      <footer class="ib-actions"><div class="ib-status">${placementId?`Placing <strong>${CATALOG_BY_ID.get(placementId).label}</strong>`:selected>=0?`Selected <strong>${CATALOG_BY_ID.get(records[selected]?.item)?.label||"item"}</strong>`:`${records.length}/${MAX_ITEMS} items`}</div>
      <div class="ib-toolrow"><button type="button" data-action="rotate" ${placementId||selected>=0?"":"disabled"}>Rotate</button><button type="button" data-action="delete" ${selected>=0?"":"disabled"}>Delete</button><button type="button" data-action="undo" ${history.length?"":"disabled"}>Undo</button><button type="button" data-action="reset">Default</button></div>
      <div class="ib-saverow"><button type="button" data-action="cancel" ${saving?"disabled":""}>Cancel</button><button type="button" class="primary" data-action="save" ${saving?"disabled":""}>${saving?"Saving…":"Save interior"}</button></div></footer>`;
    panel.querySelectorAll("[data-category]").forEach(btn=>btn.onclick=()=>{category=btn.dataset.category;renderPanel();});
    panel.querySelectorAll("[data-item]").forEach(btn=>btn.onclick=()=>beginPlacement(btn.dataset.item));
    panel.querySelector('[data-action="rotate"]').onclick=rotateSelection;
    panel.querySelector('[data-action="delete"]').onclick=deleteSelection;
    panel.querySelector('[data-action="undo"]').onclick=undo;
    panel.querySelector('[data-action="reset"]').onclick=resetDefault;
    panel.querySelector('[data-action="cancel"]').onclick=cancelBuild;
    panel.querySelector('[data-action="save"]').onclick=saveBuild;
  }

  function pushHistory(){history.push(cloneLayout(records));if(history.length>30)history.shift();}
  function updateSelection(){itemRoots.forEach((root,index)=>root.traverse(obj=>{if(obj.isMesh&&!obj.material?.userData?.interiorGhost){if(!obj.userData.baseEmissive)obj.userData.baseEmissive=obj.material.emissive?.getHex?.()||0;if(obj.material.emissive)obj.material.emissive.setHex(index===selected?0x253b52:obj.userData.baseEmissive);}}));}
  async function beginPlacement(id){
    if(records.length>=MAX_ITEMS){showToast(`Homes can hold up to ${MAX_ITEMS} items.`);return;}
    placementId=id;selected=-1;placementRecord={item:id,x:0,z:0,r:0};if(placementGhost){group.remove(placementGhost);disposeRoot(placementGhost);}
    placementGhost=await makeItem(placementRecord,-1,{ghost:true});group.add(placementGhost);renderPanel();
  }
  function rotateSelection(){
    if(placementRecord){placementRecord.r=(placementRecord.r+1)%4;if(placementGhost)placementGhost.rotation.y=-placementRecord.r*Math.PI/2;}
    else if(selected>=0&&records[selected]){pushHistory();records[selected].r=(records[selected].r+1)%4;renderLayout(records);}
    renderPanel();
  }
  function deleteSelection(){if(selected<0)return;pushHistory();records.splice(selected,1);selected=-1;renderLayout(records);renderPanel();}
  function undo(){if(!history.length)return;records=history.pop();selected=-1;renderLayout(records);renderPanel();}
  function resetDefault(){pushHistory();records=cloneLayout(DEFAULT_INTERIOR_LAYOUT);selected=-1;renderLayout(records);renderPanel();}
  function cancelPlacement(){placementId=null;placementRecord=null;if(placementGhost){group.remove(placementGhost);disposeRoot(placementGhost);placementGhost=null;}}

  const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2(),floorPlane=new THREE.Plane(new THREE.Vector3(0,1,0),-ROOM.y),hitPoint=new THREE.Vector3();
  function pointerFloor(event){const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-((event.clientY-rect.top)/rect.height)*2+1);raycaster.setFromCamera(pointer,camera);return raycaster.ray.intersectPlane(floorPlane,hitPoint)?hitPoint:null;}
  function placementValid(record){
    const def=CATALOG_BY_ID.get(record.item),w=record.r%2?def.footprint[1]:def.footprint[0],d=record.r%2?def.footprint[0]:def.footprint[1];
    if(Math.abs(record.x)+w/2>8.84||Math.abs(record.z)+d/2>6.84)return false;
    if(def.solid===false)return true;
    return !records.some(other=>{const otherDef=CATALOG_BY_ID.get(other.item);if(otherDef.solid===false)return false;const ow=other.r%2?otherDef.footprint[1]:otherDef.footprint[0],od=other.r%2?otherDef.footprint[0]:otherDef.footprint[1];return Math.abs(record.x-other.x)<(w+ow)/2+.06&&Math.abs(record.z-other.z)<(d+od)/2+.06;});
  }
  function onPointerMove(event){if(!building||!placementRecord)return;const point=pointerFloor(event);if(!point)return;placementRecord.x=snap(point.x-ROOM.x);placementRecord.z=snap(point.z-ROOM.z);placementGhost.position.x=placementRecord.x;placementGhost.position.z=placementRecord.z;const valid=placementValid(placementRecord);placementGhost.traverse(obj=>{if(obj.isMesh){const mats=Array.isArray(obj.material)?obj.material:[obj.material];for(const mat of mats)mat.opacity=valid ? .58 : .24;}});}
  async function onPointerDown(event){
    if(!building||event.button!==0||panel.contains(event.target)||toggle.contains(event.target))return;
    if(placementRecord){if(!placementValid(placementRecord)){showToast("That item needs to stay inside the room.");return;}pushHistory();records.push({...placementRecord});cancelPlacement();await renderLayout(records);selected=records.length-1;renderPanel();return;}
    const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-((event.clientY-rect.top)/rect.height)*2+1);raycaster.setFromCamera(pointer,camera);
    const hit=raycaster.intersectObjects(itemRoots,true).find(entry=>Number.isInteger(entry.object.userData.interiorIndex));selected=hit?hit.object.userData.interiorIndex:-1;updateSelection();renderPanel();
  }
  const placementSurfaces=[renderer.domElement,document.getElementById("lookZone")].filter(Boolean);
  for(const surface of placementSurfaces){surface.addEventListener("pointermove",onPointerMove);surface.addEventListener("pointerdown",onPointerDown);}
  window.addEventListener("keydown",event=>{if(!building)return;if(event.key.toLowerCase()==="r"){event.preventDefault();rotateSelection();}else if(event.key==="Delete"||event.key==="Backspace"){event.preventDefault();deleteSelection();}else if(event.key==="Escape"){event.preventDefault();placementId?cancelPlacement():cancelBuild();renderPanel();}});

  async function startBuild(){if(!active||!editable)return;building=true;savedRecords=cloneLayout(records);history=[];selected=-1;document.body.classList.add("interior-build-mode");document.body.dataset.interiorBuildMode="true";panel.classList.add("open");toggle.classList.remove("visible");renderPanel();}
  function finishBuild(){building=false;saving=false;selected=-1;cancelPlacement();history=[];document.body.classList.remove("interior-build-mode");delete document.body.dataset.interiorBuildMode;panel.classList.remove("open");if(active&&editable)toggle.classList.add("visible");updateSelection();}
  async function cancelBuild(){records=cloneLayout(savedRecords);await renderLayout(records);finishBuild();showToast("Interior changes discarded.");}
  async function saveBuild(){if(saving)return;saving=true;renderPanel();try{await saveLayout(currentHouseId,cloneLayout(records));savedRecords=cloneLayout(records);finishBuild();showToast("Interior saved — visitors will see it too.");}catch(error){saving=false;renderPanel();showToast(error?.message||"Couldn't save the interior yet.");}}
  toggle.onclick=startBuild;

  async function enter({building:buildingData,houseId,layout,isOwner}){
    active=true;editable=Boolean(isOwner);currentHouseId=Number(houseId);group.visible=true;applyTheme(buildingData);document.body.dataset.interiorLoaded="loading";
    const normalized=normalizeInteriorLayout(layout);records=cloneLayout(normalized===null?DEFAULT_INTERIOR_LAYOUT:normalized);savedRecords=cloneLayout(records);
    await renderLayout(records);toggle.classList.toggle("visible",editable);return true;
  }
  function exit(){active=false;editable=false;currentHouseId=null;finishBuild();toggle.classList.remove("visible");group.visible=false;delete document.body.dataset.interiorLoaded;delete document.body.dataset.interiorItems;}
  async function refresh(layout){if(!active||building)return;const normalized=normalizeInteriorLayout(layout);await renderLayout(normalized===null?DEFAULT_INTERIOR_LAYOUT:normalized);savedRecords=cloneLayout(records);}
  function isBuildMode(){return building;}

  group.visible=false;
  return {group,enter,exit,refresh,resolvePlayer,cameraColliders,isBuildMode,getLayout:()=>cloneLayout(records)};
}
