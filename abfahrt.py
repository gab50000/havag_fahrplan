#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import re
import sys
import requests as req
from lxml import html
from datetime import datetime, timedelta
from dateutil import parser
import threading
import locale
import Queue
import pygame
from pygame.locals import *
# necessary for umlaut
locale.setlocale(locale.LC_ALL, "")


def get_next_connections(start, destination, time, debug=False):
    """"""
    if debug:
        logfile = open("get_next_connections.log", "a")
    """Input: start location, destination, datetime object"""
    dtn = time
    time_now = "{:02d}:{:02d}".format(dtn.hour, dtn.minute)
    date_now = "{:02d}.{:02d}.{}".format(dtn.day, dtn.month, dtn.year)
    url = "http://www.havag.com/fahrplan/verbindung"
    data = {"results[2][2][from]": "Halle (Saale), {}".format(start.encode("utf-8")),
            "results[2][2][to]": "Halle (Saale), {}".format(destination.encode("utf-8")),
            "results[2][2][time_mode]": "departure", "results[2][2][mode]": "connection",
            "results[2][2][means_of_transport][]": "STR", "results[2][2][from_opt]": "3",
            "results[2][2][to_opt]": "3", "results[2][2][via_opt]": "1",
            "results[2][2][time]": time_now, "results[2][2][date]": date_now }

    headers = {"Content-Type" : "application/x-www-form-urlencoded"}
    r = req.post(url, data=data, headers=headers)
    document = html.fromstring(r.text)
    connections = document.cssselect("div.content-timetable")
    departures = []
    for connection in connections:
        conn_text = html.tostring(connection.cssselect("li")[1])
        if debug:
            print >> logfile, "found connection", conn_text
        departure = parser.parse(re.findall("\d+\:\d+", conn_text)[0])
        departures.append(departure)
    if debug:
        logfile.close()
    return departures


def get_next_connections_db(start, destination, time, debug=False):
    url = "http://reiseauskunft.bahn.de"
    params = {"S" : "Triftstr., Halle (Saale)", "Z" : "Kröllwitz, Halle (Saale)",
              "adult-number": "1", }
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


class PygameWindow:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            self.log = open("abfahrt.log", "a")
        self.routes = [("Triftstr.", u"Büschdorf"), ("Triftstr.", u"Kröllwitz"),
                       ("Volkspark", "Rannischer Platz"), ("Volkspark", "Pfarrstr.")]
        self.departures = []

        os.environ["SDL_FBDEV"] = "/dev/fb1"
        os.environ["SDL_MOUSEDRV"] = "TSLIB"
        os.environ["SDL_MOUSEDEV"] = "/dev/input/touchscreen"
        pygame.init()
        self.screen = pygame.display.set_mode((320, 240))
        self.background = pygame.Surface(self.screen.get_size())
        self.background = self.background.convert()
        self.background.fill((0, 0, 0))
        self.fontsize = 30
        self.font = pygame.font.Font(None, self.fontsize)
        self.xcenter = self.background.get_rect().centerx
        self.y_offset = 0
        pygame.mouse.set_visible(False)

    def write_text(self, text, pos, color):
        t = self.font.render(text, 1, color)
        rect = t.get_rect()
        rect.center = pos
        self.background.blit(t, (rect.x, pos[1]))

    def write_messages(self, text_messages):
        self.y_offset = min(0, self.y_offset)
        if len(text_messages) > 240/self.fontsize:
            self.y_offset = max(-len(text_messages)*self.fontsize + 240, self.y_offset)
        for i, (message, color) in enumerate(text_messages):
            pos = (self.xcenter, self.y_offset + i*self.fontsize)
            self.write_text(message, pos, color)

    def blit_and_flip(self):
        self.screen.blit(self.background, (0, 0))
        pygame.display.flip()

    def determine_line_positions(self):
        line_no = 240 / self.fontsize
        offset = self.fontsize / 2
        self.positions = xrange(offset, 240+offset, self.fontsize)
        # connection number is line number minus line for time
        #  minus line for update notification
        self.connection_no = (line_no - 2)/2

    def get_swipe(self):
        pygame.event.get()
        if pygame.mouse.get_pressed()[0]:
            rel = pygame.mouse.get_rel()
            if self.pressed:
                return rel
            else:
                self.pressed = True
                return 0, 0
        else:
            self.pressed = False
            return 0, 0

    def check_quit(self):
        key = pygame.key.get_pressed()
        if key[K_q]:
            sys.exit()

    def run(self):
        time_shift = timedelta(minutes=0)
        time_for_update = True
        updating = False
        delete = False
        q = Queue.Queue()
        p = None
        while 1:
            messages = []
            messages.append(("{:>32}".format((datetime.now() + time_shift).strftime("%H:%M")), (255, 255, 255)))
            self.background.fill((0, 0, 0))
            if time_for_update:
                t = datetime.now() + time_shift
                p = threading.Thread(target=get_departures_queue, args=(self.routes, t, q, self.debug))
                p.start()
                updating = True
                time_for_update = False
                if self.debug:
                    print >> self.log, "time for update!"
                    print >> self.log, "time is", t
            if updating:
                try:
                    self.departures = q.get(timeout=0.1)
                    p.join()
                    messages.append(("Update finished!", (255, 255, 255)))
                    updating = False
                    if self.debug:
                        print >> self.log, "got {} from thread".format(self.departures)

                except Queue.Empty:
                    if self.debug:
                        print >> self.log, "queue was empty. keep updating"
                    messages.append(("Updating...", (255, 255, 255)))

            # counter = 0
            for dept_time, start, dest in self.departures:
                time_left_sec = int((dept_time - datetime.now() - time_shift).total_seconds())
                if time_left_sec > 0:
                    message_color = get_color(time_left_sec)
                    time_left_str = "{:02d}:{:02d}:{:02d}".format(
                        time_left_sec/3600, (time_left_sec % 3600)/60, time_left_sec % 60)
                    messages.append((u"{:>14} → {:14}".format(start, dest), message_color))
                    messages.append(("{:^32}".format(time_left_str), message_color))
                else:
                    if time_left_sec < -60:
                        delete = True
            if delete:
                messages.append(("Deleting...", (255, 255, 255)))
                self.departures.pop(0)
                delete = False
            if len(self.departures) < 12 and not updating:
                time_for_update = True
            self.write_messages(messages)
            y_shift = self.get_swipe()[1]
            self.y_offset += y_shift
            self.blit_and_flip()
            self.check_quit()
            pygame.time.delay(33)


def get_color(time_left_sec):
    green_time = 1200
    yellow_time = 600
    red_time = 300
    if time_left_sec < red_time:
        time_color = (255, 0, 0)
    elif time_left_sec < yellow_time:
        time_color = (255, int(float(time_left_sec-red_time)/(yellow_time-red_time)*255), 0)
    elif time_left_sec < green_time:
        time_color = (int((1-float(time_left_sec-yellow_time)/(green_time-yellow_time))*255), 255, 0)
    else:
        time_color = (0, 255, 0)
    return time_color

if __name__ == "__main__":
    pw = PygameWindow()
    pw.run()
