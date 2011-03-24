#
# Retrieve the TEPCO power usage from the text and the image.
#
# 2011-3-22
# Shigeru KANEMOTO
# sgk//switch-science.com
#

import urllib2
import datetime
import re

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

def from_web(oldlastmodstr=None):
  csv = urllib2.urlopen(CSV_URL)
  lastmodstr = csv.headers['last-modified']
  if lastmodstr == oldlastmodstr:
    return None
  r = {
    'usage-updated': datetime.datetime.strptime(lastmodstr, '%a, %d %b %Y %H:%M:%S %Z'),
    'lastmodstr': lastmodstr,
  }

  #
  # Power usage
  #
  usage = {}
  csv.readline()
  csv.readline()
  for line in csv:
    line = line.split(',')
    power = int(line[2])
    if power == 0:
      break
    hour = int(line[1].split(':')[0])
    usage[hour] = (power, False)

  #
  # Rolling blackout
  #
  try:
    image = urllib2.urlopen(IMAGE_URL)
    image = pygif.GifDecoder(image.read())
    image = image.images[0]
    def pixel(x, y):
      return image.pixels[y * image.width + x]

    comb = []
    for x in range(53, 570):
      if pixel(x, 284) == COLOR_BLACK:
	comb.append(x + 1)

    for h in usage.keys():
      x = comb.pop(0)
      usage[h] = (usage[h][0], (pixel(x, 285) == COLOR_ORANGE))
  except:
    pass

  r['usage'] = usage

  #
  # Capacity
  #
  page = urllib2.urlopen(PAGE_URL)
  page = page.read()

  m = RE_CAPACITY.search(page)
  if not m:
    raise RuntimeError
  capacity = m.group(1)
  capacity = int(capacity.replace(',', ''))
  r['capacity'] = capacity

  t = m.group(2)
  t = datetime.datetime.strptime(t + ' 2011', '%b %d. %H:%M %Y')
  t = t - datetime.timedelta(hours=9)
  r['capacity-updated'] = t	# UTC

  return r

def main():
  import locale
  locale.setlocale(locale.LC_ALL, 'C')
  import pprint
  pprint.pprint(from_web())

if __name__ == '__main__':
  main()
