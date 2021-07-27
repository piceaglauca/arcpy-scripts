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
    validfilechars = "!@#$%^&()[]{};-_+=\'~,. abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join (c for c in filename if c in validfilechars)

class KML:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.dirname = os.path.dirname(filepath)

        self.open()

    def open(self):
        try:
            self.data = open(self.filepath, 'r')
        except:
            arcpy.AddError ("Invalid KML.")
            raise arcpy.ExecuteError

    def getDOM (self):
        return parseDOM(self.data)

    def process(self, gdb):
        kmlDOM = self.getDOM()
        gdb.startEditing()

        newFeatures = self.insertNewFeatures(kmlDOM)

        gdb.stopEditing(True)

        return newFeatures

    def insertNewFeatures(self, kmlDOM):
        domPlacemarks = kmlDOM.getElementsByTagName("Placemark")
        featureList = []
        for dom in domPlacemarks:
            feature = Feature(dom, self.filename)
            if gdb.insertRowIfNew(feature): # True if row inserted
                featureList.append(feature)

        return featureList

class KMZ (KML):
    def __init__(self, filepath, photos_path):
        KML.__init__(self, filepath)
        self.photodir = os.path.join (self.dirname, photos_path)

        if not os.path.isdir(self.photodir) and os.path.isfile(self.photodir):
            arcpy.AddError ("Photo directory is a file. Choose a folder to save photos.")
            raise arcpy.ExecuteError
        elif not os.path.isdir(self.photodir):
            try:
                os.mkdir(self.photodir)
            except IOError as e:
                if e.errno == errno.EACCES:
                    arcpy.AddError ("Permission denied when trying to create photo directory.")
                raise arcpy.ExecuteError

    def open(self):
        kml = 'doc.kml'
        try:
            self.kmz = zipfile.ZipFile(self.filepath, 'r')
            self.data = self.kmz.open(kml)
        except:
            arcpy.AddError ("Invalid KMZ.")
            raise arcpy.ExecuteError

    # Implemented in superclass. See KML.getDOM()
    #def getDOM (self):
    #    return parseDOM(self.data)

    def process(self, gdb):
        kmzDOM = self.getDOM()
        gdb.startEditing()

        newFeatures = KML.insertNewFeatures(self, kmzDOM)
        photoList = {}
        for feature in newFeatures:
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
                        path = os.path.join (self.photodir, photoList[kmzPhotoPath])
                        try:
                            with open(path, 'wb') as f:
                                f.write(self.kmz.read(photo))
                        except:
                            arcpy.AddError ("Problem writing " + kmzPhotoPath + " to " + path)
                            raise arcpy.ExecuteError

        gdb.stopEditing(True)

