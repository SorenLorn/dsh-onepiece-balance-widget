#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把生成的立绘规范化为挂件可用的角色帧（支持多个角色包）。

做五件事：
  1. 去底：只去掉**与画布边缘连通**的白底（含 ChatGPT 的"假透明"棋盘格底）；
     人物内部的白（眼睛、牙齿、白衣、帽子上的白色图案）一律不动 —— 这些区域
     和被围住的背景空隙在亮度/标准差/面积上完全重叠，自动判定必然误伤，
     确实需要抠掉的空隙只能由 HOLES 手工指定种子点。
     已经抠好的图可跳过这一步。
  2. 擦掉指定矩形里的水印
  3. 去白边（defringe）：把角色内部的颜色向外扩散到 alpha 边缘带，
     让描边外侧那一圈不再残留"白底混色"，深色界面上不会出现亮圈
  4. 统一到 1024x1024：角色高 88%、底边距 2%、水平居中、宽度不超 94%
  5. 导出 PNG-24（带 alpha）

状态命名（与 pack.json 的 frames 键一致）：
    idle = 待机    tap = 被点击    wait = 等待回答    warning = 余额告警

用法：
    python tools/prep-art.py            # 处理全部
    python tools/prep-art.py nami       # 只处理指定包
    python tools/prep-art.py --check    # 只统计现有帧的白边残留，不改文件

