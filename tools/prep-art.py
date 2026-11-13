#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把生成的立绘规范化为挂件可用的角色帧（支持多个角色包）。

做四件事：
  1. 去底（纯白底 / ChatGPT 的"假透明"棋盘格底都能处理；已经抠好的图可跳过）
  2. 擦掉指定矩形里的水印
  3. 统一到 1024x1024：角色高 88%、底边距 2%、水平居中、宽度不超 94%
  4. 导出 PNG-24（带 alpha）

用法：
    python tools/prep-art.py            # 处理全部
    python tools/prep-art.py chopper    # 只处理指定包

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

# pack: 输出到 assets/packs/<pack>/
# src : 工作区根目录下的原图
# rect: 需要先擦成白色的矩形（水印），None = 没有
# precut: 原图已经带干净 alpha（跳过抠图，只做尺寸归一）
JOBS = [
    # —— 路飞 ——
    ('luffy', '路飞待机.jpg', 'idle.png', (250, 792, 610, 851), False),
    ('luffy', '路飞被点击.png', 'tap.png', None, False),
    ('luffy', '路飞等待回答.png', 'wait.png', None, False),
    ('luffy', '路飞余额告警.png', 'warning.png', None, False),
    # —— 乔巴 ——
    ('chopper', '乔巴待机.png', 'idle.png', None, True),
    ('chopper', '乔巴被点击.png', 'tap.png', None, False),
    ('chopper', '乔巴等待回答.png', 'wait.png', None, False),
    ('chopper', '乔巴余额警告.png', 'warning.png', None, False),
]


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
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.7))

    out = im.convert('RGBA')
    out.putalpha(alpha)
    return out


def load_precut(path):
    """已经抠好的图：把 253/254 这类"接近满"的 alpha 拉满。"""
    im = Image.open(path).convert('RGBA')
    a = im.split()[-1].point(lambda v: 255 if v >= 200 else (0 if v <= 8 else v))
    im.putalpha(a)
    return im


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


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ''
    # 先全部处理，再按包统一调色，最后落盘 —— 调色需要"同一包的所有帧"一起看
    by_pack = {}
    for pack, src, dst, rect, precut in JOBS:
        if only and pack != only:
            continue
        p = os.path.join(ROOT, src)
        if not os.path.exists(p):
            print(f'跳过（找不到）：{src}')
            continue
        im = load_precut(p) if precut else matte(p, rect)
        out, bbox = normalize(im)
        by_pack.setdefault(pack, []).append((dst, out, bbox, src))

    print(f"{'包':<9}{'源文件':<18}{'输出':<12}{'原始内容':<13}{'缩放后':<12}{'占高':<8}{'底边距'}")
    print('-' * 86)
    for pack, items in by_pack.items():
        if len(items) > 1:
            print(f'  [{pack}] 统一曝光')
            fixed = match_exposure([(d, im) for d, im, _b, _s in items])
            items = [(d, fixed[i][1], b, s) for i, (d, im, b, s) in enumerate(items)]
        out_dir = os.path.join(ROOT, 'assets', 'packs', pack)
        os.makedirs(out_dir, exist_ok=True)
        for dst, im, bbox, src in items:
            im.save(os.path.join(out_dir, dst), 'PNG', optimize=True)
            bb = im.split()[-1].getbbox()
            print(f"{pack:<9}{src:<18}{dst:<12}"
                  f"{str(bbox[2]-bbox[0])+'x'+str(bbox[3]-bbox[1]):<13}"
                  f"{str(bb[2]-bb[0])+'x'+str(bb[3]-bb[1]):<12}"
                  f"{(bb[3]-bb[1])/CANVAS*100:>5.1f}%  {CANVAS-bb[3]:>4}px")


if __name__ == '__main__':
    main()
