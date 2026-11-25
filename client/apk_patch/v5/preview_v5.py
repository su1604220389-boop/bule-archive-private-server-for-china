#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPROXIMATE visual preview for v5: v4 (left) vs v5 (right).

!!! 这是近似图 —— NOT an Android renderer !!!
A hand-built mock that reuses the exact dp/sp values and literal colours that are
compiled into res_Q9_v5.axml, so the user can judge the *geometry* and *colours*
before flashing a 2 GB apk.  Font metrics, the RadioButton ring size, the drawable
rounding of the card and any system font scaling are approximations only.

Why the 一键登录 / TapTap strip is drawn in both panels: its visibility is decided
by initView() at runtime (LoginPageType params), not by the XML — v4 and v5 both
left that node untouched.
"""
import os
from PIL import Image, ImageDraw, ImageFont

S = 1.7                    # px per dp
PANEL_W_DP = 380
PANEL_H_DP = 580
CARD_W = 328
CARD_TOP = 58
FONT_DIR = r'C:\Windows\Fonts'

ACCENT = (0x2F, 0x6F, 0xED)
STRIP_BG = (0xF1, 0xF5, 0xFC)


def ft(name, dp):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), max(8, int(round(dp * S))))


def px(v):
    return int(round(v * S))


class Panel(object):
    def __init__(self, img, ox):
        self.d = ImageDraw.Draw(img)
        self.ox = ox
        self.card_x = ox + (px(PANEL_W_DP) - px(CARD_W)) // 2
        self.callouts = []

    def cx(self, dp_from_card_left):
        return self.card_x + px(dp_from_card_left)

    def text_c(self, y_dp, s, font, fill):
        tw = self.d.textlength(s, font=font)
        self.d.text((self.card_x + (px(CARD_W) - tw) / 2, px(y_dp)), s, font=font, fill=fill)

    def bg(self):
        h = px(PANEL_H_DP)
        for y in range(h):
            t = y / max(1, h - 1)
            self.d.line([(self.ox, y), (self.ox + px(PANEL_W_DP), y)],
                        fill=(int(0x1A + (0x0C - 0x1A) * t),
                              int(0x2A + (0x14 - 0x2A) * t),
                              int(0x4E + (0x28 - 0x4E) * t)))

    def card(self, h_dp):
        self.d.rounded_rectangle([self.card_x, px(CARD_TOP),
                                  self.card_x + px(CARD_W), px(CARD_TOP + h_dp)],
                                 radius=px(10), fill=(255, 255, 255))

    def header(self, y):
        d = self.d
        bx, by = self.cx(20), px(y + 24)
        d.line([(bx + px(5), by - px(6)), (bx - px(3), by), (bx + px(5), by + px(6))],
               fill=(0x5A, 0x60, 0x6E), width=max(2, px(1.4)))
        lx = self.card_x + (px(CARD_W) - px(120)) // 2
        d.rounded_rectangle([lx, px(y + 16), lx + px(120), px(y + 44)], radius=px(4),
                            fill=(0x1B, 0x3A, 0x8A))
        f = ft('msyhbd.ttc', 8)
        t = 'BLUE ARCHIVE'
        d.text((lx + (px(120) - d.textlength(t, font=f)) / 2, px(y + 25)), t, font=f,
               fill=(255, 255, 255))
        cx_, cy_ = self.cx(CARD_W - 24), px(y + 24)
        for s in (+1, -1):
            d.line([(cx_ - px(6), cy_ - s * px(6)), (cx_ + px(6), cy_ + s * px(6))],
                   fill=(0x5A, 0x60, 0x6E), width=max(2, px(1.4)))
        return y + 12 + 24 + 7

    # ----------------------------------------------------- v5 new widget ----
    def radio_strip(self, y, h=44):
        """RadioGroup#FFF1F5FC, 2x RadioButton (40dip rows, 2dip group padding)."""
        d = self.d
        x0, x1 = self.cx(24), self.cx(CARD_W - 24)
        d.rectangle([x0, px(y), x1, px(y + h)], fill=STRIP_BG)

        half = (CARD_W - 48) / 2.0
        fr = ft('msyh.ttc', 15)
        for n, (txt, checked) in enumerate((('\u6e38\u5ba2\u767b\u5f55', True),
                                            ('\u5361\u5bc6\u767b\u5f55', False))):
            cx_ = 24 + half * n + half / 2.0
            tw = d.textlength(txt, font=fr) / S
            content = 20 + 4 + tw
            sx = cx_ - content / 2.0
            ccx, ccy = sx + 10, y + h / 2.0
            d.ellipse([self.cx(ccx) - px(9), px(ccy) - px(9),
                       self.cx(ccx) + px(9), px(ccy) + px(9)],
                      outline=ACCENT, width=max(2, px(1.8)))
            if checked:
                d.ellipse([self.cx(ccx) - px(4.6), px(ccy) - px(4.6),
                           self.cx(ccx) + px(4.6), px(ccy) + px(4.6)],
                          fill=ACCENT)
            d.text((self.cx(sx + 24), px(ccy - 10)), txt, font=fr, fill=(0x2B, 0x34, 0x45))
        return y + h

    def stroke_field(self, y, h, hint, right=None):
        d = self.d
        x0, x1 = self.cx(24), self.cx(CARD_W - 24)
        d.rounded_rectangle([x0, px(y), x1, px(y + h)], radius=px(8),
                            outline=(0xEA, 0xEA, 0xEA), width=max(1, px(1)))
        d.text((x0 + px(12), px(y + (h - 14) / 2 - 2)), hint, font=ft('msyh.ttc', 14),
               fill=(0xB9, 0xB9, 0xB9))
        if right:
            lx = x1 - px(60)
            d.line([(lx - px(8), px(y + h / 2 - 10)), (lx - px(8), px(y + h / 2 + 10))],
                   fill=(0xEA, 0xEA, 0xEA), width=max(1, px(1)))
            tw = d.textlength(right, font=ft('msyh.ttc', 14))
            d.text((lx + (px(60) - tw) / 2, px(y + (h - 14) / 2 - 2)), right,
                   font=ft('msyh.ttc', 14), fill=(0xB9, 0xB9, 0xB9))

    def solid_field(self, y, h, hint):
        d = self.d
        d.rectangle([self.cx(24), px(y), self.cx(CARD_W - 24), px(y + h)],
                    fill=(0xEA, 0xF0, 0xFB))
        d.text((self.cx(40), px(y + (h - 16) / 2 - 1)), hint, font=ft('msyh.ttc', 16),
               fill=(0x9A, 0xA3, 0xB2))

    def agreement(self, y, color):
        d = self.d
        lx = self.cx(48)
        d.rectangle([lx, px(y + 2), lx + px(14), px(y + 16)], outline=color,
                    width=max(1, px(1)))
        d.text((lx + px(20), px(y + 1)), '\u7528\u6237\u534f\u8bae\u4e0e\u9690\u79c1\u653f\u7b56',
               font=ft('msyh.ttc', 12), fill=color)

    def third_party(self, y, dim=False):
        d = self.d
        f2 = ft('msyh.ttc', 12)
        edge = (0xE2, 0xE6, 0xEE) if dim else (0xD8, 0xDD, 0xE6)
        ink = (0x9A, 0xA3, 0xB2) if dim else (0x33, 0x33, 0x33)
        bx = self.cx(24)
        d.rounded_rectangle([bx, px(y), bx + px(96), px(y + 26)], radius=px(13),
                            outline=edge, width=max(1, px(1)))
        t = '\u4e00\u952e\u767b\u5f55'
        tw = d.textlength(t, font=f2)
        d.text((bx + (px(96) - tw) / 2, px(y + 4)), t, font=f2, fill=ink)
        bx += px(120)
        d.rounded_rectangle([bx, px(y), bx + px(96), px(y + 26)], radius=px(13),
                            fill=(0x0F, 0xCF, 0xC1) if not dim else (0x9A, 0xE8, 0xE4))


