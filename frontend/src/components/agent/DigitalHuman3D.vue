<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

// 共享一个支持 Draco / Meshopt 压缩的加载器，兼容市面上各种压缩过的 GLB。
let dracoLoader: DRACOLoader | null = null
function makeLoader() {
  const loader = new GLTFLoader()
  if (!dracoLoader) {
    dracoLoader = new DRACOLoader()
    dracoLoader.setDecoderPath('/draco/gltf/') // 解码器随站点托管，避免外网 CDN
  }
  loader.setDRACOLoader(dracoLoader)
  loader.setMeshoptDecoder(MeshoptDecoder)
  return loader
}

/**
 * 浏览器内 3D 数字人。
 * - 身体动作：加载与骨架兼容的「待机 / 说话」骨骼动画(Ready Player Me 动画库)，
 *   平时播待机，`speaking` 时交叉淡入随机一段说话手势(随讲话进行而动)。
 * - 口型：用外部 `level`(0..1，TTS 音量)驱动 jawOpen/mouthOpen，叠加在动画之上。
 * - 眨眼 + 面部由 blendshape；摄像机自动取景到面部，OrbitControls 可拖动。
 * - `src` 不存在时回退 `fallbackSrc`，便于按先贤 id 放置各自模型。
 */
const props = withDefaults(
  defineProps<{ level?: number; speaking?: boolean; src?: string; fallbackSrc?: string }>(),
  { level: 0, speaking: false, src: '/models/avatar.glb', fallbackSrc: '/models/avatar.glb' },
)

const IDLE_URL = '/models/anim/idle.glb'
const TALK_URLS = ['/models/anim/talking-1.glb', '/models/anim/talking-2.glb', '/models/anim/talking-3.glb']

const wrap = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const loaded = ref(false)
const failed = ref(false)

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let controls: OrbitControls | null = null
let model: THREE.Object3D | null = null
let ro: ResizeObserver | null = null
const clock = new THREE.Clock()

// 骨骼动画
let mixer: THREE.AnimationMixer | null = null
let idleAction: THREE.AnimationAction | null = null
const talkActions: THREE.AnimationAction[] = []
let activeTalkAction: THREE.AnimationAction | null = null
let talkWeight = 0
let nextTalkGestureIn = 0

const EMBEDDED_TALK_WEIGHT = 0.62
const EMBEDDED_TALK_TIME_SCALE = 0.72
const EXTERNAL_TALK_WEIGHT = 0.72
const EXTERNAL_TALK_TIME_SCALE = 0.82
let talkTargetWeight = EXTERNAL_TALK_WEIGHT
let talkTimeScale = EXTERNAL_TALK_TIME_SCALE

const morphs = new Map<string, { mesh: THREE.Mesh; idx: number }[]>()
function setMorph(name: string, v: number) {
  const list = morphs.get(name)
  if (!list) return
  for (const { mesh, idx } of list) {
    const inf = mesh.morphTargetInfluences
    if (inf) inf[idx] = v
  }
}

// 自动识别口型/眨眼/眉毛 morph（兼容 ARKit / VRM / 中文等不同命名），
// 没有口型 morph 时退而驱动下巴骨。命名按常见度排序，取首个命中的。
const MOUTH_CANDIDATES = ['jawOpen', 'mouthOpen', 'viseme_aa', 'vrc.v_aa', 'aa', 'A', 'Fcl_MTH_A', 'mouth_open']
const BLINK_CANDIDATES = ['eyeBlinkLeft', 'eyeBlinkRight', 'eyesClosed', 'blink', 'Blink', 'vrc.blink_left', 'vrc.blink_right', 'Fcl_EYE_Close']
const BROW_CANDIDATES = ['browInnerUp', 'browInnerUp_L', 'BrowsU_C']
const JAW_BONE_CANDIDATES = ['jaw', 'Jaw', 'CC_Base_JawRoot', 'LowerJaw', 'mixamorigJaw']
const HEAD_BONE_CANDIDATES = ['CC_Base_Head', 'Head', 'head', 'mixamorigHead', 'J_Bip_C_Head']

