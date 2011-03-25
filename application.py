#
# tepco-usage-api
#
# Copyright (c) 2011 by Shigeru KANEMOTO
#

from flask import (
  Flask, request, Response, abort, json,
  render_template, render_template_string, Markup,
)
app = Flask(__name__)
app.debug = True

from google.appengine.api import memcache
from google.appengine.ext import db

import datetime
import logging
import re
import markdown
import tepco

################################################################################

class Usage(db.Model):
  entryfor = db.DateTimeProperty(required=True)
  year = db.IntegerProperty(required=True)
  month = db.IntegerProperty(required=True)
  day = db.IntegerProperty(required=True)
  hour = db.IntegerProperty(required=True)
  usage = db.IntegerProperty(required=True)
  saving = db.BooleanProperty(required=True)
  usage_updated = db.DateTimeProperty(required=True)
  capacity = db.IntegerProperty(required=True)
  capacity_updated = db.DateTimeProperty(required=True)

class Config(db.Model):
  # key_name
  value = db.StringProperty()

################################################################################

class TZ(datetime.tzinfo):
  def __init__(self, name, offset):
    self.name_ = name
    self.offset_ = offset
  def utcoffset(self, dt):
    return datetime.timedelta(hours=self.offset_)
  def tzname(self, dt):
    return self.name
  def dst(self, dt):
    return datetime.timedelta(0)

UTC = TZ('UTC', 0)
JST = TZ('JST', 9)

def jst_from_utc(dt):
  return dt.replace(tzinfo=UTC).astimezone(JST)

def utc_from_jst(dt):
  return dt.replace(tzinfo=JST).astimezone(UTC)

@app.route('/update_from_tepco')
def update_from_tepco():
  lastmod = Config.get_by_key_name('last-modified')
  lastmod = lastmod and lastmod.value
  data = tepco.from_web(lastmod)
  if not data:
    return ''	# not yet updated
  Config(
    key_name='last-modified',
    value=data['lastmodstr']
  ).put()

  usage_updated = data['usage-updated']
  capacity = data['capacity']
  capacity_updated = data['capacity-updated']

  # the image is updated hourly just after the hour.
  jst = jst_from_utc(usage_updated) - datetime.timedelta(hours=1)
  jst = jst.replace(minute=0, second=0, microsecond=0)

  for hour, (usage, saving) in data['usage'].iteritems():
    entryfor = utc_from_jst(jst.replace(hour=hour))
    entry = Usage.all().filter('entryfor =', entryfor).get()
    if entry:
      if entry.usage != usage:
	entry.usage = usage
	entry.usage_updated = usage_updated
      entry.saving = saving
    else:
      entry = Usage(
	entryfor=entryfor,
	year=entryfor.year,
	month=jst.month,
	day=jst.day,
	hour=hour,
	usage=usage,
	saving=saving,
	usage_updated=usage_updated,
	capacity=capacity,
	capacity_updated=capacity_updated,
      )
    entry.put()
  memcache.delete('latest.json')
  return ''

RE_TWITTER_ID = re.compile(r'@([a-zA-Z0-9_]+)')

@app.route('/')
def top():
  usage = Usage.all().order('-entryfor').get()
  if usage:
    today = jst_from_utc(usage.usage_updated - datetime.timedelta(hours=1))
    ratio = round(usage.usage * 100.0 / usage.capacity)
  else:
    today = datetime.datetime.now()
    ratio = 0

  contents = file('contents.mkd').read()
  contents = contents.decode('utf-8')
  contents = markdown.markdown(contents, ['def_list'])
  contents = render_template_string(contents, today=today)
  contents = RE_TWITTER_ID.sub(r'<a href="http://twitter.com/\1">@\1</a>', contents)
  contents = Markup(contents)

  return render_template(
    'top.html',
    usage=usage, today=today, ratio=ratio, contents=contents
  )

def dict_from_usage(usage):
  return usage and {
    'entryfor': str(usage.entryfor),
    'year': usage.year,
    'month': usage.month,
    'day': usage.day,
    'hour': usage.hour,
    'usage': usage.usage,
    'saving': usage.saving,
    'usage_updated': str(usage.usage_updated),
    'capacity': usage.capacity,
    'capacity_updated': str(usage.capacity_updated),
  }

RE_CALLBACK = re.compile(r'^[a-zA-Z0-9_.]+$')

def resultHandler(result, cachekey=None):
  callback = request.form.get('callback') or request.args.get('callback')
  if callback and not RE_CALLBACK.search(callback):
    abort(404)

  if cachekey:
    data = memcache.get(cachekey)
    if not data or not isinstance(data, str):
      logging.info('Cache miss, compute tye result.')
      data = result()
      if not data:
	abort(404)
      data = json.dumps(data, indent=2)
      memcache.set(cachekey, data)
  else:
    data = json.dumps(result, indent=2)

  if callback:
    return Response('%s(%s);' % (callback, data), mimetype='text/javascript')
  else:
    return Response(data, mimetype='application/json')

@app.route('/latest.json')
def latest():
  def compute():
    usage = Usage.all().order('-entryfor').get()
    return dict_from_usage(usage)
  return resultHandler(compute, 'latest.json')

@app.route('/<int:year>/<int:month>/<int:day>/<int:hour>.json')
def hour(year, month, day, hour):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.filter('day =', day)
  usage = usage.filter('hour =', hour)
  usage = usage.get()
  usage = dict_from_usage(usage)
  return resultHandler(usage)

@app.route('/<int:year>/<int:month>/<int:day>.json')
def day(year, month, day):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.filter('day =', day)
  usage = usage.order('entryfor')
  usage = [dict_from_usage(u) for u in usage]
  return resultHandler(usage)

@app.route('/<int:year>/<int:month>.json')
def month(year, month):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.order('entryfor')
  usage = [dict_from_usage(u) for u in usage]
  return resultHandler(usage)
