# 路飞挂件 · 形象素材清单与生成提示词

> 适用项目：`DeepSeek-Balance-Whale-Widget`（DSH 右下角余额挂件）
> 用途：替换挂件角色的美术素材，配合「角色包 + 动作引擎」方案使用
> 生成工具：ChatGPT（GPT-4o 图像）／任何支持参考图派生的文生图工具

---

## 0. 结论：4 张必需 + 1 张可选

| 文件名 | 状态 | 是否必需 | 触发时机 | 画面要点 |
|---|---|---|---|---|
| `idle.png` | 待机 | **必需** | 常驻，占 95% 时间 | 自信闭嘴笑，单手扶帽檐 |
| `tap.png` | 被点击 | **必需** | 点角色 / 点泡泡 | 大笑露牙，双手举起 |
| `wait.png` | 等待回答 | **必需** | 提问 / 授权挂起期间 | 歪头疑惑，手挠脸 |
| `warning.png` | 余额告警 | **必需** | 余额低于阈值 | 惊讶冒汗，双手护在胸前 |
| `blink.png` | 眨眼 | 可选 | 每 3~7 秒闪 120ms | 与 idle 相同，仅闭眼 |

**为什么是 5 张而不是更多**：挤压、拉伸、起跳、摇晃、落地这些动作全部由 CSS 变换完成，不需要为它们单独出图。只有「脸部信息无法用变换表达」的差异才值得单独画一张。所以核心只要 4 张，加眨眼是性价比最高的一张补充（成本 +1，生动度 +30%）。

**不需要**：拖拽帧（用拉伸变换实现）、悬停帧（用倾身变换实现）、每轮消耗帧（复用 `tap.png`）。

---

## 1. 通用规范（所有图必须一致）

| 项 | 要求 | 不达标会怎样 |
|---|---|---|
| 画布 | `1024 × 1024`，PNG-24 带 Alpha | 尺寸不一会让帧切换时人物“跳大小” |
| 构图 | **上半身**，头顶留 4% 余量，腰部切在画布底边 | 留白过多会显得人物很小 |
| 人物占比 | 高度占画布 **92%~96%** | 低于 90% 挂件里会缩成一团 |
| 朝向 | **3/4 左侧脸**（面朝气泡方向） | 朝右会和气泡“背对背” |
| 描边 | 深藏青 `#1B2A63`，粗细统一（1024 画布下约 8px） | 与气泡描边 `#203170` 打架 |
| 上色 | 赛璐璐平涂，每种颜色 2 个层次 | 写实厚涂缩小后会糊成一团 |
| 背景 | **纯透明**，无地面、无投影、无边框 | 白方块会直接露在页面上 |
| 禁止 | 文字、水印、符号（问号/感叹号）、多个角色、遮挡脸的手 | 缩小到 120px 时全是噪点 |

> 挂件里角色只占方块右下角的 **59.45%**，实际显示宽度约 220px。所有细节都要按“缩到 120px 还认得出”的标准画。

---

## 2. 为什么必须“同画布、同比例、同基线”

挂件切状态是直接把 `img.src` 换掉，容器不重排、不做过渡补偿。这意味着：

- 两张图人物高度差 5%，切状态时就会看到**人物瞬间跳了一下**；
- 头顶位置差 20px，呼吸动画的节奏就会被打断；
- 腰线不在同一水平线，切帧时会有“上下滑动”的错觉。

**所以正确顺序是：先出一张满意的 `idle.png` 定稿，其余 4 张全部以它为参考图派生**，而不是分别写 5 段毫不相干的提示词。

---

## 3. 逐张提示词

### 3.1 `idle.png` —— 待机（先做这张）

**中文要点**：自信的闭嘴笑，一只手扶着草帽帽檐，另一只手自然下垂；重心略微后仰，显得放松。这是所有其他图的“基准姿态”，后续派生都以它为准。

