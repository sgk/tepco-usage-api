#!/usr/bin/python
from wsgiref.handlers import CGIHandler
from main import app

CGIHandler().run(app)
