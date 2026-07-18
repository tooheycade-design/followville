import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import * as SkeletonUtils from "three/addons/utils/SkeletonUtils.js";

/*
 * Followville Avatar System v1
 *
 * Saved profiles contain stable catalog IDs only. The visible character is a
 * modular, rigged GLB assembled from a shared core plus the selected modeled
 * hair, outfit, and hat. The default initial payload is about 0.5 MB.
 */

export const AVATAR_VERSION = 1;

export const AVATAR_CATALOG = Object.freeze({
  skin: Object.freeze([
    { id:"porcelain", label:"Porcelain", swatch:0xffede4, tint:0xffeee9 },
    { id:"fair", label:"Fair", swatch:0xf8d6c2, tint:0xfff3eb },
    { id:"peach", label:"Peach", swatch:0xeebc9e, tint:0xffffff },
    { id:"warm", label:"Warm", swatch:0xe8aa80, tint:0xffdbc3 },
    { id:"honey", label:"Honey", swatch:0xdba476, tint:0xe8b990 },
    { id:"amber", label:"Amber", swatch:0xc88961, tint:0xc88d6f },
    { id:"bronze", label:"Bronze", swatch:0xa96d4d, tint:0x9f6b58 },
    { id:"cocoa", label:"Cocoa", swatch:0x845039, tint:0x795146 },
    { id:"deep", label:"Deep", swatch:0x673d2e, tint:0x573d37 },
    { id:"espresso", label:"Espresso", swatch:0x4b2c23, tint:0x3c2d2a }
  ]),
  height: Object.freeze([
    { id:"kid", label:"Kid", note:"younger proportions", scale:.72, headScale:1.22, target:"about 4′5″" },
    { id:"tween", label:"Tween", note:"growing", scale:.82, headScale:1.14, target:"about 4′11″" },
    { id:"teen", label:"Teen", note:"medium", scale:.92, headScale:1.07, target:"about 5′5″" },
    { id:"adult", label:"Adult", note:"standard", scale:1.00, headScale:1.00, target:"about 5′9″" },
    { id:"tall", label:"Tall", note:"tall adult", scale:1.08, headScale:.98, target:"about 6′1″" }
  ]),
  face: Object.freeze([
    { id:"classic", label:"Classic", width:1.00, height:1.00, note:"balanced features" },
    { id:"round", label:"Round", width:1.08, height:.96, note:"fuller cheeks" },
    { id:"oval", label:"Oval", width:.98, height:1.06, note:"longer profile" },
    { id:"narrow", label:"Narrow", width:.92, height:1.03, note:"slender profile" },
    { id:"heart", label:"Heart", width:1.04, height:1.02, note:"tapered silhouette" },
    { id:"square", label:"Square", width:1.07, height:1.01, note:"broader silhouette" },
    { id:"soft", label:"Soft", width:1.04, height:.98, note:"gentle profile" },
    { id:"defined", label:"Defined", width:.96, height:1.02, note:"sharper profile" }
  ]),
  hair: Object.freeze([
    { id:"none", label:"No hair" },
    { id:"close_crop", label:"Buzz cut" },
    { id:"tousled", label:"Short crop" },
    { id:"swept", label:"Simple part" },
    { id:"afro", label:"Double buns" },
    { id:"long", label:"Long layers" }
  ]),
  outfit: Object.freeze([
    { id:"tailored", label:"Village blue", tint:[.78,1.04,1.30], top:0x557a8b, bottom:0x8b5f42, accent:0xd9c4a0, note:"village collection" },
    { id:"striped", label:"Village moss", tint:[.88,1.04,.78], top:0x55704b, bottom:0x8a6b3d, accent:0xd8c28d, note:"village collection" },
    { id:"tee", label:"Village cedar", tint:[1.18,.70,.52], top:0xa76548, bottom:0x695d4b, accent:0xe0ca9c, note:"village collection" },
    { id:"field_jacket", label:"Ranger woodland", tint:[1,1,1], top:0x59634a, bottom:0x4b443a, accent:0x8f6a44, note:"ranger collection" },
    { id:"weekend", label:"Ranger linen", tint:[1,1,1], top:0x8a6b4d, bottom:0x5b4439, accent:0xc5a16f, note:"ranger collection" },
    { id:"active", label:"Ranger twilight", tint:[.68,.82,1.24], top:0x465773, bottom:0x343b49, accent:0x7186a2, note:"ranger collection" }
  ]),
  hat: Object.freeze([
    { id:"none", label:"No hat" },
    { id:"ranger_hood", label:"Ranger hood" }
  ]),
  look: Object.freeze([
    { id:"custom", label:"Build my own", group:"Custom", note:"use every tailor control" },
    { id:"casual_day_f", label:"Easy day I", group:"Everyday" },
    { id:"casual_day_m", label:"Easy day II", group:"Everyday" },
    { id:"casual_sky_f", label:"Sky casual I", group:"Everyday" },
    { id:"casual_sky_m", label:"Sky casual II", group:"Everyday" },
    { id:"casual_lilac_f", label:"Lilac casual I", group:"Everyday" },
    { id:"casual_lilac_m", label:"Lilac casual II", group:"Everyday" },
    { id:"casual_bald", label:"Clean casual", group:"Everyday" },
    { id:"suit_f", label:"Town suit I", group:"Town roles" },
    { id:"suit_m", label:"Town suit II", group:"Town roles" },
    { id:"classy_f", label:"Classic formal I", group:"Town roles" },
    { id:"classy_m", label:"Classic formal II", group:"Town roles" },
    { id:"chef_f", label:"Chef I", group:"Town roles" },
    { id:"chef_m", label:"Chef II", group:"Town roles" },
    { id:"doctor_young_f", label:"Doctor I", group:"Town roles" },
    { id:"doctor_young_m", label:"Doctor II", group:"Town roles" },
    { id:"doctor_senior_f", label:"Senior doctor I", group:"Town roles" },
    { id:"doctor_senior_m", label:"Senior doctor II", group:"Town roles" },
    { id:"worker_f", label:"Builder I", group:"Town roles" },
    { id:"worker_m", label:"Builder II", group:"Town roles" },
    { id:"cowboy_f", label:"Rancher I", group:"Town roles" },
    { id:"cowboy_m", label:"Rancher II", group:"Town roles" },
    { id:"kimono_f", label:"Festival I", group:"Town roles" },
    { id:"kimono_m", label:"Festival II", group:"Town roles" },
    { id:"pirate_f", label:"Pirate I", group:"Adventure" },
    { id:"pirate_m", label:"Pirate II", group:"Adventure" },
    { id:"viking_f", label:"Viking I", group:"Adventure" },
    { id:"viking_m", label:"Viking II", group:"Adventure" },
    { id:"ninja_f", label:"Night ninja I", group:"Adventure" },
    { id:"ninja_m", label:"Night ninja II", group:"Adventure" },
    { id:"sand_ninja_f", label:"Sand ninja I", group:"Adventure" },
    { id:"sand_ninja_m", label:"Sand ninja II", group:"Adventure" },
    { id:"gold_knight_f", label:"Golden knight I", group:"Adventure" },
    { id:"gold_knight_m", label:"Golden knight II", group:"Adventure" },
    { id:"knight_m", label:"Steel knight", group:"Adventure" },
    { id:"elf", label:"Woodland elf", group:"Adventure" },
    { id:"witch", label:"Town witch", group:"Adventure" },
    { id:"wizard", label:"Town wizard", group:"Adventure" }
  ])
});

