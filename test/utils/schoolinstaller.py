#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2017 Univention GmbH
#
# https://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <https://www.gnu.org/licenses/>.

from optparse import OptionParser
import sys
import time
import traceback

from univention.lib.umc import Client, ConnectionError, HTTPError

from univention.config_registry import ConfigRegistry
ucr = ConfigRegistry()
ucr.load()

parser = OptionParser()
parser.add_option(
	'-H', '--host', dest='host', default='%s.%s' % (ucr.get('hostname'), ucr.get('domainname')),
	help='host to connect to', metavar='HOST')
parser.add_option(
	'-u', '--user', dest='username',
	help='username', metavar='UID', default='Administrator')
parser.add_option(
	'-p', '--password', dest='password',
	help='password', metavar='PASSWORD')
parser.add_option(
	'-o', '--ou', dest='ou',
	help='ou name of the school', metavar='OU')
parser.add_option(
	'-S', '--single-server', dest='setup',
	action='store_const', const='singlemain',
	help='install a single server setup on a main')
parser.add_option(
	'-M', '--multi-server', dest='setup',
	action='store_const', const='multiserver',
	help='install a multi server setup')
parser.add_option(
	'-E', '--educational-server-name', dest='name_edu_server',
	help='name of the educational server', metavar='NAME_EDU_SLAVE')
parser.add_option(
	'-e', '--educational-server', dest='server_type',
	action='store_const', const='educational',
	help='install a dc subordinate in educational network (DEFAULT)')
parser.add_option(
	'-a', '--administrative-server', dest='server_type',
	action='store_const', const='administrative',
	help='install a dc subordinate in administrative network')
parser.add_option(
	'-m', '--main-host', dest='main', default=ucr['ldap/main'],
	help='on a subordinate the main host needs to be specified', metavar='HOST')
parser.add_option(
	'-s', '--samba-version', dest='samba', default='4',
	help='the version of samba, either 3 or 4', metavar='HOST')

(options, args) = parser.parse_args()

if ucr['server/role'] == 'domaincontroller_subordinate' and not options.server_type:
	parser.error('Please specify the subordinate type (--educational-server or --administrative-server)!')

if ucr['server/role'] == 'domaincontroller_subordinate' and options.server_type == 'administrative' and not options.name_edu_server:
	parser.error('Please specify the name of the educational subordinate when installing an administrative subordinate (-E)!')

if not options.setup:
	parser.error('Please specify a setup type: multi server (-M) or single server (-S)!')

if options.samba not in ('3', '4'):
	parser.error('Samba version needs to be either 3 or 4!')

if ucr['server/role'] != 'domaincontroller_main' and not options.main:
	parser.error('Please specify a main host (-m)!')

if not options.username or not options.password:
	parser.error('Please specify username (-u) and password (-p)!')

if not options.ou:
	if ucr['server/role'] == 'domaincontroller_subordinate' or options.setup == 'singlemain':
		parser.error('Please specify a school OU (-o)!')
	options.ou = ''

client = Client(options.host, options.username, options.password, language='en-US')

params = {
	'setup': options.setup,
	'username': options.username,
	'password': options.password,
	'main': options.main,
	'samba': options.samba,
	'schoolOU': options.ou,
}

if options.server_type:
	params['server_type'] = options.server_type
if options.name_edu_server:
	params['nameEduServer'] = options.name_edu_server

result = client.umc_command('schoolinstaller/install', params).result
if result and not result.get('success', True):  # backwards compatibility
	print 'ERROR: Failed to run installer!'
	print 'output: %s' % result
	sys.exit(1)

print '=== INSTALLATION STARTED ==='
status = {'finished': False}
failcount = 0
last_message = None
while not status['finished']:
	if failcount >= 1200:
		print 'ERROR: %d failed attempts - committing suicide' % (failcount, )
		sys.exit(1)
	try:
		status = client.umc_command('schoolinstaller/progress').result
		failcount = 0
	except (HTTPError, ConnectionError) as exc:
		failcount += 1
		print 'TRACEBACK %d in client.umc_command("schoolinstaller/progress"):\n%s' % (failcount, traceback.format_exc(),)
		time.sleep(1)
	message = '%(component)s - %(info)s' % status
	if last_message != message:
		last_message = message
		print message
	else:
		print '.',

if len(status['errors']) > 0:
	print 'ERROR: installation failed!'
	print 'output: %s' % status
	sys.exit(1)

result = client.umc_command('lib/server/restart').result
if not result:
	print 'ERROR: Failed to restart UMC'
	print 'output: %s' % result
	sys.exit(1)

# https://forge.univention.org/bugzilla/show_bug.cgi?id=42305
print 'UMC will be restarted on the system. Waiting for 20 seconds.'
time.sleep(20)

sys.exit(0)
