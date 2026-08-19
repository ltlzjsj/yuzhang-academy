import { onBeforeUnmount, ref } from 'vue'
import { synthesize, synthesizeStream, type SynthOpts, type TtsPcmStream } from '@/api/voice'

type Playable = { kind: 'stream'; stream: TtsPcmStream } | { kind: 'blob'; blob: Blob }

// Keep browser-side speed neutral. Style/speed should come from the TTS prompt
// so every generated sentence stays consistent.
const PLAYBACK_RATE = 1
const STRONG_ENDERS = /[。！？!?\n]/
const SOFT_ENDERS = /[，,；;：:]/
const FIRST_SOFT_MIN = 18
const FIRST_HARD_MAX = 42

/**
 * Low-latency speech playback.
 *
 * Text is split into small utterances. Each utterance is requested from the
 * streaming TTS endpoint as PCM16 and scheduled into Web Audio as chunks arrive,
 * so the user hears the first sentence before the full audio file exists.
 */
export function useSpeechPlayback(getOpts?: () => SynthOpts) {
  const speaking = ref(false)
  const loading = ref(false)
  const error = ref('')
  const level = ref(0)

  let actx: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let timeData: Uint8Array | null = null
  let meterRaf = 0

  function ensureGraph() {
    if (actx) return
    const AC = (window.AudioContext || (window as any).webkitAudioContext) as typeof AudioContext | undefined
    if (!AC) return
    try {
      actx = new AC()
      analyser = actx.createAnalyser()
      analyser.fftSize = 512
      analyser.smoothingTimeConstant = 0.55
      timeData = new Uint8Array(analyser.fftSize)
      analyser.connect(actx.destination)
    } catch {
      actx = null
      analyser = null
      timeData = null
    }
  }

  function startMeter() {
    if (meterRaf) return
    const loop = () => {
      if (analyser && timeData) {
        analyser.getByteTimeDomainData(timeData)
        let sum = 0
        for (let i = 0; i < timeData.length; i++) {
          const v = (timeData[i] - 128) / 128
          sum += v * v
        }
        const rms = Math.sqrt(sum / timeData.length)
        const target = Math.min(1, rms * 3.4)
        level.value = level.value * 0.5 + target * 0.5
      }
      if (speaking.value || level.value > 0.012) {
        meterRaf = requestAnimationFrame(loop)
      } else {
        level.value = 0
        meterRaf = 0
      }
    }
    meterRaf = requestAnimationFrame(loop)
  }

  let buffer = ''
  const pending: string[] = []
  const ready: Playable[] = []
  let synthRunning = false
  let playRunning = false
  let stopped = false
  let heardFirstAudio = false
  let currentAudio: HTMLAudioElement | null = null
  let currentUrl: string | null = null
  let currentReader: ReadableStreamDefaultReader<Uint8Array> | null = null
  let activeSources: AudioBufferSourceNode[] = []
  let scheduledUntil = 0

  function splitAt(index: number) {
    const seg = buffer.slice(0, index).trim()
    buffer = buffer.slice(index)
    if (seg) pending.push(seg)
  }

  function extract(flush: boolean) {
    let idx: number
    while ((idx = buffer.search(STRONG_ENDERS)) !== -1) {
      splitAt(idx + 1)
    }

    // For the first audible response, don't wait for a full Chinese period if
    // the model is writing a long opening clause.
    if (!flush && !heardFirstAudio && !pending.length && !ready.length && !synthRunning) {
      const soft = buffer.search(SOFT_ENDERS)
      if (soft >= FIRST_SOFT_MIN) {
        splitAt(soft + 1)
      } else if (buffer.length >= FIRST_HARD_MAX) {
        splitAt(FIRST_HARD_MAX)
      }
    }

    if (flush) {
      const rest = buffer.trim()
      buffer = ''
      if (rest) pending.push(rest)
    }
  }

  function feed(delta: string) {
    if (stopped || !delta) return
    buffer += delta
    extract(false)
    pump()
  }

  function finish() {
    if (stopped) return
    extract(true)
    pump()
  }

  function speak(text: string) {
    reset()
    feed(text)
    finish()
  }

  function pump() {
    runSynth()
    runPlay()
  }

  async function runSynth() {
    if (synthRunning) return
    synthRunning = true
    if (!ready.length) loading.value = true
    while (!stopped && pending.length) {
      const seg = pending.shift()!
      try {
        const stream = await synthesizeStream(seg, getOpts?.() ?? {})
        if (stopped) {
          stream.reader.cancel().catch(() => {})
          break
        }
        ready.push({ kind: 'stream', stream })
        runPlay()
      } catch (e: any) {
        // Fallback keeps older deployments usable if the streaming endpoint is
        // unavailable, though first sound will be slower on this path.
        try {
          const blob = await synthesize(seg, getOpts?.() ?? {})
          if (!stopped) {
            ready.push({ kind: 'blob', blob })
            runPlay()
          }
        } catch (fallbackErr: any) {
          error.value = fallbackErr?.message || e?.message || '语音合成失败。'
        }
      }
    }
    synthRunning = false
    if (!pending.length) loading.value = false
    if (!ready.length && !playRunning && !synthRunning) speaking.value = false
  }

  async function runPlay() {
    if (playRunning) return
    playRunning = true
    speaking.value = true
    while (!stopped && ready.length) {
      const item = ready.shift()!
      loading.value = false
      if (item.kind === 'stream') await playPcmStream(item.stream)
      else await playBlob(item.blob)
    }
    playRunning = false
    if (!stopped && !ready.length && !pending.length && !synthRunning) speaking.value = false
  }

  function mergeCarry(carry: Uint8Array, value: Uint8Array) {
    if (!carry.length) return value
    const merged = new Uint8Array(carry.length + value.length)
    merged.set(carry)
    merged.set(value, carry.length)
    return merged
  }

  function schedulePcm(bytes: Uint8Array, sampleRate: number) {
    if (!actx || !analyser || bytes.length < 2) return
    const samples = new Float32Array(bytes.length / 2)
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    for (let i = 0; i < samples.length; i++) {
      samples[i] = view.getInt16(i * 2, true) / 32768
    }
    const audioBuffer = actx.createBuffer(1, samples.length, sampleRate)
    audioBuffer.copyToChannel(samples, 0)

    const source = actx.createBufferSource()
    source.buffer = audioBuffer
    source.playbackRate.value = PLAYBACK_RATE
    source.connect(analyser)

    const startAt = Math.max(scheduledUntil, actx.currentTime + 0.018)
    source.start(startAt)
    scheduledUntil = startAt + audioBuffer.duration / PLAYBACK_RATE
    activeSources.push(source)
    source.onended = () => {
      activeSources = activeSources.filter((s) => s !== source)
    }
  }

  async function playPcmStream(stream: TtsPcmStream) {
    ensureGraph()
    if (!actx || !analyser) {
      const blob = await collectStream(stream.reader)
      await playBlob(blob)
      return
    }
    if (actx.state === 'suspended') await actx.resume().catch(() => {})
    startMeter()
    currentReader = stream.reader
    scheduledUntil = Math.max(scheduledUntil, actx.currentTime + 0.04)
    let carry = new Uint8Array(0)

    try {
      while (!stopped) {
        const { done, value } = await stream.reader.read()
        if (done) break
        if (!value?.length) continue
        const bytes = mergeCarry(carry, value)
        const aligned = bytes.length - (bytes.length % 2)
        carry = aligned < bytes.length ? bytes.slice(aligned) : new Uint8Array(0)
        schedulePcm(bytes.slice(0, aligned), stream.sampleRate)
        heardFirstAudio = true
      }
    } finally {
      currentReader = null
    }

    if (carry.length && !stopped) schedulePcm(carry, stream.sampleRate)
    const tailMs = Math.max(0, (scheduledUntil - (actx?.currentTime ?? 0)) * 1000)
    if (tailMs > 0) await new Promise((resolve) => setTimeout(resolve, tailMs))
  }

  async function collectStream(reader: ReadableStreamDefaultReader<Uint8Array>) {
    const chunks: Uint8Array[] = []
    while (!stopped) {
      const { done, value } = await reader.read()
      if (done) break
      if (value?.length) chunks.push(value)
    }
    return new Blob(chunks, { type: 'audio/pcm' })
  }

  function playBlob(blob: Blob): Promise<void> {
    return new Promise((resolve) => {
      currentUrl = URL.createObjectURL(blob)
      currentAudio = new Audio(currentUrl)
      currentAudio.playbackRate = PLAYBACK_RATE
      currentAudio.preservesPitch = true
      heardFirstAudio = true
      const done = () => {
        if (currentUrl) {
          URL.revokeObjectURL(currentUrl)
          currentUrl = null
        }
        currentAudio = null
        resolve()
      }
      currentAudio.onended = done
      currentAudio.onerror = () => {
        error.value = '语音播放失败。'
        done()
      }
      currentAudio.play().catch(() => done())
    })
  }

  function stop() {
    stopped = true
    pending.length = 0
    ready.splice(0).forEach((item) => {
      if (item.kind === 'stream') item.stream.reader.cancel().catch(() => {})
    })
    buffer = ''
    currentReader?.cancel().catch(() => {})
    currentReader = null
    activeSources.forEach((source) => {
      try {
        source.stop()
      } catch {
        /* already stopped */
      }
    })
    activeSources = []
    scheduledUntil = 0
    if (currentAudio) {
      currentAudio.pause()
      currentAudio.src = ''
      currentAudio = null
    }
    if (currentUrl) {
      URL.revokeObjectURL(currentUrl)
      currentUrl = null
    }
    speaking.value = false
    loading.value = false
    if (meterRaf) {
      cancelAnimationFrame(meterRaf)
      meterRaf = 0
    }
    level.value = 0
  }

  function reset() {
    stop()
    stopped = false
    heardFirstAudio = false
    error.value = ''
  }

  onBeforeUnmount(stop)

  return { speaking, loading, error, level, feed, finish, speak, stop, reset }
}