def draw_v4(p):
    """exactly the v4 look (no entry switch)."""
    d = p.d
    p.card(406 - 54)
    y = CARD_TOP + 8
    y = p.header(y)
    hero = y + 6
    p.text_c(hero, '\u5361\u5bc6\u767b\u5f55', ft('msyhbd.ttc', 21), (0x12, 0x20, 0x3A))
    y = hero + 29 + 5
    p.text_c(y, '\u65e0\u9700\u9a8c\u8bc1\u7801\uff0c\u8f93\u5165\u5361\u5bc6\u76f4\u63a5\u767b\u5f55',
             ft('msyh.ttc', 12), (0x8A, 0x94, 0xA6))
    y += 17 + 14
    d.line([(p.cx(24), px(y)), (p.cx(CARD_W - 24), px(y))], fill=(0xE7, 0xEC, 0xF5),
           width=max(1, px(1)))
    y += 1 + 8
    p.solid_field(y, 52, '\u8bf7\u8f93\u5165\u5361\u5bc6')
    y += 52 + 8 + 12
    d.rectangle([p.cx(24), px(y), p.cx(CARD_W - 24), px(y + 52)], fill=ACCENT)
    fb = ft('msyhbd.ttc', 18)
    t = '\u767b \u5f55'
    d.text((p.card_x + (px(CARD_W) - d.textlength(t, font=fb)) / 2, px(y + 13)), t, font=fb,
           fill=(255, 255, 255))
    y += 52 + 16
    p.agreement(y, (0x9A, 0xA3, 0xB2))
    y += 17 + 14
    p.third_party(y, dim=True)


