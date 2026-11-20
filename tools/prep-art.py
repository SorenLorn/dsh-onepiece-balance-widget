#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把生成的立绘规范化为挂件可用的角色帧（支持多个角色包）。

做五件事：
  1. 去底（纯白底 / ChatGPT 的"假透明"棋盘格底都能处理；已经抠好的图可跳过）
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

CANVAS = 1024          # 输出画布边长
FILL = 0.88            # 角色高度占画布比例
MAXW = 0.94            # 角色宽度上限（带鹿角/大翅膀的角色靠这条兜底）
BOTTOM = 0.02          # 底部留白比例

BLEED = 10             # 边缘带颜色扩散半径（源图像素）；要 > 缩小时的滤波支撑半径

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

# 没有对应原图、只能原地去白边的帧（已经归一过，不再走缩放，避免二次重采样）
STATIC_FRAMES = {
    'luffy': ['warning.png'],
    'chopper': ['warning.png'],
}

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


def bleed_colors(im, radius=BLEED):
    """把实心区的颜色向外扩散到 alpha 边缘带（defringe）。

    为什么不直接"按 alpha 反算原色"：纯白底抠图后边缘像素是 c = a*原色 + (1-a)*白，
    反算要除以 alpha，alpha 很小时是除零噪声；而缩小时那圈近白像素还会被滤波
    摊到描边外，深色背景上就是一圈亮边。
    这里改成"用最近的角色色覆盖边缘带"，透明区也带上角色色，
    于是无论是直接显示还是缩放，边缘混出来的都是角色色而不是白色。
    """
    w, h = im.size
    alpha = im.split()[3]
    ab = alpha.tobytes()
    px = im.load()
    known = bytearray(w * h)
    frontier = []
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    # 种子只取"贴着边缘的实心像素"，避免把整块实心区都塞进队列
    for y in range(h):
        base = y * w
        for x in range(w):
            if ab[base + x] >= 250:
                known[base + x] = 1
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
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and not known[ny * w + nx]:
                    cand[(nx, ny)] = 1
        if not cand:
            break
        cand = list(cand)
        # 取色只认「上一层及更早」的像素，避免同层之间互相传染还没上色的白
        for (x, y) in cand:
            sr = sg = sb = n = 0
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and known[ny * w + nx]:
                    r, g, b, _a = px[nx, ny]
                    sr += r
                    sg += g
                    sb += b
                    n += 1
            if n:
                px[x, y] = (sr // n, sg // n, sb // n, px[x, y][3])
        for (x, y) in cand:
            known[y * w + x] = 1
        frontier = cand
    return im


def drop_enclosed(cand, im, min_area=8):
    """把"被角色围住、与画布边缘不连通"的背景块也去掉。

    抬起的胳膊和下巴之间会围出一块背景，从画布边缘的洪水填充到不了那儿，
    它就留成实心白块。实测特征（灰像素占比 / 亮度标准差）：
        腋下背景块 43% / 10.1；眼睛 4-7% / 6.4-7.1；牙齿 3-4% / 4.8-5.7
    所以用「灰占比 > 20% 或标准差 > 9」判定；小于 400px 的小块另有一套判定。
    """
    w, h = cand.size
    px = cand.load()
    ip = im.load()
    seen = bytearray(w * h)
    for y0 in range(h):
        for x0 in range(w):
            if px[x0, y0] != 255 or seen[y0 * w + x0]:
                continue
            q = deque([(x0, y0)])
            seen[y0 * w + x0] = 1
            pts = []
            s = s2 = 0.0
            gray = 0
            while q:
                x, y = q.popleft()
                r, g, b = ip[x, y]
                v = (r + g + b) / 3.0
                s += v
                s2 += v * v
                if v < 245:
                    gray += 1
                pts.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        if px[nx, ny] == 255 and not seen[j]:
                            seen[j] = 1
                            q.append((nx, ny))
            n = len(pts)
            if n < min_area:
                continue
            mean = s / n
            sd = max(0.0, s2 / n - mean * mean) ** 0.5
            gray_frac = gray / n
            if n < 400:
                # 小块：正常画面的白色块都远大于 400px（眼睛/牙齿约 4000px），
                # 这个区间里只有"背景残渣"和"极扁的纯白"两种。
                if gray_frac > 0.25 or (sd < 2.0 and mean > 248):
                    for (x, y) in pts:
                        px[x, y] = 128
                continue
            if gray_frac > 0.20 or sd > 9.0:
                for (x, y) in pts:
                    px[x, y] = 128


def matte(path, clear_rect=None):
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

    drop_enclosed(cand, im)

    alpha = cand.point(lambda v: 0 if v == 128 else 255)
    alpha = alpha.filter(ImageFilter.MinFilter(3))       # 收 1px，去掉描边外侧的晕边
    alpha = alpha.point(lambda v: 0 if v < 8 else 255)   # 灭掉残留的极淡噪点
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.7))  # 只留 1px 抗锯齿过渡

    out = im.convert('RGBA')
    out.putalpha(alpha)
    return bleed_colors(out)


def load_precut(path):
    """已经抠好的图：把 253/254 这类"接近满"的 alpha 拉满，再补白边。"""
    im = Image.open(path).convert('RGBA')
    a = im.split()[-1].point(lambda v: 255 if v >= 200 else (0 if v <= 8 else v))
    im.putalpha(a)
    return bleed_colors(im)


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


def check():
    """只统计现有帧的白边残留，不改任何文件。"""
    import glob
    print(f"{'帧':<28}{'白边占比':>10}{'边缘样本':>10}")
    print('-' * 50)
    for f in sorted(glob.glob(os.path.join(ROOT, 'assets', 'packs', '*', '*.png'))):
        im = Image.open(f).convert('RGBA')
        ratio, tot = edge_white_ratio(im)
        print(f"{os.path.relpath(f, ROOT):<28}{ratio:>9.1f}%{tot:>10}")


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
        p = os.path.join(ROOT, src)
        if not os.path.exists(p):
            print(f'跳过（找不到）：{src}')
            continue
        old = os.path.join(ROOT, 'assets', 'packs', pack, dst)
        if os.path.exists(old):
            before[(pack, dst)] = edge_white_ratio(Image.open(old).convert('RGBA'))[0]
        im = load_precut(p) if precut else matte(p, rect)
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
            by_pack.setdefault(pack, []).append((name, bleed_colors(im), None, '(原地)', False))

    print(f"{'包':<9}{'源文件':<20}{'输出':<12}{'缩放后':<12}{'占高':<8}{'白边(前→后)'}")
    print('-' * 96)
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
            prev = before.get((pack, dst))
            delta = f'{prev:.1f}%→{after:.1f}%' if prev is not None else f'—→{after:.1f}%'
            print(f"{pack:<9}{src:<20}{dst:<12}"
                  f"{str(bb[2]-bb[0])+'x'+str(bb[3]-bb[1]):<12}"
                  f"{(bb[3]-bb[1])/CANVAS*100:>5.1f}%  {delta}")
        scaffold(pack, out_dir)


if __name__ == '__main__':
    main()
