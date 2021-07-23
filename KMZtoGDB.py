from xml.dom.minidom import parse as parseDOM
import zipfile
import sys
import os
import re
import datetime
import argparse
import arcpy

RE_COORDS = re.compile('(-?[0-9]+\.[0-9]+),([0-9]+\.[0-9]+),')
RE_DATE = re.compile('([0-9][0-9][0-9][0-9])-([0-9][0-9])-([0-9][0-9])T([0-9][0-9]):([0-9][0-9]):([0-9][0-9])')
RE_IMG = re.compile('<img src="(images[^"]*)"')

class gdbAccess:
    ProjectFolder = 'G:/Projects/Various_Clients/Galore Creek/Field Data'
    GDB = ProjectFolder + '/testing.gdb'
    photo_dir = ProjectFolder + '/KMZPhotos'

    fc_points = GDB + '/KMLPoint'
    attr_points = ['Name', 'Description', 'Date', 'Origin_file', 'SHAPE@']

    fc_lines = GDB + '/KMLLine'
    attr_lines = ['Name', 'Description', 'Date', 'Origin_file', 'SHAPE@']

    table_photos = GDB + '/Photos'
    attr_photos = ['Feature_Type', 'Feature_OBJECTID', 'Photo_Path']

    def __init__(self):
        self.editor = arcpy.da.Editor(self.GDB)

    def startEditing(self):
        self.editor.startEditing()
        self.editor.startOperation()
        self.cursor = {'Point':    arcpy.da.InsertCursor (self.fc_points, self.attr_points),
                       'Polyline': arcpy.da.InsertCursor (self.fc_lines, self.attr_lines),
                       'Photos':   arcpy.da.InsertCursor (self.table_photos, self.attr_photos)}

    def insertRow (self, feature):
        try: 
            objectid = self.cursor[feature.featureType].insertRow(feature.toTuple())
        except RuntimeError:
            print ("Error inserting new row: " + str(feature.toTuple()))
            raise
        if len(feature.photos) > 0:
            for photo in feature.photos:
                # set photopath to be <kmz filename w/o .kmz>_<photo name>.jpg
                photopath = feature.filename[:-4] + '_' + photo[len('images/'):]
                try:
                    self.cursor['Photos'].insertRow ((feature.featureType, objectid, photopath))
                except RuntimeError:
                    print ("Error inserting photos: " + photopath)
                    raise
    
    def stopEditing (self, commit=False):
        self.editor.stopOperation()
        self.editor.stopEditing(commit)

    def __del__ (self):
        if self.editor.isEditing:
            self.editor.stopEditing(False)

class Feature:
    gcs_sr = arcpy.SpatialReference(4326) # Lat Long: Geographic Coordinate System WGS84
    albers_sr = arcpy.SpatialReference(3005) # Albers

    def __init__(self, dom, filename):
        self.name = getName(dom)
        self.date = getDate(dom)
        self.description, self.photos = getExtendedData(dom)
        self.featureType, self.shape = getShape(dom)
        self.filename = filename

    def toTuple(self):
        return (self.name, self.description, self.date, self.filename, self.shape)

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
        match = RE_DATE.search(raw)
        return datetime.datetime(int(match.group(1)),
                                 int(match.group(2)),
                                 int(match.group(3)),
                                 int(match.group(4)),
                                 int(match.group(5)),
                                 int(match.group(6)))

    def getShape(feature):
        raw = feature.getElementsByTagName("coordinates")[0].childNodes[0].data

        match = RE_COORDS.findall(raw, re.MULTILINE)
        points = []
        for coord in match:
            points.append(arcpy.Point(coord[0], coord[1]))

        if len(points) == 1:
            featureType = "Point"
            feature = arcpy.PointGeometry(points[0], gcs_sr)
        else:
            featureType = "Polyline"
            feature = arcpy.Polyline(arcpy.Array(points), gcs_sr)

        projectedFeature = feature.projectAs(albers_sr)

        return featureType, projectedFeature

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

def openKMZ(filename):
    if os.access (filename, os.R_OK):
        return zipfile.ZipFile(filename, 'r')
    else:
        print ('KMZtoGDB: could not open KMZ: ' + filename)
        sys.exit(1)

def openDOM (kmz):
    kml = 'doc.kml'
    if kml in kmz.namelist():
        return parseDOM(kmz.open(kml))
    else:
        print ('KMZtoGDB: invalid KMZ.')
        sys.exit(1)

def processKMZ(kmzDOM, filename):
    domPlacemarks = kmzDOM.getElementsByTagName("Placemark")
    gdb = gdbAccess ()
    gdb.startEditing()

    for dom in domPlacemarks:
        feature = Feature(dom, filename)
        gdb.insertRow(feature)

        #print ('Feature is type: ' + feature.featureType)
        #print ('\t  name:\t' + feature.name)
        #print ('\t  date:\t' + feature.date.isoformat())
        #print ('\t  desc:\t' + feature.description)
        #print ('\tphotos:\t' + str(feature.photos))
        #print ('\tcoords:\t' + str(feature.shape.firstPoint.X) + ',' + str(feature.shape.firstPoint.Y))

    gdb.stopEditing(True)

def KMZtoGDB(**kwargs):
    filename = kwargs.get('kmz')
    kmz = openKMZ(filename)
    kmzDOM = openDOM(kmz)

    processKMZ(kmzDOM, os.path.basename(filename))
