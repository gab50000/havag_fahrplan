#!/usr/bin/python
# -*- coding: utf-8 -*-
import requests as req
import re
import bs4
from datetime import datetime
import ipdb
from dateutil import parser
import curses
import time
import multiprocessing as mp
import locale
#necessary for umlaut
locale.setlocale(locale.LC_ALL,"")

def get_next_connections(start, destination, time):
	"""Input: start location, destination, datetime object"""
	dtn = time
	time_now = "{:02d}:{:02d}".format(dtn.hour, dtn.minute)
	date_now = "{:02d}.{:02d}.{}".format(dtn.day, dtn.month, dtn.year)
	url="http://www.havag.com/fahrplan/verbindung"
	#data = {"from" : "Halle+(Saale),+Triftstr.", "to" : "Halle+(Saale),+lutherstr"}
	data = {"results[2][2][from]" : "Halle (Saale), {}".format(start), 
		"results[2][2][to]" : "Halle (Saale), {}".format(destination), 
		"results[2][2][time_mode]" : "departure", "results[2][2][date]" : "17.04.2015", 
		"results[2][2][mode]":"connection", "results[2][2][means_of_transport][]":"STR", 
		"results[2][2][from_opt]": "3", "results[2][2][to_opt]": "3",
		"results[2][2][via_opt]": "1", "results[2][2][time]": time_now, "results[2][2][date]": date_now }

	headers = {"Content-Type" : "application/x-www-form-urlencoded"}
	r = req.post(url, data=data, headers=headers)
	soup = bs4.BeautifulSoup(r.text)
	connections = soup.find_all("div", class_ = "content-timetable")
	departures = []
	for connection in connections:
		conn_text = connection.findChildren("li")[1].text
		departure = parser.parse(re.findall("\d+\:\d+", conn_text)[0])
		departures.append(departure)
	return departures

def get_departures(routes):
	t = datetime.now()
	next_departures = []
	for route in routes:
		start, dest = route
		conns = get_next_connections(start, dest, t)
		for c in conns:
			next_departures.append((c, start, dest))
	next_departures.sort(key=lambda x: (x[0]-datetime.now()).seconds)
	return next_departures
	
def get_departures_queue(routes, t, q):
	next_departures = []
	for route in routes:
		start, dest = route
		conns = get_next_connections(start, dest, t)
		for c in conns:
			next_departures.append((c, start, dest))
	next_departures.sort(key=lambda x: (x[0]-datetime.now()).seconds)
	q.put(next_departures)

class CursesWindow:
	def __init__(self):
		self.curses_colors = [curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_BLUE, 
								curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_MAGENTA, curses.COLOR_RED]
		self.routes = [("Triftstr.", "Büschdorf"), ("Triftstr.", "Kröllwitz"), ("Volkspark", "Rannischer Platz"), ("Volkspark", "Pfarrstr.")]
		self.myscreen = curses.initscr()
		self.departures = []
		curses.curs_set(0)
		curses.start_color()
			#~ curses.init_pair(i, self.curses_colors[i], curses.COLOR_BLACK) 
		for i, color in enumerate(self.curses_colors):
			curses.init_pair(i, color, curses.COLOR_BLACK) 
			
	def __enter__(self):
		pass
	def __exit__(self, type, value, traceback):
		curses.endwin()
		
	def run(self):
		time_for_update = True
		updating = False
		q = mp.Queue()
		while 1:
			if time_for_update == True:
				t = datetime.now()
				p = mp.Process(target=get_departures_queue, args=(self.routes, t, q))
				p.start()
				updating = True
				time_for_update = False
			if updating == True:
				try:
					self.departures = q.get(timeout=0.1)
					p.join()
					self.myscreen.addstr(0, 0, "Update finished!", curses.color_pair(1))
					updating = False
				except mp.queues.Empty:
					self.myscreen.addstr(0, 0, "Updating...", curses.color_pair(0))
			for i, (dept_time, start, dest) in enumerate(self.departures[:3]):
				time_left = (dept_time - datetime.now()).seconds
				time_left_str = "{:02d}:{:02d}:{:02d}".format(time_left/3600, (time_left%3600)/60, time_left%60)
				self.myscreen.addstr(i*3 + 5, 30, "{:>20} -> {:<20} at {:<5}. {}".format(start, dest, dept_time.strftime("%H:%M"), time_left_str), curses.color_pair(3))
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
	cw = CursesWindow()
	with cw:
		cw.run()
