#!/usr/bin/env python


import cups, os, optparse,  urlparse
import os.path
from StringIO import StringIO
from xml.etree.ElementTree import Element, ElementTree, tostring
from xml.dom.minidom import parseString
from xml.dom import minidom

import sys

try:
  import lxml.etree as etree
except:
  etree = None

XML_TEMPLATE = """<service-group>
<name replace-wildcards="yes"></name>
<service>
	<type>_ipp._tcp</type>
	<subtype>_universal._sub._ipp._tcp</subtype>
	<port>631</port>
	<txt-record>txtvers=1</txt-record>
	<txt-record>qtotal=1</txt-record>
	<txt-record>Transparent=T</txt-record>
	<txt-record>URF=none</txt-record>
</service>
</service-group>"""

#TODO XXX FIXME
#<txt-record>ty=AirPrint Ricoh Aficio MP 6000</txt-record>
#<txt-record>Binary=T</txt-record>
#<txt-record>Duplex=T</txt-record>
#<txt-record>Copies=T</txt-record>


DOCUMENT_TYPES = {
    'application/pdf': True,
    'application/postscript': True,
    'application/vnd.cups-raster': True,
    'application/octet-stream': True,
    'image/png': True,
    'image/tiff': True,
    'image/png': True,
    'image/jpeg': True,
    'image/gif': True,
    'text/plain': True,
    'text/html': True,

    'image/x-xwindowdump': False,
    'image/x-xpixmap': False,
    'image/x-xbitmap': False,
    'image/x-sun-raster': False,
    'image/x-sgi-rgb': False,
    'image/x-portable-pixmap': False,
    'image/x-portable-graymap': False,
    'image/x-portable-bitmap': False,
    'image/x-portable-anymap': False,
    'application/x-shell': False,
    'application/x-perl': False,
    'application/x-csource': False,
    'application/x-cshell': False,
}
class AirPrintGenerate(object):
    def __init__(self, host=None, user=None, port=None, verbose=False, directory=None):
        self.host = host
        self.user = user
        self.port = port
        self.verbose = verbose
        self.directory = directory
        
        if self.user:
            cups.setUser(self.user)
    
    def generate(self):
        conn = cups.Connection()
        printers = conn.getPrinters()
        
        for p, v in printers.items():
            if v['printer-is-shared']:
                attrs = conn.getPrinterAttributes(p)
                uri = urlparse.urlparse(v['printer-uri-supported'])

                tree = ElementTree()
                tree.parse(StringIO(XML_TEMPLATE.replace('\n', '').replace('\r', '').replace('\t', '')))

                name = tree.find('name')
                name.text = 'AirPlay %s @ %%h' % (p)

                service = tree.find('service')

                port = service.find('port')
                port.text = '%d' % uri.port

                path = Element('txt-record')
                path.text = 'rp=%s' % (uri.path)
                service.append(path)

                desc = Element('txt-record')
                desc.text = 'note=%s' % (v['printer-info'])
                service.append(desc)

                product = Element('txt-record')
                product.text = 'product=(GPL Ghostscript)'
                service.append(product)

                state = Element('txt-record')
                state.text = 'printer-state=%s' % (v['printer-state'])
                service.append(state)

                ptype = Element('txt-record')
                ptype.text = 'printer-type=%s' % (hex(v['printer-type']))
                service.append(ptype)

                pdl = Element('txt-record')
                fmts = []
                defer = []

                for a in attrs['document-format-supported']:
                    if a in DOCUMENT_TYPES:
                        if DOCUMENT_TYPES[a]:
                            fmts.append(a)
                    else:
                        defer.append(a)

                fmts = ','.join(fmts+defer)

                dropped = []
                while len(fmts) >= 255:
                    (fmts, drop) = fmts.rsplit(',', 1)
                    dropped.append(drop)

                if len(dropped) and self.verbose:
                    sys.stderr.write('%s Losing support for: %s%s' % (p, ','.join(dropped), os.linesep))

                pdl.text = 'pdl=%s' % (fmts)
                service.append(pdl)

                admin = Element('txt-record')
                admin.text = 'adminurl=%s' % (v['printer-uri-supported'])
                service.append(admin)

                f = tostring(tree.getroot())
                doc = parseString(f)
                dt= minidom.getDOMImplementation('').createDocumentType('service-group', None, 'avahi-service.dtd')
                doc.insertBefore(dt, doc.documentElement)
                
                fname = 'airprint-%s.service' % p
                
                if self.directory:
                    fname = os.path.join(self.directory, fname)
                
                f = open(fname, 'w')

                if etree:
                    x = etree.parse(StringIO(doc.toxml()))
                    x.write(f, pretty_print=True, xml_declaration=True, encoding="UTF-8")
                else:
                    doc.writexml(f)
                f.close()
                
                if self.verbose:
                    sys.stderr.write('Created: %s%s' % (fname, os.linesep))

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-H', '--host', action="store", type="string", dest='hostname', help='Hostname of CUPS server', metavar='HOSTNAME')
    parser.add_option('-P', '--port', action="store", type="int", dest='port', help='Port number of CUPS server', metavar='PORT')
    parser.add_option('-u', '--user', action="store", type="string", dest='username', help='Username to authenticate with against CUPS', metavar='USER')
    parser.add_option('-d', '--directory', action="store", type="string", dest='directory', help='Directory to create service files', metavar='DIRECTORY')
    parser.add_option('-v', '--verbose', action="store_true", dest="verbose", help="Print debugging information to STDERR")
    
    (options, args) = parser.parse_args()
    
    if options.directory:
        if not os.path.exists(options.directory):
            os.mkdir(options.directory)
    
    apg = AirPrintGenerate(
        user=options.username,
        host=options.hostname,
        port=options.port,
        verbose=options.verbose,
        directory=options.directory,
    )
    
    apg.generate()
