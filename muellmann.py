#!/usr/bin/python3

from ics import Calendar, Event
from enum import Enum
import RPi.GPIO as GPIO
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

#
# All valid areas for which ICS files exist
#
AREAS = [
	'larrelt',
	'contantia',
	'port-arthur-transvaal',
	'hafen',
	'barenburg-harsweg',
	'twixlum-wybelsum-logumer-vorwerk-knock',
	'kulturviertel-sudlich-fruchteburger-weg-gewerbegebiet-2-polderweg',
	'conrebbersweg',
	'kulturviertel-nordlich-fruchteburger-weg',
	'wolthusen',
	'aok-viertel-grossfaldern',
	'kleinfaldern-herrentor',
	'friesland-borssum-hilmarsum',
	'amtsgerichtsviertel-und-ringstrasse-am-tonnenhof',
	'altstadt',
	'jarssum-widdelswehr',
	'petkum-uphusen-tholenswehr-marienwehr'
]

calendar_base_url = 'https://www.bee-emden.de/abfall/entsorgungssystem/abfuhrkalender/ics'
calendar_area = 'jarssum-widdelswehr'
calendar_file = 'abfuhrkalender.ics'

#
# Download calendar file if it does not exist
#
def get_calendar_file_for_area(a):
	local_file = a + '-' + calendar_file
	if os.path.isfile(local_file):
		# nothing to do
		pass
	else:
		url = calendar_base_url + '/' + a + '/' + calendar_file
		logging.info("Downloading from '" + url + "'")
		r = requests.get(url, allow_redirects=True)
		open(local_file, 'wb').write(r.content)
	return local_file

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
	
	p = re.compile('blau|papier|pappe|karton', re.IGNORECASE)
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
			GPIO.output(GPIO_PINS[k], GPIO.LOW)
	elif b == GarbageBin.YELLOW:
		logging.debug('Switching on yellow LED')
		GPIO.output(GPIO_PINS[b], GPIO.HIGH)
	elif b == GarbageBin.GRAY:
		logging.debug('Switching on gray LED')
		GPIO.output(GPIO_PINS[b], GPIO.HIGH)
	elif b == GarbageBin.BLUE:
		logging.debug('Switching on blue LED')
		GPIO.output(GPIO_PINS[b], GPIO.HIGH)
	elif b == GarbageBin.EXTRA:
		logging.debug('Switching on extra LED')
		GPIO.output(GPIO_PINS[b], GPIO.HIGH)
	else:
		logging.warning('No idea which LED to switch on or off')

#
# Make sure LEDs/PINs are in known state
#
def init_leds():
	GPIO.setwarnings(False)
	GPIO.cleanup()
	GPIO.setmode(GPIO.BCM)
	for b in GarbageBin:
		if b != GarbageBin.NONE:
			logging.debug('Configuring GPIO pin ' + str(GPIO_PINS[b]) + ' as output for ' + str(b))
			GPIO.setup(GPIO_PINS[b], GPIO.OUT, initial=GPIO.LOW)


if __name__ == "__main__":
	logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
	debug = False
	time_to_check = arrow.now()

	try:
		opts, args = getopt.getopt(sys.argv[1:], '', ['debug', 'area=', 'date='])
	except getopt.GetoptError as err:
		logging.critical('Command line options are b0rked')
		sys.exit(2)

	for o, a in opts:
		if o == '--debug':
			debug = True
			logging.getLogger().setLevel(logging.DEBUG)
			logging.info('Enabling DEBUG mode')
		elif o == '--area':
			if a in AREAS:
				calendar_area = a
				logging.info("Using area '" + a + "'")
			else:
				logging.critical("Unknown area '" + a + "'")
				sys.exit(2)
		elif o == '--date':
			logging.info("Setting time to '" + a + "'")
			time_to_check = arrow.get(a)
		else:
			logging.critical("Unknown option '" + o + "'")
			sys.exit(2)

	logging.debug('Assuming it is now ' + time_to_check.format('YYYY-MM-DD HH:mm:ss'))

	logging.debug('Initialzing LEDs')
	init_leds()

	logging.info("Making sure current calendar file '" + calendar_file + "' for area '" + calendar_area + "' exists")
	local_file = get_calendar_file_for_area(calendar_area)

	logging.info("Loading calendar from '" + local_file + "'")
	events = read_events_from(local_file)

	garbage_day = False
	for e in events:
		event_begin = arrow.get(e.begin)
		event_end = arrow.get(e.end)
		if event_begin <= time_to_check and event_end >= time_to_check:
			logging.info(event_begin.format('YYYY-MM-DD HH:mm:ss') + ' - ' + event_end.format('YYYY-MM-DD HH:mm:ss') + ' is now')
			garbage_day = True
			process_event(e)
		elif event_begin < time_to_check and event_end < time_to_check:
			logging.debug(event_begin.format('YYYY-MM-DD HH:mm:ss') + ' - ' + event_end.format('YYYY-MM-DD HH:mm:ss') + ' is in the past')
		elif event_begin > time_to_check:
			logging.debug(event_begin.format('YYYY-MM-DD HH:mm:ss') + ' - ' + event_end.format('YYYY-MM-DD HH:mm:ss') + ' is in the future')
		else:
			logging.warning(event_begin.format('YYYY-MM-DD HH:mm:ss') + ' - ' + event_end.format('YYYY-MM-DD HH:mm:ss') + ' is what?')

	if garbage_day == False:
		logging.info('No garbage pickup today')
		set_led_for_garbage_bin(GarbageBin.NONE)
