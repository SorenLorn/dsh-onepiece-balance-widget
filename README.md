# DSH 海贼王记账挂件（One Piece Balance Widget for DSH）

![DSH 海贼王记账挂件](assets/banner.png)

DeepSeek Harness（DSH）Web 界面右下角的常驻挂件：**草帽一伙 9 位角色**随状态换表情，同时显示 DeepSeek 余额、今日已用与每轮对话消耗；气泡内容可完全自定义（点击序列、模块化排版、并列加权出泡、随机语句 / 随机图片）。标准 DSH bundle 插件，`dsh plugin` 一键安装，不需要任何会话令牌。

## 来源：本项目是二次开发

本仓库是 **[月匠 MeteorNOX](https://github.com/MeteorNOX) 的 [DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)（DSH 小鲸鱼记账挂件）的二次开发**（MIT 许可）。

记账内核、余额观测与校正、泡泡系统、音效系统、吸附与翻转、路由与打包方式**全部沿用上游**；本项目只做了三件事：

| 改动 | 说明 |
|---|---|
| 角色皮肤制 | 把「一只鲸鱼」换成 9 套角色包，每套 3~4 张状态帧，菜单里即点即切 |
| 素材流水线 | `tools/prep-art.py`：去底抠图 → 去白边 → 1024 归一 → 同包曝光统一 → 状态命名 |
| 主题视觉 | 插件图标、宣传图、气泡纸张配色统一成海贼王风格 |

> 记账口径、多厂商 API（34 个模板）、凭据安全边界、完整 FAQ 这些**上游原有功能**没有改动，本文不重复抄写，请直接看[上游 README](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget#readme)。

## 角色与状态

挂件菜单里点「形象」一行即可切换角色，立刻换脸（不用刷新），选择记在 `localStorage` 的 `dshw-pack`，下次打开沿用。

| 包 id | 角色 | 待机 `idle` | 被点击 `tap` | 等待回答 `wait` | 余额告警 `warning` |
|---|---|---|---|---|---|
| `luffy` | 路飞 | ✅ | ✅ | ✅ | ✅ |
| `chopper` | 乔巴 | ✅ | ✅ | ✅ | ✅ |
| `zoro` | 索隆 | ✅ | ✅ | ✅ | — |
| `nami` | 娜美 | ✅ | ✅ | ✅ | — |
| `usopp` | 乌索普 | ✅ | ✅ | ✅ | — |
| `sanji` | 山治 | ✅ | ✅ | ✅ | — |
| `robin` | 罗宾 | ✅ | ✅ | ✅ | — |
| `jinbe` | 甚平 | ✅ | ✅ | ✅ | — |
| `brook` | 布鲁克 | ✅ | ✅ | ✅ | — |

> 9 个按钮一排放不下，这一行是**横向滚动**的：按钮条下方有细滚动条（可拖动、点轨道跳转），鼠标滚轮在这一行上滚也会横向推；重新打开菜单时会把当前选中的角色滚进可视区。

### 状态什么时候会变

「状态帧」负责表情，「CSS 动作」叠在帧上负责位移与形变：

| 触发场景 | 状态帧 | 动作 | 音效 |
|---|---|---|---|
| 静置常驻 | `idle` | 4.2s 呼吸 | — |
| 点角色 / 点泡泡 | `tap` | 挤压回弹 | `tap` |
| 松手 | 保持当前帧 | 落地缓冲 | `land` |
| 拖拽超过 3px | 保持当前帧 | 小幅摆动 | — |
| 每轮对话结算 | 保持当前帧 | 起跳 | `cost` |
| 模型思考 / 输出中 | `wait` | 慢速点头 | — |
| 提问 / 授权挂起 | `wait` | 循环摇晃 | `wait` |
| 余额低于预警线 | `warning`（没有就回落 `idle`） | 抖动 | — |

三条要记住的：

- **缺帧自动降级**：没有 `warning` 的角色（目前 7 位）在告警时回落到 `idle`，不会报错、也不会出碎图。
- **切角色不影响记账**：换皮肤只换图，账本、今日已用、泡泡配置都不动。
- **加第 10 位角色**：把三张图放进 `assets/packs/<新id>/` 并写一份 `pack.json`，或用 `tools/prep-art.py` 从原图生成。

## 安装

```bash
# 从本仓库装（推荐）
dsh plugin --profile web add github:SorenLorn/dsh-onepiece-balance-widget

# 或在本仓库根目录
dsh plugin --profile web add link:.
```

- 装完**重启 `dsh web`**，再 F5 刷新浏览器（图标、宿主侧路由都需要重启才生效；只改前端脚本则 Ctrl+F5 即可）。
- ⚠️ npm 上的 `dsh-whale-widget` 是**上游鲸鱼版**（本 fork 未单独发版，`package.json` 的 name 沿用上游以免破坏 bundle 解析）——想装海贼王版请用上面的 `github:` 或 `link:.`。
- 官方桌面客户端（Electron）请在桌面端会话里让 DSH 自己装，别加 `--profile web`。

## 仓库结构

```text
.
├── package.json / cordis.patch.yml   # 插件元数据与挂载声明
├── icon.png                          # 插件列表图标（256×256，圆角透明）
├── assets/
│   ├── banner.png                    # 本文顶部宣传图
│   ├── whale-widget.js               # 前端挂件本体（宿主按 mtime 热读取）
│   ├── packs/                        # ★ 9 套角色皮肤：pack.json + 状态帧 + sfx/ + emblem.svg
│   └── …                             # 默认形象、内置音效、泡泡图
├── lib/
│   ├── index.js                      # 宿主插件（路由 + 记账 + 角色包扫描）
│   └── accounting.mjs                # 记账内核
└── tools/
    ├── prep-art.py                   # ★ 素材流水线（下文）
    ├── make-sfx.mjs                  # 程序合成音效
    └── ci-audit.mjs                  # CI 自检
```

宿主对外暴露 **28 个 `/dsh-whale/*` 路由**（`/dsh-whale/packs.json` 等），全部接在 DSH 的浏览器信任栅栏后面：不带会话直接访问返回 **401/403** 属正常，说明路由已注册且栅栏在工作。

## 素材从哪来、怎么重跑

角色帧由根目录的原始立绘经 `tools/prep-art.py` 生成，**原始立绘不入库**（体积大、命名也不统一，只作本地输入），仓库里只保留处理好的 `assets/packs/**`。

```bash
python tools/prep-art.py            # 全部重跑
python tools/prep-art.py nami       # 只处理一个包
python tools/prep-art.py --check    # 只统计白边/光晕，不改文件
```

流水线的三条关键约束（都是踩过坑才定下来的）：

1. **人物内部的白一律不动**：只去掉与画布边缘连通的白底。眼白、牙齿、白衣、帽子上的白色图案在亮度/标准差/面积上与被围住的背景空隙完全重叠，任何自动阈值都会把眼睛或帽子删掉；确实要抠的封闭空隙只能在脚本 `HOLES` 里按种子点手工指定。
2. **去白边分三步**：轮廓最外 1~2px 是「角色色 × 白底」的混色（不透明但颜色脏）→ 用内侧颜色覆盖；半透明边缘带用最近的角色色扩散；高斯模糊留下的低 alpha 尾巴直接归零，只留 1px 抗锯齿。
3. **同包各帧统一曝光**：AI 分次生成的四张图亮度会差 10~20 级，不拉齐摆在一起就是「一张深一张浅」。

## 常见问题

- **换了角色，记账数据会不会变？** 不会。角色只是外观，账本按密钥指纹分本，与皮肤无关。
- **新图标什么时候显示？** `icon.png` 在宿主启动时读入，**重启 `dsh web` / 桌面客户端**才刷新。
- **余额与官网对不上？** 先核对同一账户、同一币种、同一统计区间；有充值的话用「小鲸鱼记账 → 余额校正」填实际到账金额（口径说明见上游 README）。
- **想改气泡里的内容？** 菜单 →「泡泡设置」逐模块编辑，金额用 `{cost}` 引用。

## 致谢与许可

- **上游项目**：[MeteorNOX/DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)，作者**月匠（MeteorNOX）**及其贡献者（完整名单见上游 README 的「致谢」）。本项目的记账、泡泡、音效、吸附、打包全部来自上游。
- **本项目的美术**：角色立绘为 AI 图像工具生成后经脚本处理，属同人性质的演绎，**不是官方素材、也未获原作权利方授权**；来源与权利说明见 [PROVENANCE.md](PROVENANCE.md)。
- **许可**：代码 MIT（见 [LICENSE](LICENSE)）；`assets/`、`icon.png` 下的美术素材**不在 MIT 覆盖范围**，随插件原样提供，不授予再许可。
