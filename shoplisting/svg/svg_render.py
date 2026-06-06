# datamatrix code

from PIL import Image
from pylibdmtx.pylibdmtx import encode as dmtx_encode
from io import BytesIO

def gen_recipe_label(recipe_id):
  return f'R{recipe_id:08d}'

def gen_recipe_barcode(recipe_id):
  #recipe_id = gen_recipe_label(recipe_id)
  return gen_datamatrix(recipe_id, {'scheme': 'text', 'size': '16x16'})

def gen_datamatrix(text, dmtx_params):
  encoded = dmtx_encode(text.encode('ascii'), **dmtx_params)
  im = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
  stream = BytesIO()
  im.save(stream, 'PNG')
  stream.seek(0)
  return stream.read()

# svg code

import drawsvg as draw
import numpy as np
from collections import defaultdict
from PIL import ImageFont
import re

def breaktext(fit_width, ttfpath, size, text):
  f = ImageFont.truetype(ttfpath, size)
  breaks = list(re.finditer(r'\s+|$', text))
  segments = []
  start = 0
  i = 0
  while (len(breaks) > 0):
    segment = text[start:breaks[i].start(0)]
    width = f.getlength(segment)
    if (width > fit_width):
      segments.append(text[start:breaks[i-1].start(0)])
      start = breaks[i-1].end(0)
      breaks = breaks[i-1:]
      i = 0
    i += 1
    if (i == len(breaks)):
      segments.append(text[start:])
      breaks = []
  return segments

def transform(v, bb_l):
  v = np.array(v)
  nv = len(v) // 2
  return tuple(v * (bb_l[2:]*nv) + (bb_l[:2]*nv))

def transform_bb(bb, bb_l):
  bb = np.array(bb)
  size = bb[2:] * bb_l[2:]
  offset = bb[:2] * bb_l[2:] + bb_l[:2]
  return np.concatenate((offset,size))

class Configurable:
  def __init__(self, cfg):
    self._cfgtree = cfg
  def cfg(self, key, default=None):
    try:
      node = self._cfgtree
      for k in key.split('.'):
        node = node[k]
      return node
    except KeyError:
      if (default == None):
        raise
      return default

class SvgPage(Configurable):
  def __init__(self, cfg):
    Configurable.__init__(self, cfg)
    size = self.cfg('page.size')
    dpi = self.cfg('page.dpi')
    self.canvas = draw.Drawing(size[0]*dpi, size[1]*dpi, origin=(0,0), displayInline=False)
    self.canvas.append(draw.Rectangle(0,0,size[0]*dpi, size[1]*dpi, fill='white', stroke='black'))
    self.current_area = 0
  def getdrawarea(self, x, y, grid):
    size = self.cfg('page.size')
    dpi = self.cfg('page.dpi')
    real_size = (size[0]*dpi, size[1]*dpi)
    margin = self.cfg('page.margin')
    margin_size = (margin[0]*dpi, margin[1]*dpi)
    card_origin = (margin_size[0]/2, margin_size[1]/2)
    card_area = (real_size[0]-margin_size[0], real_size[1]-margin_size[1])
    card_size = (card_area[0]/grid[0], card_area[1]/grid[1])
    return (card_origin[0] + card_size[0] * x, card_origin[1] + card_size[1] * y
            , card_size[0], card_size[1])
  def addcard(self, card):
    grid = self.cfg('page.cardgrid')
    x, y = self.current_area % grid[0], self.current_area // grid[0]
    bb = self.getdrawarea(x, y, grid)
    drawn_card = MealCard(self, bb, card)
    self.current_area += 1
  def svg_data(self):
    return self.canvas.as_svg()

class DrawArea:
  def __init__(self, bb, canvas):
    self.bb = bb
    self.buffer = defaultdict(list)
    self.canvas = canvas
  def transform(self, v):
    return transform(v, self.bb)
  def transform_bb(self, bb):
    return transform_bb(bb, self.bb)
  def draw(self, item, z=0):
    self.buffer[z].append(item)
  def flush(self):
    zlvls = sorted(self.buffer.keys())
    for z in zlvls:
      for item in self.buffer[z]:
        self.canvas.append(item)

class ConfigProxy:
  def __init__(self, parent):
    self._parent = parent
  def cfg(self, key, default=None):
    return self._parent.cfg(key, default)

RIGHT = 1
TOP = 2

