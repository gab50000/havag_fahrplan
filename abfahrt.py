#!/usr/bin/python
# -*- coding: utf-8 -*-
import requests as req
import re
from lxml import html
from datetime import datetime, timedelta
import ipdb
from dateutil import parser
import curses
import time
import multiprocessing as mp
import threading
import locale
import Queue
#necessary for umlaut
locale.setlocale(locale.LC_ALL,"")

def get_next_connections(start, destination, time, debug=False):
	if debug == True:
		logfile = open("get_next_connections.log", "a")
	"""Input: start location, destination, datetime object"""
	dtn = time
	time_now = "{:02d}:{:02d}".format(dtn.hour, dtn.minute)
	date_now = "{:02d}.{:02d}.{}".format(dtn.day, dtn.month, dtn.year)
	url="http://www.havag.com/fahrplan/verbindung"
	data = {"results[2][2][from]" : "Halle (Saale), {}".format(start), 
		"results[2][2][to]" : "Halle (Saale), {}".format(destination), 
		"results[2][2][time_mode]" : "departure", "results[2][2][date]" : "17.04.2015", 
		"results[2][2][mode]":"connection", "results[2][2][means_of_transport][]":"STR", 
		"results[2][2][from_opt]": "3", "results[2][2][to_opt]": "3",
		"results[2][2][via_opt]": "1", "results[2][2][time]": time_now, "results[2][2][date]": date_now }

	headers = {"Content-Type" : "application/x-www-form-urlencoded"}
	r = req.post(url, data=data, headers=headers)
	document = html.fromstring(r.text)
	connections = document.cssselect("div.content-timetable")
	departures = []
	for connection in connections:
		conn_text = html.tostring(connection.cssselect("li")[1])
		if debug == True:
			print >> logfile, "found connection", conn_text
		departure = parser.parse(re.findall("\d+\:\d+", conn_text)[0])
		departures.append(departure)
	if debug == True:
		logfile.close()
	return departures

def get_departures(routes):
	t = datetime.now()
	next_departures = []
	for route in routes:
		start, dest = route
		conns = get_next_connections(start, dest, t)
		for c in conns:
			if c < datetime.now():
				c += timedelta(days=1)
			next_departures.append((c, start, dest))
	next_departures.sort(key=lambda x: (x[0]-datetime.now()).total_seconds())
	return next_departures
	
def get_departures_queue(routes, t, q, debug=False):

	next_departures = []
	for route in routes:
		start, dest = route
		conns = get_next_connections(start, dest, t, debug=debug)
		for c in conns:
			if c < datetime.now():
				c += timedelta(days=1)
			next_departures.append((c, start, dest))
	next_departures.sort(key=lambda x: (x[0]-datetime.now()).total_seconds())
	q.put(next_departures)

class CursesWindow:
	def __init__(self, debug=False):
		self.debug = debug
		if self.debug == True:
			self.log = open("abfahrt.log", "a")
		self.curses_colors = [curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_BLUE, 
								curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_MAGENTA, curses.COLOR_RED]
		self.routes = [("Triftstr.", "Büschdorf"), ("Triftstr.", "Kröllwitz"), ("Volkspark", "Rannischer Platz"), ("Volkspark", "Pfarrstr.")]
		self.myscreen = curses.initscr()
		self.departures = []
		curses.curs_set(0)
		curses.start_color()
			#~ curses.init_pair(i, self.curses_colors[i], curses.COLOR_BLACK) 
		for i, color in enumerate(self.curses_colors):
			curses.init_pair(i+1, color, curses.COLOR_BLACK) 

	def __enter__(self):
		pass
	def __exit__(self, type, value, traceback):
		curses.endwin()
		if self.debug == True:
			self.log.close()
		
	def run(self):
		time_shift = timedelta(minutes=9)
		time_for_update = True
		updating = False
		delete = False
		q = Queue.Queue()
		p = None
		while 1:
			self.myscreen.clear()
			if time_for_update == True:
				t = datetime.now() + time_shift
				p = threading.Thread(target=get_departures_queue, args=(self.routes, t, q, self.debug))
				p.start()
				updating = True
				time_for_update = False
				if self.debug == True:
					print >> self.log, "time for update!"
					print >> self.log, "time is", t
			if updating == True:
				try:
					self.departures = q.get(timeout=0.1)
					p.join()
					self.myscreen.addstr(0, 0, "Update finished!", curses.color_pair(4))
					updating = False
					if self.debug == True:
						print >> self.log, "got {} from thread".format(self.departures)
				#~ except mp.queues.Empty:
				except Queue.Empty:
					if self.debug == True:
						print >> self.log, "queue was empty. keep updating"
					self.myscreen.addstr(0, 0, "Updating...", curses.color_pair(5))
			
			counter = 0
			for dept_time, start, dest in self.departures:
				#~ time_left = dept_time - datetime.now() - time_shift
				time_left_sec =  int((dept_time - datetime.now() - time_shift).total_seconds())
				#choose color depending on time left
				if time_left_sec > 600:
					color = curses.color_pair(4)
				elif time_left_sec > 300:
					color = curses.color_pair(5)
				else:
					color = curses.color_pair(7)
				if time_left_sec > 0 and counter < 3:
					time_left_str = "{:02d}:{:02d}:{:02d}".format(time_left_sec/3600, (time_left_sec%3600)/60, time_left_sec%60)
					#~ self.myscreen.addstr(counter*3 + 1, 0, "{:10} -> {:10}: {}".format(start, dest, time_left_str), color)
					self.myscreen.addstr(counter*3 + 1, 0, "{:5} -> {:5}: {}".format(start[:5], dest[:5], time_left_str), color)
					counter += 1
				else:
					if time_left_sec < -60:
						delete = True
			if delete == True:
				self.myscreen.addstr(0, 0, "Deleting...", curses.color_pair(5))
				self.departures.pop(0)
				delete = False
			if len(self.departures) < 12 and updating == False:
				time_for_update = True
			#~ self.myscreen.addstr(30, 0, "dep len: {}, time for update: {}, updating: {}, delete: {}".format(len(self.departures), time_for_update, updating, delete), curses.color_pair(1))
			self.myscreen.refresh()
			time.sleep(1)
		
def curses_main(stdscr):
	while 1:
		stdscr.addstr(10, 10, "huhu", curses.A_NORMAL)
		stdscr.refresh()

def curses_routine():
	try:
		# Initialize curses
		stdscr=curses.initscr()
		# Turn off echoing of keys, and enter cbreak mode,
		# where no buffering is performed on keyboard input
		curses.noecho()
		curses.cbreak()
		
		# In keypad mode, escape sequences for special keys
		# (like the cursor keys) will be interpreted and
		# a special value like curses.KEY_LEFT will be returned
		stdscr.keypad(1)
		curses_main(stdscr)                    # Enter the main loop
		# Set everything back to normal
		stdscr.keypad(0)
		curses.echo()
		curses.nocbreak()
		curses.endwin()                 # Terminate curses
	finally:
		# In event of error, restore terminal to sane state.
		stdscr.keypad(0)
		curses.echo()
		curses.nocbreak()
		curses.endwin()
		#~ traceback.print_exc()           # Print the exception	

def main(*args):
	routes = [("Triftstr.", "Büschdorf"), ("Triftstr.", "Kröllwitz"), ("Volkspark", "Rannischer Platz"), ("Volkspark", "Pfarrstr.")]
	curses_routine()
	

	#~ for nd in next_departures:
		#~ print nd[0].strftime("%H:%M"), nd[1], "->", nd[2]
if __name__ == "__main__":
	cw = CursesWindow(debug=True)
	with cw:
		cw.run()