export const DEFAULT_AVATAR = Object.freeze({
  version:AVATAR_VERSION,
  skin:"peach",
  height:"adult",
  face:"classic",
  hair:"swept",
  outfit:"tailored",
  hat:"none",
  look:"custom"
});

const catalogMaps = Object.fromEntries(Object.entries(AVATAR_CATALOG)
  .map(([key, values]) => [key, new Map(values.map(value => [value.id, value]))]));

export function normalizeAvatarConfig(value){
  const input = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const normalized = { version:AVATAR_VERSION };
  for (const key of ["skin","height","face","hair","outfit","hat","look"]){
    const selected = typeof input[key] === "string" ? input[key] : DEFAULT_AVATAR[key];
    normalized[key] = catalogMaps[key].has(selected) ? selected : DEFAULT_AVATAR[key];
  }
  return normalized;
}

export function avatarConfigKey(value){
  const config = normalizeAvatarConfig(value);
  return `${config.version}:${config.skin}:${config.height}:${config.face}:${config.hair}:${config.outfit}:${config.hat}:${config.look}`;
}

export function avatarChoice(kind, id){
  return catalogMaps[kind]?.get(id) || catalogMaps[kind]?.get(DEFAULT_AVATAR[kind]) || null;
}

const ASSET_ROOT = new URL("./avatar_assets/avatar_v1/", import.meta.url);
const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath("https://unpkg.com/three@0.160.0/examples/jsm/libs/draco/gltf/");
const gltfLoader = new GLTFLoader();
gltfLoader.setDRACOLoader(dracoLoader);
const assetPromises = new Map();

