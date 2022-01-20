#!/usr/bin/python3

from ics import Calendar, Event
from enum import Enum
import RPi.GPIO as gpio
import requests
import arrow
import os.path
import logging
import re
import getopt
import sys

class GarbageBin(Enum):
	NONE = 0
	GRAY = 1
	YELLOW = 2
	BLUE = 3
	EXTRA = 4

#
# See https://de.pinout.xyz
#
GPIO_PINS = {
	GarbageBin.GRAY: 17,
	GarbageBin.YELLOW: 27,
	GarbageBin.BLUE: 22,
	GarbageBin.EXTRA: 23
}

calendar_url = 'https://www.bee-emden.de/abfall/entsorgungssystem/abfuhrkalender/ics/jarssum-widdelswehr/abfuhrkalender.ics'
calendar_file = 'abfuhrkalender.ics'

#
# Download calendar file from url if it does not exist
#
def get_calendar_file(u):
	if os.path.isfile(calendar_file):
		return
	else:
		logging.info("Downloading from '" + u + "'")
		r = requests.get(u, allow_redirects=True)
		open(calendar_file, 'wb').write(r.content)

#
# Read events from file
#
def read_events_from(f):
	with open(f, 'r') as file:
        	ics_text = file.read()
	return Calendar(ics_text).events

#
# Find out which garbage bin the given category represents
#
def analyze_category(c):
	p = re.compile('gelb', re.IGNORECASE)
	if p.match(c):
		return GarbageBin.YELLOW
	
	p = re.compile('grau|rest', re.IGNORECASE)
	if p.match(c):
		return GarbageBin.GRAY
	
	p = re.compile('blau|papier', re.IGNORECASE)
	if p.match(c):
		return GarbageBin.BLUE

	return GarbageBin.EXTRA

#
# Do something with this event
#
def process_event(e):
	logging.info("Name: '" + e.name + "'")

	i = 0
	for c in e.categories:
		c = c.strip()
		b = analyze_category(c)
		logging.info('Category[' + str(i) + "]: '" + c + "' -> " + str(b))
		set_led_for_garbage_bin(b)
		i = i + 1

#
# Actually switch the LEDs
#
def set_led_for_garbage_bin(b):
	if b == GarbageBin.NONE:
		logging.debug('Switching off all LEDs')
		for k in GPIO_PINS.keys():
			gpio.output(GPIO_PINS[k], gpio.LOW)
	elif b == GarbageBin.YELLOW:
		logging.debug('Switching on yellow LED')
		gpio.output(GPIO_PINS[b], gpio.HIGH)
	elif b == GarbageBin.GRAY:
		logging.debug('Switching on gray LED')
		gpio.output(GPIO_PINS[b], gpio.HIGH)
	elif b == GarbageBin.BLUE:
		logging.debug('Switching on blue LED')
		gpio.output(GPIO_PINS[b], gpio.HIGH)
	elif b == GarbageBin.EXTRA:
		logging.debug('Switching on extra LED')
		gpio.output(GPIO_PINS[b], gpio.HIGH)
	else:
		logging.warning('No idea which LED to switch on or off')

#
# Make sure LEDs/PINs are in known state
#
def init_leds():
	gpio.setwarnings(False)
	gpio.cleanup()
	gpio.setmode(gpio.BCM)
	for b in GarbageBin:
		if b != GarbageBin.NONE:
			logging.debug('Configuring GPIO pin ' + str(GPIO_PINS[b]) + ' as output for ' + str(b))
			gpio.setup(GPIO_PINS[b], gpio.OUT)


if __name__ == "__main__":
	try:
		opts, args = getopt.getopt(sys.argv[1:], '', ['debug','url='])
	except getopt.GetoptError as err:
		logging.error('Command line options are b0rked')
		sys.exit(2)

	debug = False
	for o, a in opts:
		if o == "--debug":
       		 	debug = True
		elif o == "--url":
			calendar_url = a
		else:
			assert False, 'unhandled option'

	if debug:
		logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.DEBUG)
		rightnow = arrow.get('2022-01-14 04:00:00', 'YYYY-MM-DD HH:mm:ss')
	else:
		logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
		rightnow = arrow.utcnow()

	logging.debug('It is now ' + rightnow.format('YYYY-MM-DD HH:mm:ss'))

	logging.debug('Initialzing LEDs')
	init_leds()

	logging.info("Making sure current calendar file '" + calendar_file + "' exists")
	get_calendar_file(calendar_url)

	logging.info("Loading calendar from '" + calendar_file + "'")
	events = read_events_from(calendar_file)

	garbage_day = False
	for e in events:
		event_begin = arrow.get(e.begin)
		event_end = arrow.get(e.end)
		if event_begin <= rightnow and event_end >= rightnow:
			logging.info(event_begin.format('YYYY-MM-DD HH:mm:ss') + ' - ' + event_end.format('YYYY-MM-DD HH:mm:ss') + ' is now')
			garbage_day = True
			process_event(e)
		elif event_begin < rightnow and event_end < rightnow:
			logging.debug(event_begin.format('YYYY-MM-DD HH:mm:ss') + ' - ' + event_end.format('YYYY-MM-DD HH:mm:ss') + ' is in the past')
		elif event_begin > rightnow:
			logging.debug(event_begin.format('YYYY-MM-DD HH:mm:ss') + ' - ' + event_end.format('YYYY-MM-DD HH:mm:ss') + ' is in the future')
		else:
			logging.warning(event_begin.format('YYYY-MM-DD HH:mm:ss') + ' - ' + event_end.format('YYYY-MM-DD HH:mm:ss') + ' is what?')

	if garbage_day == False:
		logging.info('No garbage pickup today')
		set_led_for_garbage_bin(GarbageBin.NONE)