class MealCard(DrawArea, ConfigProxy):
  def __init__(self, page, bb, card_data):
    DrawArea.__init__(self, bb, page.canvas)
    ConfigProxy.__init__(self, page)
    self.card = card_data
    self.flag_counts = [0]*4
    self.drawbase()
    self.addflags()
    self.addcenter()
    self.drawdmtx()
    self.flush()
  def drawbase(self):
    self.draw(draw.Rectangle(*self.transform_bb((0, 0, 1, 1)), fill='white', stroke='black'), 0)
    circle_r = self.transform_bb((0,0,0,self.cfg('card.circle.r')))[3]
    self.draw(draw.Circle(*self.transform(self.cfg('card.circle.pos')), circle_r, fill='white', stroke='grey'), 5)
  def drawtitle(self, text, box_color):
    corner_r = self.transform_bb((0,0,0,self.cfg('card.title.box_r')))[3]
    rect_bb = self.transform_bb(self.cfg('card.title.box'))
    title_rect = draw.Rectangle(*rect_bb, fill='white', stroke=box_color, rx=corner_r)
    self.draw(title_rect, 1)
    title_pos = self.transform(self.cfg('card.title.titlepos'))
    title = draw.Text(text, self.cfg('typeface.card.titlesize'), *title_pos, text_anchor='middle',
      font_family=self.cfg('typeface.family'))
    self.draw(title, 2)
  def drawflag(self, corner, height, width, color, label):
    right, top = corner & RIGHT == RIGHT, corner & TOP == TOP
    top = 1-top
    v1 = np.array((right, top))
    v2 = v1 + (0, height * (-1 if top else 1))
    v3 = v1 + (width * (-1 if right else 1), 0)
    vertices = np.concatenate((v1,v2,v3))
    text_offset = (-0.02 if right else 0.02, -0.025 if top else 0.05)
    vt = v1 + text_offset
    if (self.flag_counts[corner] > 0):
      c = self.flag_counts[corner]
      vo = (0, self.cfg('card.flag.offset')*(-1 if top else 1) * c)
      vertices += vo*3
      vt += vo
    self.flag_counts[corner] += 1
    self.draw(draw.Lines(*self.transform(vertices), fill=color),1)
    self.draw(
      draw.Text(label,self.cfg('typeface.card.flagsize'),*self.transform(vt),
      text_anchor='end'if right else'start',
      font_family=self.cfg('typeface.family')), 2)
  def addflags(self):
    flags = self.card['tags']
    size = self.cfg('card.flag.size')
    for flag in flags:
      corner = 2 * ('TOP' in flag['position']) + 1 * ('RIGHT' in flag['position'])
      label = flag['name']
      color = flag['color']
      self.drawflag(corner, size[1], size[0], color, label)
  def addcenter(self):
    r_width = self.transform_bb(self.cfg('card.title.box'))[2]
    ttf = self.cfg('typeface.ttfpath')
    size = self.cfg('typeface.card.titlesize')
    text = self.card['name']
    title = '\n'.join(breaktext(r_width, ttf, size, text))
    box_color = self.cfg('card.title.color')
    self.drawtitle(title, box_color)
    note = self.card['bot_note']
    if (note):
      note_size = self.cfg('typeface.card.notesize')
      text = '\n'.join(breaktext(r_width, ttf, note_size, note))
      note_pos = self.transform(self.cfg('card.title.notepos'))
      self.draw(draw.Text(text, note_size, *note_pos, text_anchor='middle',
        font_family=self.cfg('typeface.family')), 2)
    time = self.card['top_note']
    if (time):
      time_size = self.cfg('typeface.card.timesize')
      time_pos = self.transform(self.cfg('card.title.timepos'))
      self.draw(draw.Text(time, time_size, *time_pos, fill='red', text_anchor='middle',
        font_family=self.cfg('typeface.family')), 2)
  def drawdmtx(self):
    recipeid = self.card['id']
    dmtx = gen_recipe_barcode(recipeid)
    bb = self.transform_bb(self.cfg('card.dmtx.box'))
    img = draw.Image(*bb, data = dmtx, mimeType='image/png')
    self.draw(img, 5)
    label_pos = self.transform(self.cfg('card.dmtx.labelpos'))
    title = draw.Text(recipeid.replace(' ','_'), self.cfg('typeface.card.dmtxsize'), *label_pos, text_anchor='middle',
      font_family=self.cfg('typeface.family'))
    self.draw(title, 6)