def draw_v5(p):
    d = p.d
    p.card(406)
    y = CARD_TOP + 8
    y = p.header(y)
    y += 10
    y = p.radio_strip(y)                       # <-- the new strip
    p.callouts.append((y - 22, 1))
    hero = y + 6
    p.text_c(hero, '\u5361\u5bc6\u767b\u5f55', ft('msyhbd.ttc', 21), (0x12, 0x20, 0x3A))
    p.callouts.append((hero + 10, 2))
    y = hero + 29 + 5
    p.text_c(y, '\u65e0\u9700\u9a8c\u8bc1\u7801\uff0c\u8f93\u5165\u5361\u5bc6\u76f4\u63a5\u767b\u5f55',
             ft('msyh.ttc', 12), (0x8A, 0x94, 0xA6))
    y += 17 + 14
    d.line([(p.cx(24), px(y)), (p.cx(CARD_W - 24), px(y))], fill=(0xE7, 0xEC, 0xF5),
           width=max(1, px(1)))
    y += 1 + 8
    p.solid_field(y, 52, '\u8bf7\u8f93\u5165\u5361\u5bc6')
    p.callouts.append((y + 26, 3))
    y += 52 + 8 + 12
    d.rectangle([p.cx(24), px(y), p.cx(CARD_W - 24), px(y + 52)], fill=ACCENT)
    fb = ft('msyhbd.ttc', 18)
    t = '\u767b \u5f55'
    d.text((p.card_x + (px(CARD_W) - d.textlength(t, font=fb)) / 2, px(y + 13)), t, font=fb,
           fill=(255, 255, 255))
    p.callouts.append((y + 26, 4))
    y += 52 + 16
    p.agreement(y, (0x9A, 0xA3, 0xB2))
    y += 17 + 14
    p.third_party(y, dim=True)


