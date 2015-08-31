import os
import re
import sys
import urllib2
import logging
from xml.dom import minidom

from string import letters

import jinja2
import webapp2

from google.appengine.api import memcache
from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), 
								autoescape = True)

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		t = jinja_env.get_template(template)
		return t.render(params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

GMAPS_URL = "http://maps.googleapis.com/maps/api/staticmap?size=380x263&sensor=false&"  #google maps api
def gmaps_img(points):                                                       #if points exist(i.e a list of coordinates) plot them on gmaps
    markers = '&'.join('markers=%s,%s' % (p.lat,p.lon) for p in points)
    return GMAPS_URL + markers


IP_URL = "http://api.hostip.info/?ip="   #link given by the api which gives an xml code
def get_coords(ip):           #function to get coordinates based on ip address (using an api for getting coordinates)
    #ip = "4.2.2.2"
    #ip = "23.24.209.141"
    url = IP_URL + ip        #adding the particular ip of interest to get coordinates
    content = None
    try:
        content = urllib2.urlopen(url).read()   #read the xml code
    except URLError:
        return

    if content:
        d = minidom.parseString(content)                      #parsing xml into python
        coords = d.getElementsByTagName("gml:coordinates")     #use to extract value by a tag name
        if coords and coords[0].childNodes[0].nodeValue:       
            lon, lat = coords[0].childNodes[0].nodeValue.split(',')
            return db.GeoPt(lat, lon)                         #GAE inbuilt db function to store coordinates


class Art(db.Model):
    title = db.StringProperty(required = True)
    art = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    coords = db.GeoPtProperty()      # to store coordinates in google datastore		


def top_arts(update = False):
    key = 'top'    # initializing key to a random string
    arts = memcache.get(key)
    if arts is None or update:    
        logging.error("DB QUERY")
        arts = db.GqlQuery("SELECT * FROM Art ORDER BY created DESC LIMIT 10")
        arts = list(arts)
        memcache.set(key,arts)
    return arts


class MainPage(Handler):
    def render_front(self, title="", art="", error=""):
        arts = top_arts()
        
        #if arts have coords display map with marker indicating coordinates
        img_url = None
        points = filter(None, (a.coords for a in arts))
        if points:
            img_url = gmaps_img(points)

        self.render("front.html", title=title, art=art, error = error, arts = arts, img_url = img_url)


    def get(self):
        #self.write(repr(get_coords(self.request.remote_addr)))  # requesting for an ip address and writing it on the front page
        self.render_front()         #repr is used cause, python objects will have tags ('<') which HTML will think is part of it and wont print what we want

    def post(self):
        title = self.request.get("title")
        art = self.request.get("art")

        if title and art:
            p = Art(title = title, art = art)
            coords = get_coords(self.request.remote_addr)     #store coordinates in a variable "coords"
            if coords:
                p.coords = coords                             #if coords exist add it to the class Art

            p.put()
            #CACHE.clear()  #clearing the dictionary(cache) after a new submission(so that the new cache includes this latest submission)
            
            # rerun the query and update the cache
            top_arts(True) # this sets the fact that a page view wont hit the db

            self.redirect("/")
        else:
            error = "we need both a title and some artwork!"
            self.render_front(title, art, error)		


app = webapp2.WSGIApplication([('/', MainPage)], debug = True)								