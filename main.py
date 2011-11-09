#
# tepco-usage-api
#
# Copyright (c) 2011 by Shigeru KANEMOTO
#

from flask import (
  Flask, request, Response, abort, json,
  render_template, render_template_string, Markup,
  make_response,
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
  forecast = db.IntegerProperty()
  usage_updated = db.DateTimeProperty(required=True)
  capacity = db.IntegerProperty(required=True)
  capacity_updated = db.DateTimeProperty(required=True)
  capacity_peak_period = db.IntegerProperty()
  forecast_peak_usage = db.IntegerProperty()
  forecast_peak_period = db.IntegerProperty()
  forecast_peak_updated = db.DateTimeProperty()

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

  if data.has_key('quick'):
    Config(
      key_name='quick.txt',
      value=data['quick']
    ).put()

  # the image is updated hourly just after the hour.
  jst = jst_from_utc(data['usage-updated']) - datetime.timedelta(hours=1)
  jst = jst.replace(minute=0, second=0, microsecond=0)

  for hour, (usage, saving, forecast) in data['usage'].iteritems():
    entryfor = utc_from_jst(jst.replace(hour=hour))
    entry = Usage.all().filter('entryfor =', entryfor).get()
    if entry:
      if entry.usage != usage:
	entry.usage = usage
	entry.usage_updated = data['usage-updated']
      entry.saving = saving
      if forecast:
	entry.forecast = forecast
    else:
      entry = Usage(
	entryfor=entryfor,
	year=entryfor.year,
	month=jst.month,
	day=jst.day,
	hour=hour,
	usage=usage,
	saving=saving,
	forecast=forecast,
	usage_updated=data['usage-updated'],
	capacity=data['capacity'],
	capacity_updated=data['capacity-updated'],
	capacity_peak_period=data['capacity-peak-period'],
	forecast_peak_usage=data['forecast-peak-usage'],
	forecast_peak_period=data['forecast-peak-period'],
	forecast_peak_updated=data['forecast-peak-updated'],
      )
    entry.put()
  memcache.flush_all()
  return ''

RE_TWITTER_ID = re.compile(r'@([a-zA-Z0-9_]+)')

@app.route('/')
def top():
  usage = None
  for usage in Usage.all().order('-entryfor').fetch(24):
    if usage.usage != 0:
      break
  if usage:
    today = jst_from_utc(usage.usage_updated - datetime.timedelta(hours=1))
    ratio = round(usage.usage * 100.0 / usage.capacity, 1)
  else:
    today = datetime.datetime.now()
    ratio = 0

  contents = file('contents.mkd').read()
  contents = contents.decode('utf-8')
  contents = markdown.markdown(contents, ['def_list'])
  contents = render_template_string(contents, today=today)
  contents = RE_TWITTER_ID.sub(
    r'<a href="http://twitter.com/\1">@\1</a>',
    contents
  )
  contents = Markup(contents)

  response = make_response(
    render_template(
      'top.html',
      usage=usage, today=today, ratio=ratio, contents=contents
    )
  )
  response.headers['Cache-Control'] = 'public, max-age=180'
  return response

def dict_from_usage(usage):
  return usage and {
    'entryfor': str(usage.entryfor),
    'year': usage.year,
    'month': usage.month,
    'day': usage.day,
    'hour': usage.hour,
    'usage': usage.usage,
    'saving': usage.saving,
    'forecast': usage.forecast,
    'usage_updated': str(usage.usage_updated),
    'capacity': usage.capacity,
    'capacity_updated': str(usage.capacity_updated),
    'capacity_peak_period': usage.capacity_peak_period,
    'forecast_peak_usage': usage.forecast_peak_usage,
    'forecast_peak_period': usage.forecast_peak_period,
    'forecast_peak_updated': usage.forecast_peak_updated and str(usage.forecast_peak_updated),
  }

RE_CALLBACK = re.compile(r'^[a-zA-Z0-9_.]+$')

def route_json(rule, **options):
  def decorator(func):
    def decorated(*args, **kw):
      callback = request.form.get('callback') or request.args.get('callback')
      if callback and not RE_CALLBACK.search(callback):
	abort(404)

      data = memcache.get(request.path)
      if not data or not isinstance(data, str):
	logging.info('Cache miss for %s' % request.path)
	data = func(*args, **kw)
	if not data:
	  abort(404)
	data = json.dumps(data, indent=2)
	memcache.set(request.path, data)

      if callback:
	data = '%s(%s);' % (callback, data)
      return Response(
	data,
	mimetype='application/json',
	headers=(('Cache-Control', 'public, max-age=180'),),
      )
    app.add_url_rule(rule, func.__name__, decorated, **options)
    return decorated
  return decorator

@route_json('/latest.json')
def latest():
  usage = None
  for usage in Usage.all().order('-entryfor').fetch(24):
    if usage.usage != 0:
      break
  return dict_from_usage(usage)

@route_json('/<int:year>/<int:month>/<int:day>/<int:hour>.json')
def hour(year, month, day, hour):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.filter('day =', day)
  usage = usage.filter('hour =', hour)
  usage = usage.get()
  return dict_from_usage(usage)

@route_json('/<int:year>/<int:month>/<int:day>.json')
def day(year, month, day):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.filter('day =', day)
  usage = usage.order('entryfor')
  return [dict_from_usage(u) for u in usage if u.usage != 0]

@route_json('/<int:year>/<int:month>.json')
def month(year, month):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.order('entryfor')
  return [dict_from_usage(u) for u in usage if u.usage != 0]

@app.route('/quick.txt')
def quick():
  data = memcache.get(request.path)
  if not data:
    data = Config.get_by_key_name('quick.txt')
    if not data:
      abort(404)
    data = data.value
    memcache.set(request.path, data)
  response = make_response(data)
  response.headers['Cache-Control'] = 'public, max-age=180'
  return response
