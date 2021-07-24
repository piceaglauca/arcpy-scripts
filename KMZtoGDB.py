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

def sanitizeFilename (filename):
    validfilechars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join (c for c in filename if c in validfilechars)

class KMZ:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.dirname = os.path.dirname(filepath)
        self.photodir = self.dirname + '/KMZPhotos/'

    def open(self):
        if os.access (self.filepath, os.R_OK):
            self.kmz = zipfile.ZipFile(self.filepath, 'r')
        else:
            print ('KMZtoGDB: could not open KMZ: ' + self.filepath)
            sys.exit(1)

    def getDOM (self):
        kml = 'doc.kml'
        if kml in self.kmz.namelist():
            return parseDOM(self.kmz.open(kml))
        else:
            print ('KMZtoGDB: invalid KMZ.')
            sys.exit(1)

    def process(self, gdbpath):
        kmzDOM = self.getDOM()
        domPlacemarks = kmzDOM.getElementsByTagName("Placemark")
        gdb = GDB (gdbpath)
        gdb.startEditing()

        photoList = {}
        for dom in domPlacemarks:
            feature = Feature(dom, self.filename)
            if gdb.insertRowIfNew(feature): # True if row inserted
                for kmzPhotoPath, gdbPhotoPath in feature.photos:
                    if not kmzPhotoPath in photoList.keys():
                        photoList[kmzPhotoPath] = gdbPhotoPath

        if len(photoList) > 0:
            for photo in self.kmz.namelist():
                if not photo.startswith('images/'):
                    continue
                else:
                    kmzPhotoPath = sanitizeFilename(os.path.basename(photo))
                    if not kmzPhotoPath in photoList.keys():
                        print ("problem with " + photo)
                    else:
                        path = self.photodir + photoList[kmzPhotoPath]
                        try:
                            with open(path, 'wb') as f:
                                f.write(self.kmz.read(photo))
                        except:
                            print ("problem writing " + kmzPhotoPath + " to " + path)
                            raise

        gdb.stopEditing(True)

class GDB:
    def __init__(self, gdbpath):
        self.gdbpath = gdbpath
        self.projectFolder = os.path.dirname(gdbpath)
        photo_dir = self.projectFolder + '/KMZPhotos'

        arcpy.env.workspace = self.gdbpath

        self.fc_points = 'KMLPoint'
        self.attr_points = ['Name', 'Description', 'Date', 'Origin_file', 'SHAPE@']

        self.fc_lines = 'KMLLine'
        self.attr_lines = ['Name', 'Description', 'Date', 'Origin_file', 'SHAPE@']

        self.table_photos = 'Photos'
        self.attr_photos = ['Feature_Type', 'Feature_OBJECTID', 'Photo_Path']

        gdbSchema = arcpy.ListFeatureClasses() + arcpy.ListTables()
        for fc in [self.fc_points, self.fc_lines, self.table_photos]:
            if fc not in gdbSchema:
                print ("Unrecognized geodatabase")
                sys.exit(1)

    def startEditing(self):
        self.editor = arcpy.da.Editor(self.gdbpath)
        self.editor.startEditing()
        self.editor.startOperation()
        #self.search = {'Point':    arcpy.da.SearchCursor (self.fc_points, self.attr_points),
        #               'Polyline': arcpy.da.SearchCursor (self.fc_lines, self.attr_lines)}
        self.cursor = {'Point':    arcpy.da.InsertCursor (self.fc_points, self.attr_points),
                       'Polyline': arcpy.da.InsertCursor (self.fc_lines, self.attr_lines),
                       'Photos':   arcpy.da.InsertCursor (self.table_photos, self.attr_photos)}

    def searchRow (self, feature):
        if feature.featureType == "Point":
            fc   = self.fc_points
            attr = self.attr_points
        elif feature.featureType == "Polyline":
            fc   = self.fc_lines
            attr = self.attr_lines

        where=u"{} = '{}' And {} = date '{}'".format(arcpy.AddFieldDelimiters(fc, 'Name'), feature.name,
													 arcpy.AddFieldDelimiters(fc, 'Date'), feature.date)
        return arcpy.da.SearchCursor (fc, attr, where_clause=where)

    def insertRowIfNew (self, feature):
        if len(list(self.searchRow(feature))) == 0:
            self.insertRow (feature)
            return True
        else:
            return False

    def insertRow (self, feature):
        try: 
            objectid = self.cursor[feature.featureType].insertRow(feature.toTuple())
        except RuntimeError:
            print ("Error inserting new row: " + str(feature.toTuple()))
            raise
        if len(feature.photos) > 0:
            for kmzPhotoPath, gdbPhotoPath in feature.photos: # kmzPhotoPath not used here
                # set photopath to be <kmz filename w/o .kmz>_<photo name>.jpg
                #photopath = feature.filename[:-4] + '_' + photo[len('images/'):]
                try:
                    self.cursor['Photos'].insertRow ((feature.featureType, objectid, gdbPhotoPath))
                except RuntimeError:
                    print ("Error inserting photos: " + gdbPhotoPath)
                    raise
    
    def stopEditing (self, commit=False):
        self.editor.stopOperation()
        self.editor.stopEditing(commit)

    def __del__ (self):
        if self.editor.isEditing:
            self.stopEditing(False)