class GDB:
    def __init__ (self, gdbpath, fc_points='KMLPoint', fc_lines='KMLLine', table_photos='Photos', photos_path='KMZPhotos'):
        self.gdbpath = gdbpath
        self.fc_points = fc_points
        self.fc_lines = fc_lines
        self.table_photos = table_photos
        self.photos_dir = photos_path

        self.projectFolder = os.path.dirname(gdbpath)

        arcpy.env.workspace = self.gdbpath
        self.attr_points = ['Name', 'Description', 'Date', 'Origin_file', 'SHAPE@']
        self.attr_lines = ['Name', 'Description', 'Date', 'Origin_file', 'SHAPE@']
        self.attr_photos = ['Feature_Type', 'Feature_OBJECTID', 'Photo_Path']

        if not arcpy.Exists(self.fc_points):
            fc = arcpy.CreateFeatureclass_management(self.gdbpath, self.fc_points, "POINT", spatial_reference=Feature.albers_sr)
            arcpy.AddField_management(fc, 'Name', 'TEXT', field_length=200, field_is_required="REQUIRED")
            arcpy.AddField_management(fc, 'Description', 'TEXT', field_length=1000)
            arcpy.AddField_management(fc, 'Date', 'DATE', field_is_required="REQUIRED")
            arcpy.AddField_management(fc, 'Origin_file', 'TEXT', field_length=250)
        if not arcpy.Exists(self.fc_lines):
            fc = arcpy.CreateFeatureclass_management(self.gdbpath, self.fc_lines, "POLYLINE", spatial_reference=Feature.albers_sr)
            arcpy.AddField_management(fc, 'Name', 'TEXT', field_length=200, field_is_required="REQUIRED")
            arcpy.AddField_management(fc, 'Description', 'TEXT', field_length=1000)
            arcpy.AddField_management(fc, 'Date', 'DATE', field_is_required="REQUIRED")
            arcpy.AddField_management(fc, 'Origin_file', 'TEXT', field_length=250)

        # Even if a KML was specified, rather than a KMZ, it's worth creating this table
        # if it doesn't exist. It's possible that a KMZ will be loaded into the same gdb.
        if not arcpy.Exists(self.table_photos):
            table = arcpy.CreateTable_management(self.gdbpath, self.table_photos)
            arcpy.AddField_management(table, 'Feature_Type', 'TEXT', field_length=10)
            arcpy.AddField_management(table, 'Feature_OBJECTID', 'LONG')
            arcpy.AddField_management(table, 'Photo_Path', 'TEXT', field_length=1000)

        gdbSchema = arcpy.ListFeatureClasses() + arcpy.ListTables()
        for fc in [self.fc_points, self.fc_lines, self.table_photos]:
            if fc not in gdbSchema:
                arcpy.AddError ("Unable to verify or create geodatabase.")
                raise arcpy.ExecuteError

    def startEditing(self):
        self.editor = arcpy.da.Editor(self.gdbpath)
        self.editor.startEditing()
        self.editor.startOperation()
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
        try:
            if len(list(self.searchRow(feature))) == 0:
                self.insertRow (feature)
                return True
            else:
                return False
        except:
            self.stopEditing(False)
            raise

    def insertRow (self, feature):
        try: 
            objectid = self.cursor[feature.featureType].insertRow(feature.toTuple())
        except RuntimeError:
            arcpy.AddError ("Error inserting new row: " + str(feature.toTuple()))
            raise arcpy.ExecuteError
        if len(feature.photos) > 0:
            for kmzPhotoPath, gdbPhotoPath in feature.photos: # kmzPhotoPath not used here
                gdbPhotoPath = os.path.join(self.projectFolder, self.photos_dir, gdbPhotoPath)
                try:
                    self.cursor['Photos'].insertRow ((feature.featureType, objectid, gdbPhotoPath))
                except RuntimeError:
                    arcpy.AddError ("Error inserting photos to table: " + gdbPhotoPath)
                    raise arcpy.ExecuteError
    
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
        if isKML(self.filename):
            return []

        raw = dom.childNodes[0].data

        photoList = []
        for photo in RE_IMG.findall(raw):
            kmzImagePath = sanitizeFilename(photo[len('images/'):])
            gdbImagePath = self.filename[:-4] + '_' + kmzImagePath # [:-4] removes file extension
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

def isKMZ (filename):
    return filename[-3:].lower() == 'kmz'

def isKML (filename):
    return filename[-3:].lower() == 'kml'

def getDataObj (filename, photos_path):
    if isKMZ(filename):
        return KMZ(filename, photos_path)
    elif isKML(filename):
        return KML(filename)

kmz_path     = arcpy.GetParameterAsText(1)
gdb_path     = arcpy.GetParameterAsText(2)
fc_points    = arcpy.GetParameterAsText(3)
fc_lines     = arcpy.GetParameterAsText(4)
table_photos = arcpy.GetParameterAsText(5)
photos_path  = arcpy.GetParameterAsText(6)

data = getDataObj(kmz_path, photos_path)
gdb = GDB(gdb_path, fc_points, fc_lines, table_photos)
data.process(gdb)
