# -*- coding: utf-8 -*-
# Mock hpprime module for off-device smoke testing only.
_key = -1

def getkey():
    return _key

def set_key(k):
    global _key
    _key = k

def fillrect(x1, y1, x2, y2, color):
    pass

def set_pixel(x, y, color):
    pass

def draw_string(x, y, s, fg=0, bg=0xffffff):
    pass

def erase():
    pass
