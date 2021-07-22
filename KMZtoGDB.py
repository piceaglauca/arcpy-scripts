from xml.dom.minidom import parse as parseDOM
import zipfile
import sys
import os
import re
import datetime
import argparse
from pyproj import Transformer

RE_COORDS = re.compile('(-?[0-9]+\.[0-9]+),([0-9]+\.[0-9]+),')
#RE_DATE = re.compile('([0-9][0-9][0-9][0-9])-([0-9][0-9])-([0-9][0-9])T([0-9][0-9]):([0-9][0-9]):([0-9][0-9])')
RE_IMG = re.compile('<img src="(images[^"]*)"')
transformer = Transformer.from_crs(4326, 3005, always_xy=True)

def openKMZ(filename):
    if os.access (filename, os.R_OK):
        return zipfile.ZipFile(filename, 'r')
    else:
        print (f'{sys.argv[0]}: could not open KMZ: {filename}', file=sys.stderr)
        sys.exit(1)

def openDOM (kmz):
    kml = 'doc.kml'
    if kml in kmz.namelist():
        return parseDOM(kmz.open(kml))
    else:
        print (f'{sys.argv[0]}: invalid KMZ.', file=sys.stderr)
        sys.exit(1)

def getName(feature):
    name = feature.getElementsByTagName("name")[0].childNodes[0].data

    prefix="<![CDATA["
    suffix="]]>"
    
    if name.startswith(prefix):
        name = name[len(prefix):]

    if name.endswith(suffix):
        name = name[:-len(suffix)]

    return name

def getDate(feature):
    raw = feature.getElementsByTagName("when")[0].childNodes[0].data
    return datetime.datetime.fromisoformat(raw)

def getCoords(feature):
    raw = feature.getElementsByTagName("coordinates")[0].childNodes[0].data

    match = RE_COORDS.findall(raw, re.MULTILINE)
    xyCoords = []
    for coord in match:
        xyCoords.append(transformer.transform(coord[0], coord[1]))

    return xyCoords

def getPhotoList(s):
    raw = s.childNodes[0].data
    return RE_IMG.findall(raw)

def getExtendedData(feature):
    description = ""
    photos = []

    simpledata = feature.getElementsByTagName("SimpleData")

    for s in simpledata:
        if s.getAttribute("name") == "Description":
            description = s.childNodes[0].data
        elif s.getAttribute("name") == "pdfmaps_photos":
            photos = getPhotoList(s)

    return description, photos

def printFeature(feature):
    featureType = ""
    if len(feature.getElementsByTagName("Point")) > 0:
        featureType = "point"
    elif len(feature.getElementsByTagName("LineString")) > 0:
        featureType = "line"
    else:
        print (f'{sys.argv[0]}: unknown feature:\n{feature.toxml()}', file=sys.stderr)
        return

    name = getName(feature)
    datetime = getDate(feature)
    coords = getCoords(feature)
    description, photos = getExtendedData(feature) 

    print (f'type: {featureType}, name: {name}, datetime: {datetime}, coords: {coords}, description: {description}, photos: {photos}')

def printFeatures(dom):
    features = dom.getElementsByTagName("Placemark")

    for f in features:
        printFeature(f)

def main(**kwargs):
    kmz = openKMZ(kwargs.get('kmz'))
    dom = openDOM(kmz)

    printFeatures(dom)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--kmz', dest='kmz', action='store', required=True,
        metavar='file_path', help='path to the KMZ to open')
    args = p.parse_args()
    main(**vars(args))
