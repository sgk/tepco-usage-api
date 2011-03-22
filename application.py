#
# tepco-usage-api
#
# Copyright (c) 2011 by Shigeru KANEMOTO
#

from flask import Flask
app = Flask(__name__)
app.debug = True

from flask import (
  redirect, url_for, request, render_template, abort,
)

from google.appengine.ext import db
import simplejson as json

import datetime
import tepco

################################################################################

class Usage(db.Model):
  entryfor = db.DateTimeProperty(required=True)
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
    return ''
  Config(
    key_name='last-modified',
    value=data['lastmodstr']
  ).put()

  usage_updated = data['usage-updated']
  capacity = data['capacity']
  capacity_updated = data['capacity-updated']
  year = data['year']
  month = data['month']
  day = data['day']

  for hour, (usage, saving) in data['usage'].iteritems():
    entryfor = utc_from_jst(datetime.datetime(year, month, day, hour))
    entry = Usage.all().filter('entryfor =', entryfor).get()
    if not entry:
      Usage(
	entryfor=entryfor,
	usage=usage,
	saving=saving,
	usage_updated=usage_updated,
	capacity=capacity,
	capacity_updated=capacity_updated,
      ).put()
  return ''
