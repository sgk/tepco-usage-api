#
# Retrieve the TEPCO power usage from the text and the image.
#
# 2011-3-22
# Shigeru KANEMOTO
# sgk//switch-science.com
#

import urllib2
import re
import time
import datetime
import locale

import pygif

PAGE_URL = 'http://www.tepco.co.jp/en/forecast/html/index-e.html'
IMAGE_URL = 'http://www.tepco.co.jp/en/forecast/html/images/juyo-e.gif'
RE_CAPACITY = re.compile('Today\'s Maximum Capacity&nbsp;:&nbsp;([\d,]+)&nbsp;10&nbsp;thousand&nbsp;kW \(([a-zA-Z]{3} \d{1,2}. \d{1,2}:\d{2}) Update\)')

COLOR_PINK = 106
COLOR_BLUE = 6
COLOR_WATER = 51
COLOR_YELLOW = 125
COLOR_BLACK = 1
COLOR_ORANGE = 112

def from_text():
  page = urllib2.urlopen(PAGE_URL)
  page = page.read()

  m = RE_CAPACITY.search(page)
  if not m:
    raise RuntimeError
  capacity = m.group(1)
  capacity = int(capacity.replace(',', ''))
  t = m.group(2)
  t = time.strptime(t + ' 2011', '%b %d. %H:%M %Y')
  year, month, day = t.tm_year, t.tm_mon, t.tm_mday
  t = time.mktime(t) - 60*60*9
  t = datetime.datetime.utcfromtimestamp(t)

  return {
    'capacity': capacity,
    'capacity-updated': t,
    'year': year,
    'month': month,
    'day': day,
  }

def frequent_color(line):
  freq = 0
  color = COLOR_BLACK	# default
  for c in set(line):
    if c in (COLOR_PINK, COLOR_BLUE):
      continue
    f = line.count(c)
    if freq < f:
      color = c
  return color

  for c, f in [(c, colors.count(c)) for c in set(colors)]:
    if freq < f:
      freq = f
      color = c
  return color

def from_image(oldlastmodstr=None):
  image = urllib2.urlopen(IMAGE_URL)
  lastmodstr = image.headers['last-modified']
  if lastmodstr == oldlastmodstr:
    return None
  modified = datetime.datetime.strptime(lastmodstr, '%a, %d %b %Y %H:%M:%S %Z')

  image = pygif.GifDecoder(image.read())
  image = image.images[0]
  def pixel(x, y):
    return image.pixels[y * image.width + x]

  comb = []
  for x in range(53, 570):
    if pixel(x, 284) == COLOR_BLACK:
      comb.append(x + 1)

  d = {}
  for h, x in zip(range(24), comb):
    count = 0
    for y in range(285, 55, -1):
      color = frequent_color([pixel(xx, y) for xx in range(x, x + 21)])
      if color == COLOR_YELLOW:
	break
      count += 1
    if count == 0:
      break
    power = 6000 * count / (285 - 55 + 2)
    power = (power + 9) / 10 * 10
    saving = (pixel(x, 285) == COLOR_ORANGE)
    d[h] = (power, saving)

  return {
    'usage': d,
    'usage-updated': modified,
    'lastmodstr': lastmodstr,
  }

def from_web(oldlastmodstr=None):
  d = from_image(oldlastmodstr)
  if not d:
    return None
  d.update(from_text())
  return d

def main():
  locale.setlocale(locale.LC_ALL, 'C')
  import pprint
  pprint.pprint(from_web())

if __name__ == '__main__':
  main()