function assetUrl(relative){ return new URL(relative, ASSET_ROOT).href; }

function loadAsset(relative){
  if (!assetPromises.has(relative)){
    assetPromises.set(relative, gltfLoader.loadAsync(assetUrl(relative)).catch(error => {
      assetPromises.delete(relative);
      throw error;
    }));
  }
  return assetPromises.get(relative);
}

function componentPath(kind, id){
  if (kind === "look" && id !== "custom") return `look/${id}.glb`;
  if (kind === "hair" && id !== "none") return `hair/${id}.glb`;
  if (kind === "outfit") return `outfit/${id}.glb`;
  if (kind === "hat" && id !== "none") return `hat/${id}.glb`;
  return null;
}

export function preloadAvatarAssets(value=DEFAULT_AVATAR){
  const config = normalizeAvatarConfig(value);
  const paths = config.look === "custom"
    ? ["core.glb", componentPath("hair",config.hair), componentPath("outfit",config.outfit), componentPath("hat",config.hat)]
    : [componentPath("look",config.look)];
  return Promise.all(paths.filter(Boolean).map(loadAsset));
}

function cloneAsset(gltf){
  const scene = SkeletonUtils.clone(gltf.scene);
  scene.position.set(0,0,0);
  scene.rotation.set(0,0,0);
  scene.scale.set(1,1,1);
  return scene;
}

function collectRig(scene){
  const bones = new Map();
  scene.traverse(object => {
    if (object.isBone) bones.set(object.name, object);
  });
  const base = new Map();
  for (const [name,bone] of bones) base.set(name, {
    quaternion:bone.quaternion.clone(),
    position:bone.position.clone(),
    scale:bone.scale.clone()
  });
  return { scene,bones,base };
}

function configureMeshes(scene, materials){
  scene.traverse(object => {
    if (!object.isMesh) return;
    object.castShadow = true;
    object.receiveShadow = true;
    object.frustumCulled = true;
    const sourceMaterials = (Array.isArray(object.material) ? object.material : [object.material]).filter(Boolean);
    const clones = sourceMaterials.map(material => material.clone());
    object.material = Array.isArray(object.material) ? clones : clones[0];
    for (const material of clones){
      if (material.name.includes("FV_MAT_HAIR")) material.color.setHex(0x4b2d23);
      material.needsUpdate = true;
      materials.add(material);
    }
  });
}

function applySkinAndFace(root, config, materials){
  const body = root.getObjectByName("FV_BODY") || root.getObjectByName("Body");
  const bodyMeshes = [];
  root.traverse(object => {
    if (object.isMesh) bodyMeshes.push(object);
  });
  if (!bodyMeshes.length) throw new Error("Followville avatar body has no skinned meshes");
  const skin = avatarChoice("skin",config.skin);
  const outfit = avatarChoice("outfit",config.outfit);
  const morph = avatarChoice("face",config.face).morph;
  for (const mesh of bodyMeshes){
    const bodyMaterials = (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).filter(Boolean);
    for (const material of bodyMaterials){
      if (material.name.includes("FV_MAT_SKIN") && !material.name.includes("HIDDEN")){
        material.color.setHex(skin.tint ?? 0xffffff);
        material.needsUpdate = true;
      }
      if (material.name.includes("FV_MAT_OUTFIT")){
        material.color.setRGB(...(outfit?.tint ?? [1,1,1]));
        material.needsUpdate = true;
      }
      materials.add(material);
    }
    if (mesh.morphTargetInfluences && mesh.morphTargetDictionary){
      mesh.morphTargetInfluences.fill(0);
      const index = morph ? mesh.morphTargetDictionary[morph] : undefined;
      if (Number.isInteger(index)) mesh.morphTargetInfluences[index] = 1;
    }
  }
  return body || bodyMeshes[0];
}

