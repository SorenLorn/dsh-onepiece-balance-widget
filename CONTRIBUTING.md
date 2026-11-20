# 贡献指南

这是基于 [月匠 MeteorNOX 的小鲸鱼记账挂件](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget) 的**主题化二次开发**（详见 [README](README.md) 与 [PROVENANCE](PROVENANCE.md)）。记账、泡泡、音效等核心逻辑在上游，欢迎把这类改动提给上游；本仓库收的是**主题相关**的贡献。

## 欢迎什么

- **新角色包**：草帽团以外的角色、或现有角色的补帧（比如给 7 位补 `warning`）
- **素材处理改进**：`tools/prep-art.py` 的抠图/去白边/曝光统一
- **视觉细节**：菜单、气泡、图标的样式微调
- **Bug**：角色切帧、菜单滚动、包加载等与本主题相关的问题

## 加一个角色包

1. 把待机 / 被点击 / 等待回答三张原图放到仓库根目录（原图不入库，`.gitignore` 已忽略）；
2. 在 `tools/prep-art.py` 的 `JOBS` 里加三行：`('包id', '原图文件名', 'idle.png', None, False)`；
3. 跑 `python tools/prep-art.py 包id`，会生成 `assets/packs/<包id>/`（含 `pack.json`，缺的公共素材会自动补齐）；
4. 在 `assets/packs/<包id>/pack.json` 里填中文 `name`，需要的话换掉 `emblem.svg`；
5. 更新 README 的角色表。

## 提交前自检

```bash
node tools/ci-audit.mjs           # 路由对等、打包完整性、packs 是否都被 git 跟踪
python tools/prep-art.py --check  # 白边/光晕指标（应接近 0）
```

## 素材要求

- 只提交 AI 生成或自己绘制的**同人**素材，不提交动画/漫画原作截图或官方图；
- 处理后的 PNG 请保持 1024×1024、透明背景、无白边（`--check` 能看出来）；
- 新增素材请在 `PROVENANCE.md` 里补一行来源说明。
