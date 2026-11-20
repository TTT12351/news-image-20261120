#!/usr/bin/env python3
"""Draw a one-page newspaper front page summing up the world news of
Friday 20 November 2026, and write it to /output/entry.png.

Pure Python 3 standard library: the picture is painted into an RGB
framebuffer with a hand-made 5x7 bitmap font and saved with a small
deterministic PNG encoder (zlib + struct). No network, no files read,
same bytes on every run.

News selection (reported 20 Nov 2026, cross-checked across Reuters,
Just Security's Early Edition, SCMP, Dawn and One Turn's day page):
ICJ genocide ruling on Myanmar, the Trump-Xi-Putin Shenzhen summit,
Russian strikes on Kyiv, the Anthropic record IPO amid a global
sell-off, a Houthi missile hitting Riyadh's PIF tower, the Iran war
stalemate in Washington, COP31 dropping fossil fuels from its draft,
and Israeli troops crossing Gaza's Yellow Line.
"""

import os
import struct
import zlib

W = 1024
H = 1024

PAPER = (247, 243, 232)
INK = (17, 17, 17)
WHITE = (255, 255, 255)
RED = (185, 28, 28)
BLUE = (29, 78, 216)
GREEN = (21, 128, 61)
AMBER = (180, 83, 9)
PURPLE = (126, 34, 206)
TEAL = (15, 118, 110)
GREY = (90, 90, 90)
LIGHT = (232, 224, 205)

# 5x7 bitmap font: each glyph is 7 rows, each row a 5-bit mask,
# bit 4 is the leftmost pixel.
FONT = {
    "A": (14, 17, 17, 31, 17, 17, 17),
    "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (28, 18, 17, 17, 17, 18, 28),
    "E": (31, 16, 16, 30, 16, 16, 31),
    "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15),
    "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14),
    "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17),
    "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17),
    "N": (17, 17, 25, 21, 19, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14),
    "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13),
    "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),
    "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14),
    "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 21, 10),
    "X": (17, 10, 4, 4, 4, 10, 17),
    "Y": (17, 10, 4, 4, 4, 4, 4),
    "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14),
    "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (31, 2, 4, 2, 1, 17, 14),
    "4": (2, 6, 10, 18, 31, 2, 2),
    "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14),
    "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 2, 12),
    " ": (0, 0, 0, 0, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 12, 12),
    ",": (0, 0, 0, 0, 12, 4, 8),
    "'": (4, 4, 8, 0, 0, 0, 0),
    "-": (0, 0, 0, 31, 0, 0, 0),
    ":": (0, 12, 12, 0, 12, 12, 0),
    ";": (0, 12, 12, 0, 12, 4, 8),
    "/": (1, 1, 2, 4, 8, 16, 16),
    "%": (25, 26, 2, 4, 8, 11, 19),
    "$": (4, 15, 20, 14, 5, 30, 4),
    "+": (0, 4, 4, 31, 4, 4, 0),
    "!": (4, 4, 4, 4, 4, 0, 4),
    "?": (14, 17, 1, 2, 4, 0, 4),
    "(": (2, 4, 8, 8, 8, 4, 2),
    ")": (8, 4, 2, 2, 2, 4, 8),
    "&": (12, 18, 20, 8, 21, 18, 13),
    '"': (10, 10, 10, 0, 0, 0, 0),
    "*": (0, 21, 14, 31, 14, 21, 0),
}


def norm(text):
    out = []
    for ch in text.upper():
        if ch in FONT:
            out.append(ch)
        elif ch in "\u2019\u2018":
            out.append("'")
        elif ch in "\u2013\u2014":
            out.append("-")
        elif ch == "\u2022":
            out.append("*")
        else:
            out.append(" ")
    return "".join(out)