function applyHeadScale(rigs, scale, face){
  for (const rig of rigs){
    const head = rig.bones.get("Head") || rig.bones.get("head");
    const base = rig.base.get(head?.name);
    if (head && base) head.scale.set(
      base.scale.x*scale*(face?.width ?? 1),
      base.scale.y*scale,
      base.scale.z*scale*(face?.height ?? 1)
    );
  }
}

const BONE_ALIASES = Object.freeze({
  upperarm_l:["upperarm_l","UpperArm.L"],lowerarm_l:["lowerarm_l","LowerArm.L"],
  upperarm_r:["upperarm_r","UpperArm.R"],lowerarm_r:["lowerarm_r","LowerArm.R"],
  thigh_l:["thigh_l","UpperLeg.L"],thigh_r:["thigh_r","UpperLeg.R"],
  calf_l:["calf_l","LowerLeg.L"],calf_r:["calf_r","LowerLeg.R"],
  spine_02:["spine_02","Torso"],head:["head","Head"]
});
function resolvedBoneName(rig,name){
  return (BONE_ALIASES[name] || [name]).find(candidate=>rig.bones.has(candidate)) || name;
}
function pointBoneAt(rig, boneName, childName, targetDirection){
  const resolvedBone=resolvedBoneName(rig,boneName),resolvedChild=resolvedBoneName(rig,childName);
  const bone=rig.bones.get(resolvedBone),child=rig.bones.get(resolvedChild);
  if(!bone||!child||!bone.parent)return;
  rig.scene.updateMatrixWorld(true);
  const start=new THREE.Vector3(),end=new THREE.Vector3();
  bone.getWorldPosition(start);
  child.getWorldPosition(end);
  const current=end.sub(start).normalize();
  const target=targetDirection.clone().normalize();
  const delta=new THREE.Quaternion().setFromUnitVectors(current,target);
  const worldRotation=new THREE.Quaternion();
  const parentRotation=new THREE.Quaternion();
  bone.getWorldQuaternion(worldRotation);
  bone.parent.getWorldQuaternion(parentRotation);
  worldRotation.premultiply(delta);
  bone.quaternion.copy(parentRotation.invert().multiply(worldRotation));
  const base=rig.base.get(resolvedBone);
  if(base)base.quaternion.copy(bone.quaternion);
  rig.scene.updateMatrixWorld(true);
}

function applyTailorPose(rigs){
  for(const rig of rigs){
    pointBoneAt(rig,"upperarm_l","lowerarm_l",new THREE.Vector3(.11,-1,.02));
    pointBoneAt(rig,"upperarm_r","lowerarm_r",new THREE.Vector3(-.11,-1,.02));
  }
}

export async function createAvatarModel(value, options={}){
  const config = normalizeAvatarConfig(value);
  const requests = (config.look === "custom" ? [
      ["core","core.glb"],
      ["hair",componentPath("hair",config.hair)],
      ["outfit",componentPath("outfit",config.outfit)],
      ["hat",componentPath("hat",config.hat)]
    ] : [["look",componentPath("look",config.look)]])
    .filter(([,path]) => path);
  const loaded = await Promise.all(requests.map(async ([kind,path]) => [kind,cloneAsset(await loadAsset(path))]));

  const group = new THREE.Group();
  group.name = options.name || "FV_avatar";
  const visualRoot = new THREE.Group();
  visualRoot.name = "FV_avatar_visual";
  const assetRoot = new THREE.Group();
  assetRoot.name = "FV_avatar_assets";
  // Quaternius authors characters facing the opposite direction from the
  // existing Followville walker convention. The newer modular set needs the
  // half-turn; the complete-look library already faces Followville's camera.
  assetRoot.rotation.y = config.look === "custom" ? Math.PI : 0;
  visualRoot.add(assetRoot);
  group.add(visualRoot);
  const materials = new Set();
  const rigs = [];
  let body = null;
  for (const [kind,scene] of loaded){
    configureMeshes(scene,materials);
    assetRoot.add(scene);
    rigs.push(collectRig(scene));
  }
  body = applySkinAndFace(assetRoot,config,materials);

  if(config.look !== "custom"){
    // The older complete characters use a larger authoring scale. Derive the
    // conversion from their actual geometry so every one of the 37 looks
    // stands at the same 1.82 m baseline and rests exactly on the floor.
    assetRoot.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(assetRoot);
    const size = bounds.getSize(new THREE.Vector3());
    const unitScale = size.y > .001 ? 1.82 / size.y : .575;
    assetRoot.scale.setScalar(unitScale);
    assetRoot.position.y = -bounds.min.y * unitScale;
    assetRoot.updateMatrixWorld(true);
  }

  const height = avatarChoice("height",config.height);
  const face = avatarChoice("face",config.face);
  group.scale.setScalar(height.scale);
  if(config.look === "custom") applyTailorPose(rigs);
  applyHeadScale(rigs,height.headScale,face);
  group.userData.avatar = {
    config,
    key:avatarConfigKey(config),
    body,
    rigs,
    materials,
    visualRoot,
    phase:Math.random()*Math.PI*2,
    height:1.82*height.scale,
    eyeHeight:1.68*height.scale,
    labelHeight:2.04*height.scale,
    colliderRadius:.42*height.scale,
    ready:true
  };
  return group;
}