依赖：Pillow（pip install pillow）
原图不会被修改，只读取。
"""
import os
import sys
from collections import deque
from PIL import Image, ImageDraw, ImageFilter, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 原始立绘不入库，也可能被挪到仓库外面。按顺序找：仓库根 → 同级 dsh-one-pice/
SRC_DIRS = [ROOT, os.path.join(os.path.dirname(ROOT), 'dsh-one-pice')]

CANVAS = 1024          # 输出画布边长
FILL = 0.88            # 角色高度占画布比例
MAXW = 0.94            # 角色宽度上限（带鹿角/大翅膀的角色靠这条兜底）
BOTTOM = 0.02          # 底部留白比例

BLEED = 10             # 边缘带颜色扩散半径（源图像素）；要 > 缩小时的滤波支撑半径
TAIL = 26              # alpha 低于此值直接归零：高斯模糊会留 2~3px 的淡尾巴，
                       # 浅色角色旁边这条尾巴就是深色界面上的"白光晕"
AA_KNEE = 235          # alpha 高于此值直接拉满，只留 1px 抗锯齿过渡

# 包 id → 中文名（pack.json 的 name 字段）
PACK_NAMES = {
    'luffy': '路飞',
    'chopper': '乔巴',
    'nami': '娜美',
    'usopp': '乌索普',
    'sanji': '山治',
    'zoro': '索隆',
    'robin': '罗宾',
    'jinbe': '甚平',
    'brook': '布鲁克',
}

# pack: 输出到 assets/packs/<pack>/
# src : 工作区根目录下的原图
# rect: 需要先擦成白色的矩形（水印），None = 没有
# precut: 原图已经带干净 alpha（跳过抠图，只做尺寸归一）
JOBS = [
    # —— 路飞 ——
    ('luffy', '路飞待机.jpg', 'idle.png', (250, 792, 610, 851), False),
    ('luffy', '路飞被点击.png', 'tap.png', None, False),
    ('luffy', '路飞等待回答.png', 'wait.png', None, False),
    # —— 乔巴 ——
    ('chopper', '乔巴待机.png', 'idle.png', None, True),
    ('chopper', '乔巴被点击.png', 'tap.png', None, False),
    ('chopper', '乔巴等待回答.png', 'wait.png', None, False),
    # —— 娜美 ——
    ('nami', '待机娜美.png', 'idle.png', None, False),
    ('nami', '被点击娜美.png', 'tap.png', None, False),
    ('nami', '等待回复娜美.png', 'wait.png', None, False),
    # —— 乌索普 ——
    ('usopp', '待机乌索普.png', 'idle.png', None, False),
    ('usopp', '被点击乌索普.png', 'tap.png', None, False),
    ('usopp', '等待回复乌索普.png', 'wait.png', None, False),
    # —— 山治 ——
    ('sanji', '待机山治.png', 'idle.png', None, False),
    ('sanji', '被点击山治.png', 'tap.png', None, False),
    ('sanji', '等待回复山治.png', 'wait.png', None, False),
    # —— 索隆 ——
    ('zoro', '索隆待机.png', 'idle.png', None, False),
    ('zoro', '被点击索隆.png', 'tap.png', None, False),
    ('zoro', '等待回复索隆.png', 'wait.png', None, False),
    # —— 罗宾 ——
    ('robin', '待机罗宾.png', 'idle.png', None, False),
    ('robin', '被点击罗宾.png', 'tap.png', None, False),
    ('robin', '等待回复罗宾.png', 'wait.png', None, False),
    # —— 甚平 ——
    ('jinbe', '甚平待机.png', 'idle.png', None, False),
    ('jinbe', '被点击甚平.png', 'tap.png', None, False),
    ('jinbe', '等待回复甚平.png', 'wait.png', None, False),
    # —— 布鲁克 ——
    ('brook', '布鲁克待机.png', 'idle.png', None, False),
    ('brook', '被点击布鲁克.png', 'tap.png', None, False),
    ('brook', '等待回复布鲁克.png', 'wait.png', None, False),
]

# 逐帧指定"确实是背景、需要抠掉"的封闭空隙（**源图坐标的种子点**）。
# 只写长得像背景、又和画布边缘不连通的空隙；人物的眼睛/牙齿/白衣一律不写。
HOLES = {
}

# 没有对应原图、只能原地处理的帧。
# 这两张 warning 是旧管线留下的成品，没有大图可重抠；放进来自动处理只会每跑一次就再瘦一圈
# （去污染要动边缘就得收 alpha，重复收就是重复腐蚀）。所以这里留空，成品直接沿用。
STATIC_FRAMES = {}

# 新包沿用的公共素材（每个角色可以后续换成自己的）
SCAFFOLD_FROM = 'luffy'


def edge_white_ratio(im):
    """半透明边缘带里"近白像素"的占比 —— 白边残留的量化指标。"""
    px = im.load()
    w, h = im.size
    tot = white = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b, a = px[x, y]
            if 4 < a < 250:
                tot += 1
                if min(r, g, b) > 200 and max(r, g, b) - min(r, g, b) < 25:
                    white += 1
    return (white / tot * 100.0) if tot else 0.0, tot


def tighten_alpha(a):
    """砍掉 alpha 的淡尾巴，把 2~3px 的柔和过渡压成 1px 抗锯齿。

    高斯模糊保证边缘不锯齿，但也会在轮廓外留一圈 alpha 5~30 的像素。
    深色界面上这圈像素的亮度贡献是 (角色色 × alpha)，浅色角色旁边就是肉眼可见的白光晕，
    所以低 alpha 一律归零、高 alpha 直接拉满，只保留中间 1px 的过渡。
    """
    span = float(AA_KNEE - TAIL)
    return a.point(lambda v: 0 if v < TAIL else (255 if v >= AA_KNEE else int(round((v - TAIL) * 255.0 / span))))


def decontaminate(im, reach=2):
    """把轮廓最外 1~2px 的"被白底污染的颜色"换成内侧的真实颜色。

    bleed_colors 只管 alpha < 255 的像素，但**完全不透明**的最外圈同样脏：
    原图的抗锯齿/JPEG 压缩会把描边和背景混成 (255,239,214) 这种浅色，
    抠图后这圈仍是 alpha=255，于是深色底上就显出一条浅色描边线。
    做法：找出「不透明但离透明区 ≤ reach px」的像素，用再往内（≥3px）的颜色覆盖。
    只覆盖颜色、不动 alpha，所以轮廓形状一点不变。
    """
    w, h = im.size
    alpha = im.split()[3]
    near = alpha.point(lambda v: 255 if v == 0 else 0)
    near = near.filter(ImageFilter.MaxFilter(2 * reach + 1))           # 透明区外扩 reach
    solid = alpha.point(lambda v: 255 if v >= 250 else 0)
    ring = ImageChops.multiply(solid, near)                            # 不透明但贴着透明区
    rb = ring.tobytes()

    px = im.load()
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    dirt = [(i % w, i // w) for i in range(w * h) if rb[i]]
    if not dirt:
        return im
    dirt_set = set(dirt)
    # 队列种子：紧贴污染圈、且自己没被污染的不透明像素（颜色可信）
    from collections import deque
    q = deque()
    filled = set()
    for (x, y) in dirt:
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            if (nx, ny) in dirt_set:
                continue
            r, g, b, a = px[nx, ny]
            if a >= 250:
                q.append(((x, y), (r, g, b)))
                filled.add((x, y))
                break
    while q:
        (x, y), c = q.popleft()
        px[x, y] = (c[0], c[1], c[2], px[x, y][3])
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) in dirt_set and (nx, ny) not in filled:
                filled.add((nx, ny))
                q.append(((nx, ny), c))
    return im


def bleed_colors(im, radius=BLEED):
    """把实心区的颜色向外扩散到 alpha 边缘带（defringe）。

    为什么不直接"按 alpha 反算原色"：纯白底抠图后边缘像素是 c = a*原色 + (1-a)*白，
    反算要除以 alpha，alpha 很小时是除零噪声；而缩小时那圈近白像素还会被滤波
    摊到描边外，深色背景上就是一圈亮边。
    这里改成"用最近的角色色覆盖边缘带"，透明区也带上角色色，
    于是无论是直接显示还是缩放，边缘混出来的都是角色色而不是白色。

    取色用 **最近实心像素的颜色**（先到先得），不做邻居平均 —— 平均会把
    相邻的两种颜色混出中间亮度，浅色皮肤挨着深色描边时，平均色仍然偏亮，
    深色底上依旧能看到一圈淡光。
    """
    w, h = im.size
    alpha = im.split()[3]
    ab = alpha.tobytes()
    px = im.load()
    known = bytearray(w * h)
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    # 种子只取"贴着边缘的实心像素"，避免把整块实心区都塞进队列
    for y in range(h):
        base = y * w
        for x in range(w):
            if ab[base + x] >= 250:
                known[base + x] = 1
    frontier = []
    for y in range(h):
        base = y * w
        for x in range(w):
            if not known[base + x]:
                continue
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and not known[ny * w + nx]:
                    frontier.append((x, y))
                    break
    if not frontier:
        return im

    for _ in range(radius):
        cand = {}
        for (x, y) in frontier:
            c = px[x, y]
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and not known[ny * w + nx]:
                    cand.setdefault((nx, ny), c)
        if not cand:
            break
        for (x, y), c in cand.items():
            px[x, y] = (c[0], c[1], c[2], px[x, y][3])
        for (x, y) in cand:
            known[y * w + x] = 1
        frontier = list(cand.keys())
    return im


def matte(path, clear_rect=None, holes=None):
    """白底/棋盘格底 ⇒ 带 alpha 的 RGBA。

    先按「低饱和 + 高亮度」生成背景候选掩膜，再在掩膜上从边缘洪水填充。
    为什么不直接在原图上 floodfill：Pillow 的 thresh 是**三通道差值之和**，
    棋盘格的 235 与 255 差 3x20=60，超过常规阈值 ⇒ 每格各自填、连不成片。
    """
    im = Image.open(path).convert('RGB')
    w, h = im.size

    if clear_rect:
        ImageDraw.Draw(im).rectangle(clear_rect, fill=(255, 255, 255))

    r, g, b = im.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mn = ImageChops.darker(ImageChops.darker(r, g), b)
    sat = ImageChops.subtract(mx, mn)
    sat_ok = sat.point(lambda v: 255 if v < 12 else 0)
    bright_ok = mn.point(lambda v: 255 if v > 200 else 0)
    cand = ImageChops.multiply(sat_ok, bright_ok)   # 255 = 背景候选

    px = cand.load()
    seeds = []
    for x in range(0, w, 4):
        seeds.append((x, 0))
        seeds.append((x, h - 1))
    for y in range(0, h, 4):
        seeds.append((0, y))
        seeds.append((w - 1, y))
    for s in seeds:
        if px[s[0], s[1]] == 255:
            ImageDraw.floodfill(cand, s, 128, thresh=0)

    # 封闭空隙只能由 HOLES 里的种子点手工指定：自动判定无法可靠区分
    # 「眼睛/牙齿/白衣」（均值 245~253、sd 4~18、面积 2k~9k）和「真的背景空隙」
    # （均值 249~250、sd 3~6、面积 3k~82k）——两组统计量完全重叠，任何阈值都会误伤。
    for seed in (holes or ()):
        if 0 <= seed[0] < w and 0 <= seed[1] < h and cand.load()[seed[0], seed[1]] == 255:
            ImageDraw.floodfill(cand, seed, 128, thresh=0)

    alpha = cand.point(lambda v: 0 if v == 128 else 255)
    alpha = alpha.filter(ImageFilter.MinFilter(3))       # 收 1px，去掉描边外侧的晕边
    alpha = alpha.point(lambda v: 0 if v < 8 else 255)   # 灭掉残留的极淡噪点
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.7))  # 只留 1px 抗锯齿过渡
    alpha = tighten_alpha(alpha)                         # 砍掉模糊留下的淡尾巴（白晕来源）

    out = im.convert('RGBA')
    out.putalpha(alpha)
    # 去污染只改颜色、不动 alpha，不会把细结构切碎。
    # 实测：JPEG 来源（路飞待机）的指尖想拉到 5px 反而把描边深色带进去、发黑，
    # 所以统一用 2px；那一圈的奶油色在挂件实际尺寸（角色约 200px）下不足 1px，看不到。
    reach = 2
    out = decontaminate(out, reach=reach)
    return bleed_colors(out)


def load_precut(path):
    """已经抠好的图：把 253/254 这类"接近满"的 alpha 拉满，再补白边。"""
    im = Image.open(path).convert('RGBA')
    a = im.split()[-1].point(lambda v: 255 if v >= 200 else (0 if v <= 8 else v))
    im.putalpha(tighten_alpha(a))
    return bleed_colors(decontaminate(im))


def normalize(im):
    """裁到内容，等比缩放并居中；高度优先，宽度超限时以宽度为准。"""
    bbox = im.split()[-1].getbbox()
    if not bbox:
        raise RuntimeError('empty alpha')
    content = im.crop(bbox)
    cw, ch = content.size

    target_h = int(CANVAS * FILL)
    target_w = int(CANVAS * MAXW)
    scale = min(target_h / ch, target_w / cw)   # 鹿角这类宽体型靠这条兜底
    new_w, new_h = max(1, round(cw * scale)), max(1, round(ch * scale))
    content = content.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
    x = (CANVAS - new_w) // 2
    y = CANVAS - int(CANVAS * BOTTOM) - new_h
    canvas.alpha_composite(content, (x, y))
    return canvas, bbox


def color_stats(im):
    """彩色像素的平均亮度（用来判断同一套图是不是同一档曝光）。"""
    px = im.load()
    w, h = im.size
    tot = 0.0
    n = 0
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            r, g, b, a = px[x, y]
            if a < 200:
                continue
            mx, mn = max(r, g, b), min(r, g, b)
            if mx - mn > 25:          # 只看有色区域；白牙、帽子白点不参与
                tot += (mx + mn) / 2.0
                n += 1
    return (tot / n) if n else 0.0


def match_exposure(frames):
    """把同一角色包的各帧拉到同一档曝光。

    为什么需要：AI 分几次出的图，亮度会差 10~20 级（实测乔巴 idle 147 vs warning 170）。
    高度归一救不了这个 —— 摆在一起就是"一张深一张浅"。
    做法：以各帧彩色亮度中位数为基准，算一个标量增益；只作用在有色像素上（按饱和度做软边过渡），
    白牙/高光保持原样，避免"整体发灰"。
    """
    stats = [(f, color_stats(im)) for f, im in frames]
    vals = sorted(v for _, v in stats if v > 0)
    if len(vals) < 2:
        return frames
    ref = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals)//2 - 1] + vals[len(vals)//2]) / 2.0
    out = []
    for (name, im), _v in zip(frames, stats):
        cur = color_stats(im)
        if cur <= 1:
            out.append((name, im))
            continue
        gain = max(0.85, min(1.18, ref / cur))   # 限幅：别把本来正常的帧也拉坏
        if abs(gain - 1.0) < 0.02:
            out.append((name, im))
            continue
        lut = [min(255, int(round(i * gain))) for i in range(256)]
        ident = list(range(256))
        bright = im.point(lut + lut + lut + ident)  # RGBA：三个通道给增益表，alpha 用恒等表
        r, g, b, a = im.split()
        mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
        mn = ImageChops.darker(ImageChops.darker(r, g), b)
        sat = ImageChops.subtract(mx, mn)
        # 饱和度 6~26 之间做软过渡，避免白色区域出现硬边
        mask = sat.point(lambda v: 0 if v <= 6 else (255 if v >= 26 else int((v - 6) * 255 / 20)))
        mask = ImageChops.multiply(mask, a)
        merged = Image.composite(bright, im, mask)
        print(f'    调色 {name}: ×{gain:.3f}')
        out.append((name, merged))
    return out


def scaffold(pack, out_dir):
    """新包缺的公共素材补齐：pack.json / 音效 / 徽标。"""
    import json
    import shutil

    src_dir = os.path.join(ROOT, 'assets', 'packs', SCAFFOLD_FROM)
    for sub in ('sfx',):
        s = os.path.join(src_dir, sub)
        d = os.path.join(out_dir, sub)
        if os.path.isdir(s) and not os.path.isdir(d):
            shutil.copytree(s, d)
    emb = os.path.join(out_dir, 'emblem.svg')
    if not os.path.exists(emb):
        try:
            shutil.copyfile(os.path.join(src_dir, 'emblem.svg'), emb)
        except OSError:
            pass

    manifest = os.path.join(out_dir, 'pack.json')
    if os.path.exists(manifest):
        return
    frames = {k: f'{k}.png' for k in ('idle', 'tap', 'wait')
              if os.path.exists(os.path.join(out_dir, f'{k}.png'))}
    data = {
        'name': PACK_NAMES.get(pack, pack),
        'author': 'local',
        'emblem': 'emblem.svg',
        'emblemPos': 'top-right',
        'frames': frames,
        'sounds': {
            'tap': 'sfx/snap.wav',
            'land': 'sfx/thud.wav',
            'cost': 'sfx/coin.wav',
            'wait': 'sfx/alert.wav',
        },
    }
    with open(manifest, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write('\n')


def halo_stats(im, band_max=80, bright=200):
    """轮廓外那圈半透明像素的亮度 —— 深色界面上"白光晕"的量化指标。

    白边（近白像素占比）测的是"颜色有多白"，光晕测的是"低 alpha 的亮像素有多少"：
    后者才是深色底上肉眼看到的那圈雾。alpha ≤ band_max 的像素里，
    亮度 > bright 的数量越多、平均亮度越高，光晕越明显。
    """
    px = im.load()
    w, h = im.size
    band = glow = 0
    tot = 0.0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b, a = px[x, y]
            if 0 < a <= band_max:
                band += 1
                v = (r + g + b) / 3.0
                tot += v
                if v > bright:
                    glow += 1
    return band, glow, (tot / band if band else 0.0)


def check():
    """只统计现有帧的白边残留与光晕，不改任何文件。"""
    import glob
    print(f"{'帧':<28}{'白边占比':>10}{'外圈像素':>10}{'外圈亮像素':>12}{'外圈均亮':>10}")
    print('-' * 72)
    for f in sorted(glob.glob(os.path.join(ROOT, 'assets', 'packs', '*', '*.png'))):
        im = Image.open(f).convert('RGBA')
        ratio, tot = edge_white_ratio(im)
        band, glow, mean = halo_stats(im)
        print(f"{os.path.relpath(f, ROOT):<28}{ratio:>9.1f}%{band:>10}{glow:>12}{mean:>10.1f}")


def main():
    if '--check' in sys.argv:
        check()
        return
    only = sys.argv[1] if len(sys.argv) > 1 else ''
    # 先全部处理，再按包统一调色，最后落盘 —— 调色需要"同一包的所有帧"一起看
    by_pack = {}
    before = {}
    for pack, src, dst, rect, precut in JOBS:
        if only and pack != only:
            continue
        p = next((os.path.join(d, src) for d in SRC_DIRS if os.path.exists(os.path.join(d, src))), '')
        if not p:
            print(f'跳过（找不到）：{src}')
            continue
        old = os.path.join(ROOT, 'assets', 'packs', pack, dst)
        if os.path.exists(old):
            before[(pack, dst)] = edge_white_ratio(Image.open(old).convert('RGBA'))[0]
        im = load_precut(p) if precut else matte(p, rect, HOLES.get((pack, dst)))
        out, bbox = normalize(im)
        by_pack.setdefault(pack, []).append((dst, out, bbox, src, True))

    # 只有原图、没有独立状态图的帧（如 warning）：原地去白边，不重新归一
    for pack, names in STATIC_FRAMES.items():
        if only and pack != only:
            continue
        for name in names:
            p = os.path.join(ROOT, 'assets', 'packs', pack, name)
            if not os.path.exists(p):
                continue
            im = Image.open(p).convert('RGBA')
            before[(pack, name)] = edge_white_ratio(im)[0]
            # ⚠️ 这里只改颜色、不改 alpha：之前为压旧管线的脏边在这里收过 1px，
            # 结果每跑一次就再瘦 1px（805→803→801…）。旧帧没有原图可重抠，
            # 只能靠去污染改色，绝不能重复腐蚀轮廓。
            im.putalpha(tighten_alpha(im.split()[3]))
            by_pack.setdefault(pack, []).append((name, bleed_colors(decontaminate(im, reach=3)), None, '(原地)', False))

    print(f"{'包':<9}{'源文件':<20}{'输出':<12}{'缩放后':<12}{'占高':<8}{'白边(前→后)':<16}{'外圈亮像素':<10}")
    print('-' * 110)
    for pack, items in by_pack.items():
        if len(items) > 1:
            print(f'  [{pack}] 统一曝光')
            fixed = match_exposure([(d, im) for d, im, _b, _s, _n in items])
            items = [(d, fixed[i][1], b, s, n) for i, (d, im, b, s, n) in enumerate(items)]
        out_dir = os.path.join(ROOT, 'assets', 'packs', pack)
        os.makedirs(out_dir, exist_ok=True)
        for dst, im, bbox, src, _n in items:
            im.save(os.path.join(out_dir, dst), 'PNG', optimize=True)
            bb = im.split()[-1].getbbox()
            after = edge_white_ratio(im)[0]
            _band, glow, glow_mean = halo_stats(im)
            prev = before.get((pack, dst))
            delta = f'{prev:.1f}%→{after:.1f}%' if prev is not None else f'—→{after:.1f}%'
            print(f"{pack:<9}{src:<20}{dst:<12}"
                  f"{str(bb[2]-bb[0])+'x'+str(bb[3]-bb[1]):<12}"
                  f"{(bb[3]-bb[1])/CANVAS*100:>5.1f}%  {delta:<16}"
                  f"{glow:>4} (均亮 {glow_mean:.0f})")
        scaffold(pack, out_dir)


if __name__ == '__main__':
    main()