```
Chibi anime sticker illustration, single character, upper body from head to waist, waist cropped exactly at the bottom edge of the canvas, head top 4% below the top edge, character fills 94% of the canvas height.

Character: a cheerful pirate boy, 2.5 heads tall, messy black hair, straw hat with a red ribbon band, a small stitched scar under his left eye, large expressive eyes, thick black eyebrows. Open red vest with no shirt underneath, an X-shaped scar on his bare chest, blue rolled-up shorts.

Pose: three-quarter view facing LEFT, body angled toward the viewer's left, one hand lightly holding the brim of his straw hat, the other arm hanging relaxed at his side. Calm confident closed-mouth smile, shoulders relaxed.

Style: flat cel shading, exactly two tones per color, no gradients, no soft airbrush, thick clean dark navy outline in #1B2A63, uniform line weight, no rim light, no cast shadow, no ground shadow.

Background: fully transparent, completely empty, no backdrop, no floor, no border, no frame, no text, no watermark, no symbols.
```

**负向提示词（Negative prompt）**：

```
realistic, 3d render, soft airbrush shading, gradient, glow, rim light, drop shadow, white background, checkerboard, multiple characters, cropped head, cropped hands, text, watermark, logo, symbol, question mark, exclamation mark, extra fingers, extra limbs
```

---

### 3.2 `tap.png` —— 被点击

**中文要点**：与 `idle` 完全相同的画法、比例、位置，只把表情和手臂换掉：张嘴大笑露出一排牙，眼睛笑成弯月，双手向上举。**脖子以下尽量不动**，否则切帧会像换了个人。

```
Use the attached image as an exact reference. Keep the character design, canvas size, character scale, head position, waist line, line weight, color palette and shading style completely unchanged.

Change only this: the expression becomes a huge open-mouth laugh showing a row of teeth, eyes squeezed shut into happy curved arcs, both arms raised up in excitement with open hands, head tilted very slightly back.

Everything below the chest must stay identical to the reference. Same three-quarter view facing left, same straw hat angle, same outline color #1B2A63, same flat two-tone cel shading.

Background: fully transparent, no shadow, no ground, no text, no symbols, single character only.
```

---

### 3.3 `wait.png` —— 等待回答

**中文要点**：歪头、挑一边眉、一只手在挠脸颊。这个状态会在“模型卡住等你点确认”时循环摇晃，所以表情要偏向“疑惑但不焦虑”。

```
Use the attached image as an exact reference. Keep the character design, canvas size, character scale, head position, waist line, line weight, color palette and shading style completely unchanged.

Change only this: the head tilts about 12 degrees to the side, one eyebrow raised higher than the other, mouth a small confused pout, one hand raised to scratch his cheek. The other arm stays relaxed as in the reference.

Do not add any question mark, punctuation or floating symbols. The confusion must come only from the face and the head tilt. Same three-quarter view facing left, same straw hat angle, same outline color #1B2A63, same flat two-tone cel shading.

Background: fully transparent, no shadow, no ground, no text, no symbols, single character only.
```

---

### 3.4 `warning.png` —— 余额告警

**中文要点**：眼睛瞪大、嘴张成小圆、太阳穴一滴汗、双肩耸起、双手护在胸前。要“被吓到”而不是“生气”，因为这是提醒你钱快没了，不是责备。

```
Use the attached image as an exact reference. Keep the character design, canvas size, character scale, head position, waist line, line weight, color palette and shading style completely unchanged.

Change only this: eyes wide open in shock, mouth open in a small round "o", a single sweat drop on his temple, shoulders raised, both hands pulled up defensively in front of his chest.

No exclamation mark, no alarm icon, no red glow, no extra props. The alarm must read from the pose and the face alone. Same three-quarter view facing left, same straw hat angle, same outline color #1B2A63, same flat two-tone cel shading.

Background: fully transparent, no shadow, no ground, no text, no symbols, single character only.
```

---

### 3.5 `blink.png` —— 眨眼（可选）

**中文要点**：和 `idle` 一个字都不差，只有眼睛闭上、嘴型不变。它的用途是每 3~7 秒替换 120ms，制造“在呼吸的活物”感。

```
Use the attached image as an exact reference. Keep every single thing identical: same pose, same hand on the hat brim, same head angle, same canvas size, same scale, same colors, same line weight, same transparent background.

Change only this: both eyes are fully closed in a calm natural blink, drawn as two simple downward-curved lines. The mouth stays exactly the same closed confident smile as the reference.

Do not change the eyebrows, the hat, the hair strands, the arms or the body. This must be frame-compatible with the reference so that swapping between them looks like a blink, not a different drawing.
```

---

## 4. ChatGPT 里的操作流程