let mouthMorph: string | null = null
let mouthOpenSecondary = false
let blinkMorphs: string[] = []
let browMorph: string | null = null
let jawBone: THREE.Object3D | null = null
let jawBoneBaseX = 0
// 既没有口型 morph、下巴骨也带不动脸时(头部被刚性绑定)，退到头部微动，
// 免得讲话时整个人像尊雕像。
let headBone: THREE.Object3D | null = null
let headBaseRot: THREE.Euler | null = null
let headT = 0

let jaw = 0
let nextBlink = 1.6
let blinkT = -1

function resize() {
  if (!wrap.value || !renderer || !camera) return
  const w = wrap.value.clientWidth || 1
  const h = wrap.value.clientHeight || 1
  renderer.setSize(w, h, false)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

function frameFace() {
  if (!model) return
  const box = new THREE.Box3().setFromObject(model)
  const size = new THREE.Vector3()
  box.getSize(size)
  const H = size.y || 1.6
  const cx = (box.min.x + box.max.x) / 2
  const cz = (box.min.z + box.max.z) / 2
  const faceY = box.max.y - H * 0.1
  const target = new THREE.Vector3(cx, faceY, cz)
  const visibleH = H * 0.3
  const fov = (camera.fov * Math.PI) / 180
  const dist = visibleH / 2 / Math.tan(fov / 2)
  camera.position.set(cx, faceY + H * 0.015, cz + dist * 1.05)
  camera.lookAt(target)
  if (controls) {
    controls.target.copy(target)
    controls.minDistance = dist * 0.5
    controls.maxDistance = dist * 4.6
    controls.update()
  }
}

function applySpeaking(on: boolean) {
  if (!mixer) return
  if (on) nextTalkGestureIn = 0
}

function pickTalkAction() {
  if (!talkActions.length) return
  const pool = activeTalkAction && talkActions.length > 1
    ? talkActions.filter((a) => a !== activeTalkAction)
    : talkActions
  const action = pool[Math.floor(Math.random() * pool.length)]
  if (activeTalkAction && activeTalkAction !== action) {
    activeTalkAction.setEffectiveWeight(0)
    activeTalkAction.stop()
  }
  activeTalkAction = action
  action.reset()
  action.enabled = true
  action.setEffectiveTimeScale(talkTimeScale + Math.random() * 0.08)
  action.setEffectiveWeight(talkWeight)
  action.play()
}

function loadClipInto(url: string, onClip: (clip: THREE.AnimationClip) => void) {
  makeLoader().load(url, (g) => {
    if (g.animations?.[0]) onClip(g.animations[0])
  })
}

function setupAnimations() {
  if (!model) return
  talkTargetWeight = EXTERNAL_TALK_WEIGHT
  talkTimeScale = EXTERNAL_TALK_TIME_SCALE
  mixer = new THREE.AnimationMixer(model)
  loadClipInto(IDLE_URL, (clip) => {
    if (!mixer) return
    idleAction = mixer.clipAction(clip)
    idleAction.setLoop(THREE.LoopRepeat, Infinity)
    idleAction.setEffectiveWeight(1)
    idleAction.play()
  })
  for (const u of TALK_URLS) {
    loadClipInto(u, (clip) => {
      if (!mixer) return
      const a = mixer.clipAction(clip)
      a.setLoop(THREE.LoopRepeat, Infinity)
      a.setEffectiveTimeScale(talkTimeScale)
      a.setEffectiveWeight(0)
      a.enabled = false
      talkActions.push(a)
      if (props.speaking) applySpeaking(true)
    })
  }
}

// 用模型自带的动画片段：按名字挑「待机」与「说话/手势」，挑不出就拿第一段当待机。
function setupEmbeddedAnimations(clips: THREE.AnimationClip[]) {
  if (!model) return
  talkTargetWeight = EMBEDDED_TALK_WEIGHT
  talkTimeScale = EMBEDDED_TALK_TIME_SCALE
  mixer = new THREE.AnimationMixer(model)
  const has = (c: THREE.AnimationClip, kws: string[]) => kws.some((k) => c.name.toLowerCase().includes(k))
  const idleClip = clips.find((c) => has(c, ['idle', 'breath', 'stand', 'rest', 'loop'])) ?? clips[0]
  const talkClips = clips.filter((c) => c !== idleClip && has(c, ['talk', 'speak', 'gesture', 'wave', 'hello', 'greet']))
  idleAction = mixer.clipAction(idleClip)
  idleAction.setLoop(THREE.LoopRepeat, Infinity)
  idleAction.setEffectiveWeight(1)
  idleAction.play()
  for (const c of talkClips) {
    const a = mixer.clipAction(c)
    a.setLoop(THREE.LoopRepeat, Infinity)
    a.setEffectiveTimeScale(talkTimeScale)
    a.setEffectiveWeight(0)
    a.enabled = false
    talkActions.push(a)
  }
  if (props.speaking) applySpeaking(true)
}

// 骨架里有这根骨头 ≠ 它能带动顶点。朱熹模型就带着整套 CC_Base_Jaw/Teeth/Tongue
// 骨骼，但蒙皮权重全为 0，转它不会有任何视觉变化。
function boneAffectsSkin(bone: THREE.Object3D): boolean {
  let affects = false
  model?.traverse((o: THREE.Object3D) => {
    if (affects) return
    const sm = o as THREE.SkinnedMesh
    if (!(sm as any).isSkinnedMesh || !sm.skeleton) return
    const bi = sm.skeleton.bones.indexOf(bone as THREE.Bone)
    if (bi < 0) return
    const idx = sm.geometry.getAttribute('skinIndex')
    const wgt = sm.geometry.getAttribute('skinWeight')
    if (!idx || !wgt) return
    for (let i = 0; i < idx.count; i++) {
      for (let k = 0; k < 4; k++) {
        if (idx.getComponent(i, k) === bi && wgt.getComponent(i, k) > 1e-4) {
          affects = true
          return
        }
      }
    }
  })
  return affects
}

function onLoaded(gltf: { scene: THREE.Object3D; animations?: THREE.AnimationClip[] }) {
  model = gltf.scene
  morphs.clear()
  jawBone = null
  headBone = null
  headBaseRot = null
  model.traverse((o: THREE.Object3D) => {
    if (!jawBone && JAW_BONE_CANDIDATES.includes(o.name)) {
      jawBone = o
      jawBoneBaseX = o.rotation.x
    }
    if (!headBone && HEAD_BONE_CANDIDATES.includes(o.name)) headBone = o
    const mesh = o as THREE.Mesh
    if ((mesh as any).isMesh && mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
      for (const [name, idx] of Object.entries(mesh.morphTargetDictionary)) {
        const arr = morphs.get(name) ?? []
        arr.push({ mesh, idx: idx as number })
        morphs.set(name, arr)
      }
      mesh.frustumCulled = false
    }
  })

  // 自动挑口型/眨眼/眉毛通道
  mouthMorph = MOUTH_CANDIDATES.find((n) => morphs.has(n)) ?? null
  mouthOpenSecondary = morphs.has('mouthOpen') && mouthMorph !== 'mouthOpen'
  blinkMorphs = BLINK_CANDIDATES.filter((n) => morphs.has(n))
  browMorph = BROW_CANDIDATES.find((n) => morphs.has(n)) ?? null
  if (jawBone && !boneAffectsSkin(jawBone)) jawBone = null
  // 口型完全无解时才启用头部微动兜底
  if (!mouthMorph && !jawBone && headBone) headBaseRot = (headBone as THREE.Object3D).rotation.clone()

  scene.add(model)
  frameFace()
  resize()
  // 模型自带动画 → 优先用它自己的；没有才回退到内置 RPM 待机/说话动画。
  if (gltf.animations && gltf.animations.length) setupEmbeddedAnimations(gltf.animations)
  else setupAnimations()
  loaded.value = true
}

function loadModel(url: string, allowFallback: boolean) {
  makeLoader().load(url, onLoaded, undefined, () => {
    if (allowFallback && url !== props.fallbackSrc) loadModel(props.fallbackSrc, false)
    else failed.value = true
  })
}

function init() {
  if (!canvas.value) return
  renderer = new THREE.WebGLRenderer({ canvas: canvas.value, alpha: true, antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(22, 1, 0.1, 100)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enablePan = false
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.rotateSpeed = 0.5
  controls.minPolarAngle = Math.PI * 0.28
  controls.maxPolarAngle = Math.PI * 0.6

  scene.add(new THREE.HemisphereLight(0xffffff, 0x33384a, 2.1))
  const key = new THREE.DirectionalLight(0xfff3e0, 2.3)
  key.position.set(0.6, 1.8, 1.4)
  scene.add(key)
  const rim = new THREE.DirectionalLight(0x9ec0ff, 0.9)
  rim.position.set(-1, 1.2, -0.9)
  scene.add(rim)

  loadModel(props.src, true)

  ro = new ResizeObserver(resize)
  ro.observe(wrap.value!)
  renderer.setAnimationLoop(tick)
}

function tick() {
  if (!renderer) return
  const dt = clock.getDelta()

  // 待机是主体；说话时叠加中等幅度手势，让讲解状态更明显。
  if (props.speaking && talkActions.length) {
    nextTalkGestureIn -= dt
    if (!activeTalkAction || nextTalkGestureIn <= 0) {
      pickTalkAction()
      nextTalkGestureIn = 2.2 + Math.random() * 1.8
    }
    talkWeight += (talkTargetWeight - talkWeight) * Math.min(1, dt * 4.2)
  } else {
    talkWeight += (0 - talkWeight) * Math.min(1, dt * 4.5)
  }
  if (activeTalkAction) {
    activeTalkAction.setEffectiveWeight(talkWeight)
    if (talkWeight < 0.01 && !props.speaking) {
      activeTalkAction.stop()
      activeTalkAction.enabled = false
      activeTalkAction = null
    }
  }

  // 身体骨骼动画
  mixer?.update(dt)

  // 口型：自动识别的 morph 跟随音量并平滑（叠加在动画之上）；没有 morph 则驱动下巴骨
  const target = Math.min(1, Math.max(0, props.level)) * 0.84
  jaw += (target - jaw) * Math.min(1, dt * 18)
  if (mouthMorph) {
    setMorph(mouthMorph, jaw)
    if (mouthOpenSecondary) setMorph('mouthOpen', jaw * 0.46)
  } else if (jawBone) {
    jawBone.rotation.x = jawBoneBaseX + jaw * 0.38
  } else if (headBone && headBaseRot) {
    // 没有任何嘴部通道：用音量驱动的轻微点头/摆头顶一下，只求「在讲话」而非假口型
    headT += dt * (1.6 + jaw * 2.4)
    headBone.rotation.x = headBaseRot.x + Math.sin(headT * 1.7) * 0.035 * jaw + jaw * 0.02
    headBone.rotation.y = headBaseRot.y + Math.sin(headT * 0.9) * 0.05 * jaw
    headBone.rotation.z = headBaseRot.z + Math.sin(headT * 1.3) * 0.025 * jaw
  }
  if (browMorph) setMorph(browMorph, jaw * 0.08)

  // 眨眼（驱动所有识别到的眨眼通道）
  if (blinkMorphs.length) {
    if (blinkT < 0) {
      nextBlink -= dt
      if (nextBlink <= 0) blinkT = 0
    } else {
      blinkT += dt
      const b = blinkT < 0.16 ? Math.sin((blinkT / 0.16) * Math.PI) : 0
      for (const n of blinkMorphs) setMorph(n, b)
      if (blinkT > 0.18) {
        blinkT = -1
        nextBlink = 2 + Math.random() * 3
      }
    }
  }

  controls?.update()
  renderer.render(scene, camera)
}

watch(() => props.speaking, (v) => applySpeaking(v))

onMounted(init)
onBeforeUnmount(() => {
  renderer?.setAnimationLoop(null)
  mixer?.stopAllAction()
  ro?.disconnect()
  controls?.dispose()
  renderer?.dispose()
  renderer = null
})
</script>

<template>
  <div ref="wrap" class="dh">
    <canvas ref="canvas" class="dh__cv" />
    <div v-if="!loaded && !failed" class="dh__hint">数字人加载中…</div>
    <div v-if="failed" class="dh__hint">数字人加载失败</div>
  </div>
</template>

<style scoped>
.dh { position: relative; width: 100%; height: 100%; min-height: 0; }
.dh__cv { width: 100%; height: 100%; display: block; cursor: grab; }
.dh__cv:active { cursor: grabbing; }
.dh__hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
}
</style>
