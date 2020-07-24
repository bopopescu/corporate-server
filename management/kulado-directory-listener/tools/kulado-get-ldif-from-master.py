#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Univention Directory Listener
"""Read LDAP from the DC Main and create LDIF file (and update local schema)"""
#
# Copyright 2004-2019 Univention GmbH
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

from __future__ import print_function
import univention.uldap as uldap
import univention.config_registry

import ldap
import ldif
import sys
import os
import optparse
import gzip
import logging

from ldap.controls import SimplePagedResultsControl

sys.path.append("/usr/lib/univention-directory-listener/system/")
import replication  # noqa: E402

LDIF = '/var/lib/univention-directory-listener/main.ldif.gz'
SCHEMA = '/var/lib/univention-ldap/schema.conf'
OIDS = set(replication.BUILTIN_OIDS) | set(('1.3.6.1.4.1.4203.666.11.1.4.2.12.1'),)


# from replication.py
def _update_schema(fp, attr):
		subschema = ldap.schema.SubSchema(attr)
		for oid in replication.subschema_sort(subschema, ldap.schema.AttributeType):
			if oid in OIDS:
				continue
			obj = subschema.get_obj(ldap.schema.AttributeType, oid)
			fp.write('attributetype %s\n' % (obj,))

		for oid in replication.subschema_sort(subschema, ldap.schema.ObjectClass):
			if oid in OIDS:
				continue
			obj = subschema.get_obj(ldap.schema.ObjectClass, oid)
			fp.write('objectclass %s\n' % (obj,))


def update_schema(lo):
	"""
	update the ldap schema file
	"""
	logging.info('Fetching Schema ...')
	res = lo.search(base="cn=Subschema", scope=ldap.SCOPE_BASE, filter='(objectclass=*)', attr=['+', '*'])
	tmp = SCHEMA + '.new'
	with open(tmp, 'w') as fp:
		fp.write('# This schema was automatically replicated from the main server\n')
		fp.write('# Please do not edit this file\n\n')

		for dn, data in res:
			_update_schema(fp, data)

	os.rename(tmp, SCHEMA)


def create_ldif_from_main(lo, ldif_file, base, page_size):
	"""
	create ldif file from everything from lo
	"""
	logging.info('Fetching LDIF ...')
	if ldif_file == '-':
		output = sys.stdout
	else:
		if os.path.isfile(ldif_file):
			os.unlink(ldif_file)
		output = gzip.open(ldif_file, 'wb')

	if hasattr(ldap, 'LDAP_CONTROL_PAGE_OID'):  # python-ldap <= 2.3
		logging.debug('Using old python-ldap 2.3 API')
		api24 = False
		lc = SimplePagedResultsControl(
			controlType=ldap.LDAP_CONTROL_PAGE_OID,
			criticality=True,
			controlValue=(page_size, ''))
		page_ctrl_oid = ldap.LDAP_CONTROL_PAGE_OID
	else:  # python-ldap >= 2.4
		logging.debug('Using new python-ldap 2.4 API')
		api24 = True
		lc = SimplePagedResultsControl(
			criticality=True,
			size=page_size,
			cookie='')
		page_ctrl_oid = lc.controlType

	while True:
		msgid = lo.lo.search_ext(base, ldap.SCOPE_SUBTREE, '(objectclass=*)', ['+', '*'], serverctrls=[lc])
		rtype, rdata, rmsgid, serverctrls = lo.lo.result3(msgid)

		for dn, data in rdata:
			logging.debug('Processing %s ...', dn)
			for attr in replication.EXCLUDE_ATTRIBUTES:
				data.pop(attr, None)

			output.write(ldif.CreateLDIF(dn, data, cols=10000))

		pctrls = [
			c
			for c in serverctrls
			if c.controlType == page_ctrl_oid
		]
		if pctrls:
			if api24:
				cookie = lc.cookie = pctrls[0].cookie
			else:
				_est, cookie = pctrls[0].controlValue
				lc.controlValue = (page_size, cookie)

			if not cookie:
				break
		else:
			logging.warning("Server ignores RFC 2696 Simple Paged Results Control.")
			break

	output.close()


def main():
	usage = "usage: %prog [options]"
	parser = optparse.OptionParser(usage=usage, description=__doc__)
	parser.add_option("-l", "--ldif", action="store_true", help="Create LDIF file")
	parser.add_option("-s", "--schema", action="store_true", help="Update LDAP schema [%s]" % SCHEMA)
	parser.add_option("-o", "--outfile", default=LDIF, help="File to store gzip LDIF data [%default]")
	parser.add_option("-p", "--pagesize", type=int, default=1000, help="page size to use for LDAP paged search")
	parser.add_option("-v", "--verbose", action="count", help="Increase verbosity")
	opts, args = parser.parse_args()

	logging.basicConfig(stream=sys.stderr, level=logging.DEBUG if opts.verbose else logging.WARNING)

	ucr = univention.config_registry.ConfigRegistry()
	ucr.load()
	base = ucr.get("ldap/base")
	if ucr.get("server/role", "") == "domaincontroller_backup":
		lo = uldap.getAdminConnection()
	else:
		lo = uldap.getMachineConnection(ldap_main=True)

	if opts.schema:
		update_schema(lo)

	if opts.ldif:
		create_ldif_from_main(lo, opts.outfile, base, opts.pagesize)


if __name__ == "__main__":
	main()