1. **先跑 `idle.png`**。生成 4~6 张，挑一张：朝向对、占比够、描边干净、缩小后仍认得出。
2. **把它固定为参考图**。后续每张都在同一会话里上传这张图，用“Use the attached image as an exact reference”开头。
3. **一次只改一件事**。想同时改表情和手，模型会顺手把比例也改了。分两轮改，第二轮再微调手。
4. **每次出图后立刻检查三项**：帽檐角度、人物占比、腰线位置。任一项跑偏就重来，不要试图用后期硬修。
5. **不要在同一个会话里换风格词**。换一次“thicker outline”，后面所有图都会跟着变。

**如果工具不给透明背景**：把提示词里的背景句换成 `Background: pure flat white #FFFFFF, no shadow, no gradient.`，生成后用任意抠图工具去白底（Photoshop 魔棒 / remove.bg / 本地脚本均可）。注意**不要**让它生成“棋盘格”，那是假透明的示意图，抠不干净。

---

## 5. 生成后的后处理（必须做）

| 步骤 | 做法 | 原因 |
|---|---|---|
| 1. 抠底 | 白底→透明，边缘做 0.8px 羽化 | 硬边会在深色页面上出现白毛边 |
| 2. 统一画布 | 全部重采样到 `1024×1024` | 帧切换不跳大小 |
| 3. 对齐腰线 | 腰部切边贴画布底边（y=1024） | 切帧不上下滑 |
| 4. 对齐头高 | 头顶统一落在 y≈40 处 | 呼吸动画节奏一致 |
| 5. 导出 | PNG-24，文件名与下表一致 | 少一步就是 404 |

对齐可以在任意支持图层的工具里做：把 5 张叠在一起，降低透明度，用自由变换逐张对到同一基线上，再分别导出。

---

## 6. 与项目的对应关系

素材放进角色包目录后，由 `pack.json` 声明映射：

```
assets/packs/luffy/
├─ pack.json
├─ idle.png
├─ tap.png
├─ wait.png
├─ warning.png
├─ blink.png        （可选）
└─ sfx/
   ├─ boing.wav     （点击：橡皮弹击）
   ├─ thud.wav      （落地）
   ├─ coin.wav      （每轮消耗）
   └─ alert.wav     （等待 / 告警）
```

```json
{
  "name": "路飞",
  "frames": {
    "idle": "idle.png",
    "tap": "tap.png",
    "wait": "wait.png",
    "warning": "warning.png",
    "blink": "blink.png"
  },
  "sounds": {
    "tap": "sfx/boing.wav",
    "land": "sfx/thud.wav",
    "cost": "sfx/coin.wav",
    "wait": "sfx/alert.wav",
    "warning": "sfx/alert.wav"
  }
}
```

两条设计约束：

- **缺帧自动降级**：某个状态图不存在时，该状态回落到 `idle`，不影响挂件运行。所以你可以先只放 `idle.png` 就开始用。
- **命中区按 `idle` 计算**：点击判定是从待机图的 alpha 通道现算的凸包。其余四张的轮廓不要和 `idle` 差太多（头肩宽度差控制在 10% 以内），否则某些状态点击手感会偏。

---

## 7. 验收清单

- [ ] 5 张图同为 `1024×1024`，人物高度差 ≤ 2%
- [ ] 全部为透明底，叠在白色气泡旁没有白边、没有灰影
- [ ] 帽檐角度在 5 张里一致（这一项最容易漂）
- [ ] 缩到 120px 宽时，仍能分辨“笑 / 疑惑 / 惊讶”三种表情
- [ ] 描边颜色接近 `#1B2A63`，不与气泡的 `#203170` 撞色
- [ ] 无文字、无符号、无多余角色
- [ ] 文件名与 `pack.json` 完全对应，大小写一致

---

## 8. 版权提示

角色形象若取自现有动漫作品，**私有使用**与**公开发布**是两件事。本项目的 `PROVENANCE.md` 已声明 `assets/**` 不在 MIT 许可范围内、按 as-is 提供且不授予再许可。如果你打算把挂件发布出去，建议把角色替换为完全原创的形象——上面每一条提示词都只描述了“草帽、红背心、少年感”这类通用特征，改掉几处外观细节即可得到不侵权的原创角色。
