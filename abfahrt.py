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
import threading
import locale
import Queue

import pygame
from pygame.locals import *
#necessary for umlaut
locale.setlocale(locale.LC_ALL,"")

def get_next_connections(start, destination, time, debug=False):
    """"""
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

def get_next_connections_db(start, destination, time, debug=False):
    url = "http://reiseauskunft.bahn.de"
    params = {"S" : "Triftstr., Halle (Saale)", "Z" : "Kröllwitz, Halle (Saale)",
                "adult-number" : "1", }
    r1 = req.get(url, params=params)
    return r1.text.encode("utf-8")

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
        time_shift = timedelta(minutes=0)
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
                    self.myscreen.addstr(11, 0, "Updating...", curses.color_pair(5))

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
                    self.myscreen.addstr(counter*3 + 2, 0, "{:>14} -> {:14}".format(start[:14], dest[:14]), color)
                    self.myscreen.addstr(counter*3 + 3, 0, "{:^32}".format(time_left_str), color)
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
            self.myscreen.addstr(0, 0, "{:>32}".format((datetime.now() + time_shift).strftime("%H:%M")), curses.color_pair(1))
            self.myscreen.refresh()
            time.sleep(1)

class PygameWindow:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((320, 240))
        self.background = pygame.Surface(self.screen.get_size())
        self.background = self.background.convert()
        self.background.fill((0, 0, 0))
        self.font = pygame.font.Font(None, 36)
        self.text = self.font.render("Hello There", 1, (255, 255, 255))
        textpos = self.text.get_rect()
        textpos.centerx = self.background.get_rect().centerx
        self.background.blit(self.text, textpos)
        self.screen.blit(self.background, (0, 0))
        pygame.display.flip()

    def run(self):
        while 1:
            for event in pygame.event.get():
                if event.type == QUIT:
                    return

            self.screen.blit(self.background, (0, 0))
            pygame.display.flip()


if __name__ == "__main__":
    pw = PygameWindow()
    pw.run()
    # cw = CursesWindow(debug=True)
    # with cw:
    #     cw.run()