def main():
    w = px(PANEL_W_DP) * 2 + px(20)
    h = px(PANEL_H_DP)
    img = Image.new('RGB', (w, h), (6, 12, 26))
    left = Panel(img, 0)
    right = Panel(img, px(PANEL_W_DP) + px(20))
    left.bg()
    right.bg()
    draw_v4(left)
    draw_v5(right)

    d = ImageDraw.Draw(img)
    # ---- callout numerals ----
    for y_dp, num in right.callouts:
        r = px(10)
        cx_ = right.card_x + px(CARD_W) + px(15)
        cy_ = px(y_dp)
        d.ellipse([cx_ - r, cy_ - r, cx_ + r, cy_ + r], fill=(0xFF, 0x6B, 0x35))
        fc = ft('msyhbd.ttc', 12)
        tw = d.textlength(str(num), font=fc)
        d.text((cx_ - tw / 2, cy_ - px(6)), str(num), font=fc, fill=(255, 255, 255))

    # ---- headers ----
    d.text((px(12), px(14)), 'v4\uff08\u5f53\u524d\u5305\uff1a\u65e0\u5165\u53e3\uff09',
           font=ft('msyhbd.ttc', 13), fill=(0xB9, 0xC6, 0xDA))
    d.text((px(PANEL_W_DP) + px(32), px(14)),
           'v5\uff08\u672c\u6b21\uff1a\u4e24\u4e2a\u5165\u53e3\u56de\u6765\u4e86\uff09',
           font=ft('msyhbd.ttc', 13), fill=(0x8F, 0xC0, 0xFF))
    # ---- the "approximate" disclaimer, impossible to miss ----
    d.rectangle([0, 0, w, px(2)], fill=(0xFF, 0x6B, 0x35))
    d.text((px(PANEL_W_DP) + px(32), px(36)),
           '\u8fd1\u4f3c\u56fe\uff1aPIL \u624b\u7ed8\uff0c\u975e Android \u771f\u5b9e\u6e32\u67d3',
           font=ft('msyh.ttc', 11), fill=(0xFF, 0x9A, 0x6B))
    d.text((px(12), px(36)),
           '\uff08\u540c\u6837\u662f\u8fd1\u4f3c\u56fe\uff09',
           font=ft('msyh.ttc', 11), fill=(0x7E, 0x8B, 0xA0))

    # ---- legend ----
    legend = [
        '1  \u65b0\u589e\uff1aRadioGroup + 2x RadioButton\uff08"\u6e38\u5ba2\u767b\u5f55" / "\u5361\u5bc6\u767b\u5f55"\uff09\uff0c'
        '\u6e38\u5ba2\u9ed8\u8ba4\u9009\u4e2d\u3002\u4ec5 XML \u5b57\u9762\u91cf\uff0c\u65e0 id\u3001\u65e0\u65b0\u8d44\u6e90\u3002',
        '2  \u6807\u9898 21sp \u52a0\u7c97 + \u526f\u6807\u9898 + \u5206\u9694\u7ebf\uff1a\u4e0e v4 \u5b8c\u5168\u4e00\u81f4\uff08\u672c\u6b21\u672a\u6539\uff09\u3002',
        '3  \u9a8c\u8bc1\u7801\u6574\u884c\u4ecd gone + et_phone_code \u4ecd\u9884\u586b "000000"\uff1b'
        '\u8f93\u5165\u6846 52dip \u6d45\u84dd\u5b9e\u5e95\uff0chint="\u8bf7\u8f93\u5165\u5361\u5bc6"\u3002',
        '4  \u6309\u94ae #FF2F6FED \u767d\u5b57\u52a0\u7c97 18sp\uff0c\u9ad8 52dip\uff1a\u4e0e v4 \u5b8c\u5168\u4e00\u81f4\u3002',
        '\u25b3  \u4e24\u4e2a\u9009\u9879\u662f\u7eaf\u5c55\u793a\uff1a\u70b9\u4e86\u53ea\u6539\u81ea\u5df1\u7684\u9009\u4e2d\u6001\uff0c'
        '\u4e0d\u4f1a\u5207\u6362\u9875\u9762\u903b\u8f91\uff08\u90a3\u8981\u6539 dex\uff0c\u7ea2\u7ebf\uff09\u3002',
        '\u2192  \u4e09\u65b9\u767b\u5f55\u6761\uff08\u4e00\u952e/TapTap\uff09\u7684\u663e\u9690\u7531 initView() \u8fd0\u884c\u65f6\u51b3\u5b9a\uff0c'
        'v4/v5 \u90fd\u6ca1\u52a8\u5b83\uff0c\u753b\u5728\u8fd9\u91cc\u53ea\u4e3a\u5b8c\u6574\u3002',
    ]
    fl = ft('msyh.ttc', 11)
    top = h - px(96)
    d.rectangle([0, top - px(8), w, h], fill=(4, 9, 20))
    for i, s in enumerate(legend):
        d.text((px(12), top + i * px(14)), s, font=fl, fill=(0x9A, 0xA9, 0xC0))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preview_v5.png')
    img.save(out)
    print('saved', out, img.size)


if __name__ == '__main__':
    main()