class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(bg) * (w * h))

    def rect(self, x, y, rw, rh, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + rw)
        y1 = min(self.h, y + rh)
        if x0 >= x1 or y0 >= y1:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            off = (yy * self.w + x0) * 3
            self.px[off:off + len(row)] = row

    def text_width(self, text, scale, bold=False):
        text = norm(text)
        if not text:
            return 0
        adv = 6 * scale + (scale if bold else 0)
        return len(text) * adv - scale

    def draw_text(self, x, y, text, scale, color, bold=False):
        text = norm(text)
        adv = 6 * scale + (scale if bold else 0)
        cx = x
        for ch in text:
            glyph = FONT.get(ch, FONT[" "])
            for r in range(7):
                bits = glyph[r]
                for c in range(5):
                    if bits & (16 >> c):
                        self.rect(cx + c * scale, y + r * scale,
                                  scale + (scale if bold else 0), scale, color)
            cx += adv
        return cx - x

    def draw_centered(self, cx, y, text, scale, color, bold=False):
        w = self.text_width(text, scale, bold)
        return self.draw_text(cx - w // 2, y, text, scale, color, bold)


def wrap(text, scale, max_width, bold=False):
    words = norm(text).split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if cur and Canvas.text_width(None, trial, scale, bold) > max_width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


# Canvas.text_width is used as a helper before any canvas exists.
def _text_width(self, text, scale, bold=False):
    text = norm(text or "")
    if not text:
        return 0
    adv = 6 * scale + (scale if bold else 0)
    return len(text) * adv - scale


Canvas.text_width = _text_width


def para(cv, x, y, text, scale, color, max_width, bold=False, leading=12):
    lines = wrap(text, scale, max_width, bold)
    step = 7 * scale + leading
    for line in lines:
        cv.draw_text(x, y, line, scale, color, bold)
        y += step
    return y


def story_box(cv, x, y, w, tag, tag_color, headline, body):
    cv.rect(x, y, w, 4, tag_color)
    tw = cv.text_width(tag, 2, True)
    cv.rect(x, y + 10, tw + 16, 22, tag_color)
    cv.draw_text(x + 8, y + 14, tag, 2, WHITE, True)
    y += 42
    y = para(cv, x, y, headline, 3, INK, w, True, 6)
    y += 3
    y = para(cv, x, y, body, 2, GREY, w, False, 5)
    return y


def build():
    cv = Canvas(W, H, PAPER)
    m = 36
    right = W - m

    # Masthead
    cv.rect(0, 0, W, 52, INK)
    cv.draw_text(m, 14, "THE WORLD IN ONE DAY", 3, WHITE, True)
    rtxt = "ONE IMAGE - ALL THE NEWS"
    cv.draw_text(right - cv.text_width(rtxt, 2), 18, rtxt, 2, LIGHT)
    cv.draw_centered(W // 2, 62, "GLOBAL DAILY", 5, INK, True)
    cv.draw_centered(W // 2, 108, "FRIDAY - NOVEMBER 20 - 2026", 4, RED, True)
    cv.rect(m, 144, right - m, 3, INK)
    cv.rect(m, 151, right - m, 1, INK)

    # Lead story: the ICJ genocide ruling
    y = 164
    cv.rect(m, y, 150, 26, RED)
    cv.draw_text(m + 8, y + 6, "TOP STORY", 2, WHITE, True)
    cv.draw_text(m + 170, y + 6, "THE HAGUE - JUSTICE", 2, RED, True)
    y += 40
    y = para(cv, m, y,
             "WORLD COURT RULES MYANMAR COMMITTED GENOCIDE "
             "AGAINST THE ROHINGYA",
             4, INK, right - m, True, 8)
    y += 2
    y = para(cv, m, y,
             "THE UN'S TOP COURT FOUND MYANMAR RESPONSIBLE FOR GENOCIDE "
             "AGAINST ITS ROHINGYA MINORITY - A FIRST RULING OF ITS KIND "
             "AGAINST A STATE.",
             2, GREY, right - m, False, 5)
    cv.rect(m, y + 2, right - m, 2, INK)
    y += 14

    # Second story: Shenzhen trilateral summit, full width band
    cv.rect(m, y, right - m, 104, (235, 240, 250))
    cv.rect(m, y, 6, 104, BLUE)
    yy = para(cv, m + 20, y + 10,
              "TRUMP, XI AND PUTIN HOLD FIRST THREE-WAY SUMMIT IN SHENZHEN",
              3, BLUE, right - m - 40, True, 6)
    para(cv, m + 20, yy + 1,
         "THE US, CHINESE AND RUSSIAN LEADERS SIGNED A FOUR-POINT PEACE "
         "DECLARATION AT APEC - EUROPE AND UKRAINE WERE NOT AT THE TABLE.",
         2, INK, right - m - 40, False, 5)
    y += 114

    # Two-column story grid
    col_w = (right - m - 24) // 2
    lx = m
    rx = m + col_w + 24
    gy = y
    y1 = story_box(cv, lx, gy, col_w, "UKRAINE WAR", RED,
                   "RUSSIA HITS KYIV BRIDGES, EMBASSIES",
                   "OVERNIGHT MISSILES KILLED AT LEAST 8 AND INJURED 28 "
                   "ACROSS NINE REGIONS; AUSTRIAN AND DUTCH EMBASSIES WERE "
                   "DAMAGED.")
    y2 = story_box(cv, rx, gy, col_w, "MIDDLE EAST", AMBER,
                   "HOUTHI MISSILE HITS RIYADH TOWER",
                   "THE MISSILE BLEW OUT WINDOWS ACROSS EIGHT FLOORS OF "
                   "THE PIF TOWER IN RIYADH'S FINANCIAL DISTRICT - THE "
                   "SECOND ATTACK THIS MONTH.")
    gy = max(y1, y2) + 12
    y1 = story_box(cv, lx, gy, col_w, "IRAN WAR", PURPLE,
                   "TRUMP HOLDS OFF ON IRAN STRIKES",
                   "ANY DECISION ON NEW STRIKES IS PUT OFF UNTIL THE NEW "
                   "YEAR, AND THE SENATE BLOCKED A BID TO CURB THE WAR "
                   "51-48. COST SO FAR: $48.3BN.")
    y2 = story_box(cv, rx, gy, col_w, "MARKETS - AI", BLUE,
                   "ANTHROPIC IPO: $81BN RECORD",
                   "HISTORY'S BIGGEST DEBUT CLOSED UP 17% AT $97 - YET THE "
                   "S&P 500 FELL 2% FOR A FIFTH DAY AND TOKYO'S NIKKEI "
                   "LOST 4.8%.")
    gy = max(y1, y2) + 10

    # Numbers strip
    cv.rect(m, gy, right - m, 2, INK)
    gy += 8
    stats = [("$81BN", "BIGGEST IPO EVER"),
             ("-2%", "S&P 500, 5TH FALL"),
             ("51-48", "SENATE IRAN VOTE"),
             ("8 DEAD", "KYIV OVERNIGHT")]
    sw = (right - m) // 4
    for i, (big, small) in enumerate(stats):
        sx = m + i * sw
        cv.draw_centered(sx + sw // 2, gy, big, 3, RED, True)
        cv.draw_centered(sx + sw // 2, gy + 26, small, 1, GREY, True)
    gy += 46

    # Briefing lines: Gaza and COP31
    cv.rect(m, gy, right - m, 1, INK)
    gy += 8
    cv.draw_centered(W // 2, gy,
                     "GAZA: ISRAELI TROOPS CROSS YELLOW LINE, "
                     "FIRST SINCE TRUCE", 2, TEAL, True)
    gy += 24
    cv.draw_centered(W // 2, gy,
                     "COP31: FOSSIL-FUEL PHASE-OUT DROPPED FROM "
                     "DRAFT DEAL IN ANTALYA", 2, GREEN, True)

    # Footer ticker
    cv.rect(0, H - 58, W, 58, INK)
    ticker = ("ALSO TODAY: KENYA DISCHARGES ITS LAST EBOLA PATIENT, 37 DAYS "
              "ON * UKRAINE HITS CRIMEA BRIDGE A THIRD TIME * VOYAGER 1 "
              "REACHES ONE LIGHT-DAY FROM EARTH")
    lines = wrap(ticker, 2, right - m)
    ty = H - 46
    for line in lines[:2]:
        cv.draw_centered(W // 2, ty, line, 2, WHITE)
        ty += 24
    return cv


def png_bytes(cv):
    raw = bytearray()
    stride = cv.w * 3
    for yy in range(cv.h):
        raw.append(0)
        raw += cv.px[yy * stride:(yy + 1) * stride]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = png_bytes(build())
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(data)
    print("wrote", path, len(data), "bytes")


if __name__ == "__main__":
    main()
