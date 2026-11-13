// 生成角色包音效（原创、程序合成）
// 用法：node tools/make-sfx.mjs
// 输出：assets/packs/luffy/sfx/*.wav（44.1kHz / 16bit / 单声道）
//
// 为什么自己合成：仓库的 assets/** 是 as-is 提供的，不授予再许可；
// 随包分发的音频要能自证来源。合成波形没有采样来源问题，改参数就能重制，单文件 < 45KB。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SR = 44100
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function buf(sec) { return new Float32Array(Math.max(1, Math.round(SR * sec))) }

function lowpass(arr, cutoff) {
  const dt = 1 / SR
  const rc = 1 / (2 * Math.PI * cutoff)
  const a = dt / (rc + dt)
  let y = 0
  for (let i = 0; i < arr.length; i++) { y += a * (arr[i] - y); arr[i] = y }
  return arr
}

function normalize(arr, peak = 0.82) {
  let m = 0
  for (let i = 0; i < arr.length; i++) m = Math.max(m, Math.abs(arr[i]))
  if (m <= 1e-6) return arr
  const k = peak / m
  for (let i = 0; i < arr.length; i++) arr[i] *= k
  return arr
}

// 线性起音 + 指数衰减：听感最像"物体被碰到"
function envAt(t, dur, attack, decay) {
  if (t < attack) return t / attack
  const u = (t - attack) / Math.max(1e-4, dur - attack)
  return Math.exp(-u * decay)
}

function toWav(arr, sr = SR) {
  const n = arr.length
  const out = Buffer.alloc(44 + n * 2)
  out.write('RIFF', 0)
  out.writeUInt32LE(36 + n * 2, 4)
  out.write('WAVE', 8)
  out.write('fmt ', 12)
  out.writeUInt32LE(16, 16)
  out.writeUInt16LE(1, 20)      // PCM
  out.writeUInt16LE(1, 22)      // 单声道
  out.writeUInt32LE(sr, 24)
  out.writeUInt32LE(sr * 2, 28)
  out.writeUInt16LE(2, 32)
  out.writeUInt16LE(16, 34)
  out.write('data', 36)
  out.writeUInt32LE(n * 2, 40)
  for (let i = 0; i < n; i++) {
    const v = Math.max(-1, Math.min(1, arr[i]))
    out.writeInt16LE(Math.round(v * 32767), 44 + i * 2)
  }
  return out
}

// 弹击：噪声瞬态 + 低频撞击（点击角色）
function snap() {
  const dur = 0.26
  const b = buf(dur)
  const n = buf(dur)
  for (let i = 0; i < n.length; i++) n[i] = Math.random() * 2 - 1
  lowpass(n, 2600)
  for (let i = 0; i < b.length; i++) {
    const t = i / SR
    b[i] = Math.sin(2 * Math.PI * 96 * t) * Math.exp(-t * 26) * 0.95 +
           n[i] * Math.exp(-t * 42) * 0.55
  }
  return normalize(b, 0.85)
}

// 落地：低频下坠 + 轻微摩擦
function thud() {
  const dur = 0.3
  const b = buf(dur)
  const n = buf(dur)
  for (let i = 0; i < n.length; i++) n[i] = Math.random() * 2 - 1
  lowpass(n, 900)
  let phase = 0
  for (let i = 0; i < b.length; i++) {
    const t = i / SR
    const f = 120 * Math.exp(-t * 7) + 42
    phase += (2 * Math.PI * f) / SR
    b[i] = Math.sin(phase) * Math.exp(-t * 13) * 0.95 + n[i] * Math.exp(-t * 30) * 0.5
  }
  return normalize(b, 0.75)
}

// 金币：两个纯音依次点亮（每轮消耗结算）
function coin() {
  const dur = 0.46
  const b = buf(dur)
  for (let i = 0; i < b.length; i++) {
    const t = i / SR
    let v
    if (t < 0.085) {
      v = Math.sin(2 * Math.PI * 1046.5 * t) * Math.exp(-t * 16) +
          0.35 * Math.sin(2 * Math.PI * 2093 * t) * Math.exp(-t * 22)
    } else {
      const u = t - 0.085
      v = (Math.sin(2 * Math.PI * 1568 * u) * 0.9 + 0.3 * Math.sin(2 * Math.PI * 3136 * u)) * Math.exp(-u * 11)
    }
    b[i] = v
  }
  return normalize(b, 0.62)
}

// 提示：两声短促上扬（等待回答 / 余额告警）
function alert() {
  const dur = 0.5
  const b = buf(dur)
  const blip = (start, freq, len) => {
    for (let i = 0; i < Math.round(len * SR); i++) {
      const t = i / SR
      const idx = Math.round(start * SR) + i
      if (idx < 0 || idx >= b.length) continue
      b[idx] += (Math.sin(2 * Math.PI * freq * t) + 0.3 * Math.sin(2 * Math.PI * freq * 3 * t)) *
                envAt(t, len, 0.004, 5.5) * 0.6
    }
  }
  blip(0.02, 784, 0.13)
  blip(0.22, 1046, 0.16)
  return normalize(b, 0.55)
}

const files = [
  ['snap.wav', snap],
  ['thud.wav', thud],
  ['coin.wav', coin],
  ['alert.wav', alert],
]

// 两个角色包共用同一套合成参数，只有"写入采样率"不同：
// 头部写更低的采样率 ⇒ 播放时速度更快、音调整体上移，听起来就是小孩子的嗓子。
// 这比再写一套 DSP 简单得多，而且音色关系（衰减、包络）完全一致。
const PACKS = [
  { dir: path.join(ROOT, 'assets', 'packs', 'luffy'), sr: SR, label: '路飞' },
  { dir: path.join(ROOT, 'assets', 'packs', 'chopper'), sr: Math.round(SR / 1.28), label: '乔巴（升调）' },
]

for (const pack of PACKS) {
  const out = path.join(pack.dir, 'sfx')
  fs.mkdirSync(out, { recursive: true })
  console.log('==', pack.label, 'sr=' + pack.sr)
  for (const [name, fn] of files) {
    const bytes = toWav(fn(), pack.sr)
    fs.writeFileSync(path.join(out, name), bytes)
    console.log('  ' + String(name).padEnd(12), (bytes.length / 1024).toFixed(1) + ' KB')
  }
}