class Feature:
    gcs_sr = arcpy.SpatialReference(4326) # Lat Long: Geographic Coordinate System WGS84
    albers_sr = arcpy.SpatialReference(3005) # Albers

    def __init__(self, dom, filename):
        self.dom = dom
        self.filename = filename
        self.name = self.getName()
        self.date = self.getDate()
        self.description, self.photos = self.getExtendedData()
        self.featureType, self.shape = self.getShape()

    def toTuple(self):
        return (self.name, self.description, self.date, self.filename, self.shape)

    def getName(self):
        name = self.dom.getElementsByTagName("name")[0].childNodes[0].data

        prefix="<![CDATA["
        suffix="]]>"
        
        if name.startswith(prefix):
            name = name[len(prefix):]

        if name.endswith(suffix):
            name = name[:-len(suffix)]

        return name

    def getDate(self):
        raw = self.dom.getElementsByTagName("when")[0].childNodes[0].data
        match = RE_DATE.search(raw)
        return datetime.datetime(int(match.group(1)),
                                 int(match.group(2)),
                                 int(match.group(3)),
                                 int(match.group(4)),
                                 int(match.group(5)),
                                 int(match.group(6)))

    def getShape(self):
        raw = self.dom.getElementsByTagName("coordinates")[0].childNodes[0].data

        match = RE_COORDS.findall(raw, re.MULTILINE)
        points = []
        for coord in match:
            points.append(arcpy.Point(coord[0], coord[1]))

        if len(points) == 1:
            featureType = "Point"
            feature = arcpy.PointGeometry(points[0], self.gcs_sr)
        else:
            featureType = "Polyline"
            feature = arcpy.Polyline(arcpy.Array(points), self.gcs_sr)

        projectedFeature = feature.projectAs(self.albers_sr)

        return featureType, projectedFeature

    def getPhotoList(self, dom):
        raw = dom.childNodes[0].data

        photoList = []
        for photo in RE_IMG.findall(raw):
            kmzImagePath = sanitizeFilename(photo[len('images/'):])
            gdbImagePath = self.filename[:-4] + '_' + kmzImagePath
            photoList.append([kmzImagePath, gdbImagePath]) 

        return photoList

    def getExtendedData(self):
        description = ""
        photos = []

        simpledata = self.dom.getElementsByTagName("SimpleData")

        for s in simpledata:
            if s.getAttribute("name") == "Description":
                description = s.childNodes[0].data
            elif s.getAttribute("name") == "pdfmaps_photos":
                photos = self.getPhotoList(s)

        return description, photos

def KMZtoGDB(**kwargs):
    kmz = KMZ(kwargs.get('kmz'))
    kmz.open()
    kmz.process(kwargs.get('gdb'))
