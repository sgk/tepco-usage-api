#!/usr/bin/python
#vim:fileencoding=utf-8
#
# Retrieve the TEPCO power usage from the text and the image.
#
# 2011-3-22
# Shigeru KANEMOTO
# sgk//switch-science.com
#

import urllib2
import datetime

import pygif

IMAGE_URL = 'http://www.tepco.co.jp/forecast/html/images/juyo-j.gif'
CSV_URL = 'http://www.tepco.co.jp/forecast/html/images/juyo-j.csv'

COLOR_BLACK = (0, 0, 0)
COLOR_ORANGE = (255, 128, 0)

def from_web(oldlastmodstr=None, url=None):
  csv = urllib2.urlopen(url or CSV_URL)
  lastmodstr = csv.headers['last-modified']
  if lastmodstr == oldlastmodstr:
    return None

  r = {}
  r['usage-updated'] = datetime.datetime.strptime(
      lastmodstr, '%a, %d %b %Y %H:%M:%S %Z')
  r['lastmodstr'] = lastmodstr

  #
  # Power usage
  #
  usage = {}
  line = csv.readline()		# 2011/6/27 23:55 UPDATE

  line = csv.readline()		# ピーク時供給力（万ｋW),時間帯,供給力情報更新日,供給力情報更新時刻
  line = csv.readline()		# 4580,14:00～15:00,6/26,17:30
  line = line.strip()
  line = line.split(',')
  r['capacity'] = int(line[0])
  r['capacity-peak-period'] = int(line[1].split(':')[0])
  t = datetime.datetime.strptime(
    '2011 %s %s' % (line[2], line[3]), 
    '%Y %m/%d %H:%M'
  )
  t -= datetime.timedelta(hours=9)
  r['capacity-updated'] = t
  line = csv.readline()		# empty line

  #
  # Forecast
  #
  line = csv.readline()		# 予想最大電力(万kW),時間帯,予想最大電力情報更新日,予想最大電力情報更新時刻
  line = csv.readline()		# 3640,14:00～15:00,6/26,17:30
  line = line.strip()
  line = line.split(',')
  r['forecast-peak-usage'] = int(line[0])
  r['forecast-peak-period'] = int(line[1].split(':')[0])
  t = datetime.datetime.strptime(
    '2011 %s %s' % (line[2], line[3]), 
    '%Y %m/%d %H:%M'
  )
  t -= datetime.timedelta(hours=9)
  r['forecast-peak-updated'] = t
  line = csv.readline()		# empty line

  #
  # Hourly history
  #
  line = csv.readline()		# DATE,TIME,当日実績(万kW),予測値(万kW)
  for x in range(24):
    line = csv.readline()
    line = line.strip()
    line = line.split(',')
    hour = int(line[1].split(':')[0])
    power = int(line[2])
    forecast = int(line[3])
    usage[hour] = (power, False, forecast)
  line = csv.readline()		# empty line

  #
  # Rolling blackout
  #
  if False:
    try:
      gif = urllib2.urlopen(IMAGE_URL)
    except:
      pass
    else:
      gif = pygif.GifDecoder(gif.read())
      image = gif.images[0]

      def is_pixel(x, y, col):
	pix = image.pixels[y * image.width + x]
	pix = gif.pallete[pix]
	d = (
	  (pix[0] - col[0]) ** 2 +
	  (pix[1] - col[1]) ** 2 +
	  (pix[2] - col[2]) ** 2
	)
	return (d < 100)

      def comb():
	for x in range(50, 670):
	  if is_pixel(x, 387, COLOR_BLACK):
	    yield x + 1

      for h, x in zip(usage.iterkeys(), comb()):
	usage[h] = (usage[h][0], is_pixel(x, 387, COLOR_ORANGE))
  r['usage'] = usage

  #
  # 無視
  #
  line = csv.readline()		# 翌日のピーク時供給力(万kW),時間帯,供給力情報更新日,供給力情報更新時刻
  line = csv.readline()		# 4880,16:00～17:00,6/27,17:30
  line = csv.readline()		# empty line
  line = csv.readline()		# 翌日の予想最大電力(万kW),時間帯,予想最大電力情報更新日,予想最大電力情報更新時刻
  line = csv.readline()		# 4150,16:00～17:00,6月27日,17:30 
  line = csv.readline()		# empty line
  line = csv.readline()		# メッセージＮｏ,節電お願い文
  line = csv.readline()		# 1,節電にご協力いただき、ありがとうございます。皆さまのご協力により、電気の供給は、比較的余裕のある一日となりそうです。
  line = csv.readline()		# 1,Thank you very much for your cooperation to save electricity.According to your cooperation
  line = csv.readline()		# empty line

  #
  # 速報
  #
  line = csv.readline()		# DATE,TIME,当日実績（５分間隔値）(万kW)
  lastline = None
  for x in range(12 * 24):
    line = csv.readline()
    line = line.strip()
    line = line.split(',')
    if not line[2]:
      break
    lastline = line
  r['quick'] = '%s,%s,%d' % (lastline[1], lastline[2], r['capacity'])

  return r

def main():
  import locale
  import pprint
  import sys
  locale.setlocale(locale.LC_ALL, 'C')
  url = sys.argv[1] if len(sys.argv) > 1 else None
  pprint.pprint(from_web(url=url))

if __name__ == '__main__':
  main()
