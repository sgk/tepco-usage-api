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
IMAGE_URL = 'http://www.tepco.co.jp/forecast/html/images/juyo-j.gif'
CSV_URL = 'http://www.tepco.co.jp/forecast/html/images/juyo-j.csv'
RE_CAPACITY = re.compile('Today\'s Maximum Capacity&nbsp;:&nbsp;([\d,]+)&nbsp;10&nbsp;thousand&nbsp;kW \(([a-zA-Z]{3} \d{1,2}. \d{1,2}:\d{2}) Update\)')

COLOR_PINK = 106
COLOR_BLUE = 6
COLOR_WATER = 51
COLOR_YELLOW = 125
COLOR_BLACK = 1
COLOR_ORANGE = 112

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

def from_web(oldlastmodstr=None):
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

  savings = []
  for h, x in zip(range(24), comb):
    savings.append(pixel(x, 285) == COLOR_ORANGE)

  usage = {}
  csv = urllib2.urlopen(CSV_URL)
  csv.readline()
  csv.readline()
  for line in csv:
    line = line.split(',')
    power = int(line[2])
    if power == 0:
      break
    hour = int(line[1].split(':')[0])
    usage[hour] = (power, savings[hour])

  r = {
    'usage': usage,
    'usage-updated': modified,	# UTC
    'lastmodstr': lastmodstr,
  }

  page = urllib2.urlopen(PAGE_URL)
  page = page.read()

  m = RE_CAPACITY.search(page)
  if not m:
    raise RuntimeError
  capacity = m.group(1)
  capacity = int(capacity.replace(',', ''))
  t = m.group(2)
  t = time.strptime(t + ' 2011', '%b %d. %H:%M %Y')
  t = time.mktime(t) - 60*60*9
  t = datetime.datetime.utcfromtimestamp(t)

  r.update({
    'capacity': capacity,
    'capacity-updated': t,	# UTC
  })

  return r

def main():
  locale.setlocale(locale.LC_ALL, 'C')
  import pprint
  pprint.pprint(from_web())

if __name__ == '__main__':
  main()
