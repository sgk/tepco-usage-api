#
# tepco-usage-api
#
# Copyright (c) 2011 by Shigeru KANEMOTO
#

from flask import Flask, render_template, jsonify, abort, Response, json, request
app = Flask(__name__)
app.debug = True

from google.appengine.ext import db
import datetime, re
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
      continue
    Usage(
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
    ).put()
  return ''

def dict_from_usage(usage):
  return {
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

def resultHundler(obj):
  if not obj:
    abort(404)

  if type(obj).__name__ == 'list' and  len(obj) == 0:
    abort(404)

  _callback = None
  if request.method == "POST"  and request.form.get("callback") is not None:
    _callback = request.form.get("callback")
  elif request.args.get("callback") is not None:
    _callback = request.args.get("callback")

  ret = None
  if _callback is not None and re.search(r'^[a-zA-Z0-9]+$', _callback):
    # XXX security risk
    if type(obj).__name__ == 'list':
      ret = Response("%s(%s);"%(_callback, json.dumps(obj, indent=2)), mimetype='application/json')
    else:
      ret = Response("%s(%s);"%(_callback, json.dumps(dict_from_usage(obj), indent=2)), mimetype='application/json')
  elif type(obj).__name__ == 'list' :
    # XXX security risk
    ret = Response(json.dumps(obj, indent=2), mimetype='application/json')
  else:
    ret = jsonify(dict_from_usage(obj))

  return ret;

@app.route('/')
def top():
  usage = Usage.all().order('-entryfor').get()
  if usage:
    today = jst_from_utc(usage.usage_updated - datetime.timedelta(hours=1))
  else:
    today = timedate.timedate.now()
  ratio = round(usage.usage * 100.0 / usage.capacity)
  return render_template('top.html', usage=usage, today=today, ratio=ratio)

@app.route('/latest.json')
def latest():
  usage = Usage.all().order('-entryfor').get()
  return resultHundler(usage)

@app.route('/<int:year>/<int:month>/<int:day>/<int:hour>.json')
def hour(year, month, day, hour):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.filter('day =', day)
  usage = usage.filter('hour =', hour)
  usage = usage.get()
  return resultHundler(usage)

@app.route('/<int:year>/<int:month>/<int:day>.json')
def day(year, month, day):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.filter('day =', day)
  usage = usage.order('entryfor')
  usage = [dict_from_usage(u) for u in usage]
  return resultHundler(usage)

@app.route('/<int:year>/<int:month>.json')
def month(year, month):
  usage = Usage.all()
  usage = usage.filter('year =', year)
  usage = usage.filter('month =', month)
  usage = usage.order('entryfor')
  usage = [dict_from_usage(u) for u in usage]
  return resultHundler(usage)
