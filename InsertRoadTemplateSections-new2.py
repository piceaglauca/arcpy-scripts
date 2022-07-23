import csv
import arcpy
import datetime
import random

def uniqueNumber():
    return '{}{}'.format(datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'),random.randint(0,100))

#albers=arcpy.SpatialReference(3005) # we're not using Albers anymore
utm=arcpy.SpatialReference(26909)


class RoadTemplate:
    def __init__(self, road, template, start, end):
        self.roadName = None
        self.roadCode = road
        self.template = template
        self.start = start
        self.end = end
        self.polyline = None


########
### Process data

file=open('N:/Strategic_Group/Projects/22-1633-30 Galore Creek Mine Access Study 2022/Phase/GeoData_Working/templ.csv','r')
reader=csv.reader(file)
roadTemplates = {}
for row in reader:
    if row[1] == 'Tmpl' or row[1] == '':
        continue

    roadCode = row[0]
    template = row[1]
    startX = row[2]
    startY = row[3]
    endX = row[4]
    endY = row[5]

    start=arcpy.PointGeometry(arcpy.Point(startX, startY), utm)
    end=arcpy.PointGeometry(arcpy.Point(endX, endY), utm)

    if roadCode not in roadTemplates.keys():
        roadTemplates[roadCode] = []

    roadTemplates[roadCode].append(RoadTemplate(roadCode, template, start, end))
file.close()

gdb='G:/Projects/Various_Clients/Galore Creek/Mapping_Data_2022.gdb'
arcpy.env.workspace = gdb
editor=arcpy.da.Editor(gdb)
cleanup_fcs=[]

#########
### Cleanup by removing temp files

def cleanup(skip = False):
    if skip:
        return

    mxd = arcpy.mapping.MapDocument('CURRENT')
    df = mxd.activeDataFrame

    for fc in cleanup_fcs:
        lyr = arcpy.mapping.ListLayers(mxd, fc, df)

        if len(lyr) == 1 and type(lyr[0]) is arcpy.mapping.Layer:
            arcpy.mapping.RemoveLayer(df, lyr[0])
            arcpy.Delete_management(fc)
        else:
            raise ("problem cleaning up")


#######
### Process road templates

for roadCode in roadTemplates.keys():
    #########
    ### Insert split points into temp feature class

    fc_splitpoints = 'temp_{}'.format(uniqueNumber())
    try:
        arcpy.CreateFeatureclass_management(gdb, fc_splitpoints, "POINT", spatial_reference=utm)
        cleanup_fcs.append(fc_splitpoints)

        editor.startEditing()
        editor.startOperation()
        cursor=arcpy.da.InsertCursor(fc_splitpoints,['SHAPE@'])
        splitPoints = []
        for segment in roadTemplates[roadCode]:
            if segment.start not in splitPoints:
                splitPoints.append(segment.start)
                cursor.insertRow(segment.start)
            if segment.end not in splitPoints:
                splitPoints.append(segment.end)
                cursor.insertRow(segment.end)
        editor.stopOperation()
        editor.stopEditing(True)
    except:
        editor.stopOperation()
        editor.stopEditing(False)
        cleanup()
        raise


    #########
    ### Get specific road from FEL2A LLine, and split at split points

    try:
        fc_specificroad = 'temp_{}'.format(uniqueNumber())
        arcpy.CreateFeatureclass_management(gdb, fc_specificroad, "POLYLINE", spatial_reference=utm)
        cleanup_fcs.append(fc_specificroad)

        arcpy.FeatureClassToFeatureClass_conversion('FEL2B_LLine/FEL2B_LLine', gdb, fc_specificroad, """ "RoadCode" = '{}' """.format(roadCode))

        fc_splitroad = 'temp_{}'.format(uniqueNumber())
        arcpy.SplitLineAtPoint_management(fc_specificroad, fc_splitpoints, fc_splitroad, "1 Meter")
        cleanup_fcs.append(fc_splitroad)
    except:
        #editor.stopOperation()
        #editor.stopEditing(False)
        cleanup()
        raise

    #########
    ### Get template segments from fc_splitroad

    def isCoincident(line, points):
        "Return True if the beginning and end of line is in points"

        def approxEqual(p1, p2):
            return abs(p1.X - p2.X) < 1 and abs(p1.Y - p2.Y) < 1

        return (approxEqual(line.firstPoint, points[0].firstPoint) and
                    approxEqual(line.lastPoint, points[1].firstPoint)) or \
               (approxEqual(line.lastPoint, points[0].firstPoint) and
                    approxEqual(line.firstPoint, points[1].firstPoint)) 

    search = arcpy.da.SearchCursor(fc_splitroad, ['SHAPE@','RoadName','RoadCode'])
    templPolylines = []
    for roadTemplate in roadTemplates[roadCode]:
        for segment in search:
            if isCoincident(segment[0], (roadTemplate.start, roadTemplate.end)):
                roadTemplate.polyline = segment[0]
                roadTemplate.roadName = segment[1]
                templPolylines.append(roadTemplate)
        search.reset()

    #########
    ### Insert template segments into road templates

    fc_roadtemplates = 'FEL2B_LLine/FEL2B_RoadTemplate'
    try:
        editor.startEditing()
        editor.startOperation()
        cursor=arcpy.da.InsertCursor(fc_roadtemplates, ['SHAPE@','RoadName','RoadCode','Template'])
        for segment in templPolylines:
            cursor.insertRow ((segment.polyline, segment.roadName, segment.roadCode, segment.template))
        editor.stopOperation()
        editor.stopEditing(True)
    except:
        editor.stopOperation()
        editor.stopEditing(False)
        cleanup()
        raise

cleanup()
