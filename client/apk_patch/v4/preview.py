#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Approximate visual preview of res/Q9.xml: original (v2 look) vs v4.

NOT an Android renderer - a hand-built mock that reuses the exact dp/sp values
and literal colours compiled into the v4 AXML, so the user can judge whether the
difference will be visible before flashing a 2 GB apk.

Note: the 一键登录 / TapTap strip is drawn in BOTH panels because its visibility
is decided by initView() at runtime (LoginPageType params), not by the XML.
"""
import os
from PIL import Image, ImageDraw, ImageFont

S = 1.7
PANEL_W_DP = 380
PANEL_H_DP = 450
CARD_W = 328
CARD_TOP = 40
FONT_DIR = r'C:\Windows\Fonts'


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

    def agreement(self, y, color):
        d = self.d
        lx = self.cx(48)
        d.rectangle([lx, px(y + 2), lx + px(14), px(y + 16)], outline=color,
                    width=max(1, px(1)))
        d.text((lx + px(20), px(y + 1)), '\u7528\u6237\u534f\u8bae\u4e0e\u9690\u79c1\u653f\u7b56',
               font=ft('msyh.ttc', 12), fill=color)

    def third_party(self, y):
        d = self.d
        f2 = ft('msyh.ttc', 12)
        bx = self.cx(24)
        d.rounded_rectangle([bx, px(y), bx + px(96), px(y + 26)], radius=px(13),
                            outline=(0xD8, 0xDD, 0xE6), width=max(1, px(1)))
        t = '\u4e00\u952e\u767b\u5f55'
        tw = d.textlength(t, font=f2)
        d.text((bx + (px(96) - tw) / 2, px(y + 4)), t, font=f2, fill=(0x33, 0x33, 0x33))
        bx += px(120)
        d.rounded_rectangle([bx, px(y), bx + px(96), px(y + 26)], radius=px(13),
                            fill=(0x0F, 0xCF, 0xC1))


def draw_original(p):
    d = p.d
    p.card(275)
    y = p.header(CARD_TOP)
    y += 7
    p.stroke_field(y, 40, '\u8bf7\u8f93\u5165\u624b\u673a\u53f7')
    y += 40 + 12
    p.stroke_field(y, 40, '\u8bf7\u8f93\u5165\u9a8c\u8bc1\u7801', '\u53d1\u9001')
    y += 40 + 12
    d.rounded_rectangle([p.cx(24), px(y), p.cx(CARD_W - 24), px(y + 40)], radius=px(8),
                        fill=(0x33, 0x33, 0x33))
    f = ft('msyh.ttc', 16)
    t = '\u767b\u5f55'
    d.text((p.card_x + (px(CARD_W) - d.textlength(t, font=f)) / 2, px(y + 9)), t, font=f,
           fill=(255, 255, 255))
    y += 40 + 12
    p.agreement(y, (0xA3, 0xA3, 0xA3))
    y += 17 + 14
    p.third_party(y)


def draw_v4(p):
    d = p.d
    p.card(352)
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
    p.callouts.append((hero + 10, 1))
    y += 1 + 8
    d.rectangle([p.cx(24), px(y), p.cx(CARD_W - 24), px(y + 52)], fill=(0xEA, 0xF0, 0xFB))
    d.text((p.cx(40), px(y + 17)), '\u8bf7\u8f93\u5165\u5361\u5bc6', font=ft('msyh.ttc', 16),
           fill=(0x9A, 0xA3, 0xB2))
    p.callouts.append((y + 26, 2))
    y += 52 + 8 + 12
    d.rectangle([p.cx(24), px(y), p.cx(CARD_W - 24), px(y + 52)], fill=(0x2F, 0x6F, 0xED))
    fb = ft('msyhbd.ttc', 18)
    t = '\u767b \u5f55'
    d.text((p.card_x + (px(CARD_W) - d.textlength(t, font=fb)) / 2, px(y + 13)), t, font=fb,
           fill=(255, 255, 255))
    p.callouts.append((y + 26, 3))
    y += 52 + 16
    p.agreement(y, (0x9A, 0xA3, 0xB2))
    y += 17 + 14
    p.third_party(y)


def main():
    w = px(PANEL_W_DP) * 2 + px(20)
    h = px(PANEL_H_DP)
    img = Image.new('RGB', (w, h), (6, 12, 26))
    left = Panel(img, 0)
    right = Panel(img, px(PANEL_W_DP) + px(20))
    left.bg()
    right.bg()
    draw_original(left)
    draw_v4(right)

    d = ImageDraw.Draw(img)
    for y_dp, num in right.callouts:
        r = px(10)
        cx_ = right.card_x + px(CARD_W) + px(15)
        cy_ = px(y_dp)
        d.ellipse([cx_ - r, cy_ - r, cx_ + r, cy_ + r], fill=(0xFF, 0x6B, 0x35))
        fc = ft('msyhbd.ttc', 12)
        tw = d.textlength(str(num), font=fc)
        d.text((cx_ - tw / 2, cy_ - px(6)), str(num), font=fc, fill=(255, 255, 255))

    d.text((px(12), px(10)), '\u539f\u7248 / v2\uff08\u4f60\u73b0\u5728\u8fd9\u4e2a\u5305\uff09',
           font=ft('msyhbd.ttc', 13), fill=(0xB9, 0xC6, 0xDA))
    d.text((px(PANEL_W_DP) + px(32), px(10)), 'v4\uff08\u5361\u5bc6\u767b\u5f55\uff09',
           font=ft('msyhbd.ttc', 13), fill=(0x8F, 0xC0, 0xFF))

    legend = ['1  \u65b0\u589e\u6807\u9898\uff08\u52a0\u7c97 21sp\uff09+\u526f\u6807\u9898+\u5206\u9694\u7ebf',
              '2  \u9a8c\u8bc1\u7801\u6574\u884c gone\uff0c\u53ea\u5269\u4e00\u4e2a 52dip \u8f93\u5165\u6846\uff08\u6d45\u84dd\u5e95\uff0c\u65e0\u5706\u89d2\uff09',
              '3  \u5b9e\u8272\u84dd\u6309\u94ae #FF2F6FED\uff0c\u767d\u5b57\u52a0\u7c97 18sp\uff0c\u9ad8 52dip']
    fl = ft('msyh.ttc', 11)
    top = h - px(52)
    d.rectangle([0, top - px(8), w, h], fill=(4, 9, 20))
    for i, s in enumerate(legend):
        d.text((px(12), top + i * px(14)), s, font=fl, fill=(0x9A, 0xA9, 0xC0))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preview_v4.png')
    img.save(out)
    print('saved', out, img.size)


if __name__ == '__main__':
    main()