const AXIS_X = new THREE.Vector3(1,0,0);
const AXIS_Y = new THREE.Vector3(0,1,0);
const AXIS_Z = new THREE.Vector3(0,0,1);
const offsetQuaternion = new THREE.Quaternion();
const targetQuaternion = new THREE.Quaternion();

function poseBone(rig, name, axis, angle, blend){
  const resolved = resolvedBoneName(rig,name);
  const bone = rig.bones.get(resolved);
  const base = rig.base.get(resolved);
  if (!bone || !base) return;
  offsetQuaternion.setFromAxisAngle(axis,angle);
  targetQuaternion.copy(base.quaternion).multiply(offsetQuaternion);
  bone.quaternion.slerp(targetQuaternion,blend);
}

export function updateAvatarMotion(group, { dt=0, speed=0, running=false }={}){
  const avatar = group?.userData?.avatar;
  if (!avatar?.ready) return;
  const moving = speed > .03;
  const strideRate = running ? 10.2 : 7.3;
  if (moving) avatar.phase += dt*strideRate*Math.min(1.3,.56+speed*.105);
  const phase = avatar.phase;
  const blend = Math.min(1,dt*11);
  const stride = moving ? Math.sin(phase)*(running?.62:.44) : 0;
  const kneeLeft = moving ? Math.max(0,-Math.sin(phase))*(running?.58:.38) : 0;
  const kneeRight = moving ? Math.max(0,Math.sin(phase))*(running?.58:.38) : 0;
  const arm = -stride*(running?.82:.70);
  const idle = performance.now()*.0014 + phase*.08;

  for (const rig of avatar.rigs){
    poseBone(rig,"thigh_l",AXIS_X,stride,blend);
    poseBone(rig,"thigh_r",AXIS_X,-stride,blend);
    poseBone(rig,"calf_l",AXIS_X,kneeLeft,blend);
    poseBone(rig,"calf_r",AXIS_X,kneeRight,blend);
    poseBone(rig,"upperarm_l",AXIS_X,arm,blend);
    poseBone(rig,"upperarm_r",AXIS_X,-arm,blend);
    poseBone(rig,"lowerarm_l",AXIS_X,moving?.08:.025,blend);
    poseBone(rig,"lowerarm_r",AXIS_X,moving?.08:.025,blend);
    poseBone(rig,"spine_02",AXIS_Z,moving?Math.sin(phase)*.025:Math.sin(idle)*.008,blend);
    poseBone(rig,"head",AXIS_Y,moving?0:Math.sin(idle*.72)*.035,blend);
  }
  const bob = moving ? Math.abs(Math.sin(phase*2))*(running?.035:.022) : Math.sin(idle)*.0045;
  avatar.visualRoot.position.y = THREE.MathUtils.lerp(avatar.visualRoot.position.y,bob,blend);
}

export function disposeAvatarModel(group){
  if (!group) return;
  const materials = group.userData?.avatar?.materials;
  if (materials) for (const material of materials) material.dispose?.();
  group.removeFromParent();
}
