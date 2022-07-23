import csv
import arcpy
import datetime
import random

def uniqueNumber():
    return '{}{}'.format(datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'),random.randint(0,100))

#albers=arcpy.SpatialReference(3005)
albers=arcpy.SpatialReference(26909) # we're not using Albers anymore
utm=arcpy.SpatialReference(26909)


class SteepSegment:
    def __init__(self, road, grade, start, end):
        self.roadName = None
        self.roadCode = road
        self.grade = grade
        self.start = start
        self.end = end
        self.polyline = None


########
### Process data

file=open('N:/Strategic_Group/Projects/21-1547-30 Galore Creek Mine Access Study/Phase/GeoData_Working/scotsimpson_6m_grades.csv','r')
reader=csv.reader(file)
steepSegments = {}
for row in reader:
    if row[1] == 'Grade' or row[1] == '':
        continue

    roadCode = row[0]
    grade = abs(int(row[1]))
    startX = row[2]
    startY = row[3]
    endX = row[4]
    endY = row[5]

    start=arcpy.PointGeometry(arcpy.Point(startX, startY), utm).projectAs(albers)
    end=arcpy.PointGeometry(arcpy.Point(endX, endY), utm).projectAs(albers)

    if roadCode not in steepSegments.keys():
        steepSegments[roadCode] = []

    steepSegments[roadCode].append(SteepSegment(roadCode, grade, start, end))
file.close()

gdb='G:/Projects/Various_Clients/Galore Creek/Mapping_Data.gdb'
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
### Process steep grades

for roadCode in steepSegments.keys():
    #########
    ### Insert split points into temp feature class

    fc_splitpoints = 'temp_{}'.format(uniqueNumber())
    try:
        arcpy.CreateFeatureclass_management(gdb, fc_splitpoints, "POINT", spatial_reference=albers)
        cleanup_fcs.append(fc_splitpoints)

        editor.startEditing()
        editor.startOperation()
        cursor=arcpy.da.InsertCursor(fc_splitpoints,['SHAPE@'])
        splitPoints = []
        for segment in steepSegments[roadCode]:
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
        arcpy.CreateFeatureclass_management(gdb, fc_specificroad, "POLYLINE", spatial_reference=albers)
        cleanup_fcs.append(fc_specificroad)

        arcpy.FeatureClassToFeatureClass_conversion('FEL2A_LLine/LLine', gdb, fc_specificroad, """ "RoadCode" = '{}' """.format(roadCode))

        fc_splitroad = 'temp_{}'.format(uniqueNumber())
        arcpy.SplitLineAtPoint_management(fc_specificroad, fc_splitpoints, fc_splitroad, "1 Meter")
        cleanup_fcs.append(fc_splitroad)
    except:
        #editor.stopOperation()
        #editor.stopEditing(False)
        cleanup()
        raise

    #########
    ### Get steep segments from fc_splitroad

    def isCoincident(line, points):
        "Return True if the beginning and end of line is in points"

        def approxEqual(p1, p2):
            return abs(p1.X - p2.X) < 1 and abs(p1.Y - p2.Y) < 1

        return (approxEqual(line.firstPoint, points[0].firstPoint) and
                    approxEqual(line.lastPoint, points[1].firstPoint)) or \
               (approxEqual(line.lastPoint, points[0].firstPoint) and
                    approxEqual(line.firstPoint, points[1].firstPoint)) 

    search = arcpy.da.SearchCursor(fc_splitroad, ['SHAPE@','RoadName','RoadCode'])
    steepPolylines = []
    for steepSegment in steepSegments[roadCode]:
        for segment in search:
            if isCoincident(segment[0], (steepSegment.start, steepSegment.end)):
                steepSegment.polyline = segment[0]
                steepSegment.roadName = segment[1]
                steepPolylines.append(steepSegment)
        search.reset()

    #########
    ### Insert steep segments into FEL2A_LLine_SteepGrades

    fc_steepgrades = 'FEL2A_LLine/SteepGrade'
    try:
        editor.startEditing()
        editor.startOperation()
        cursor=arcpy.da.InsertCursor(fc_steepgrades, ['SHAPE@','Road_Name','Road_Code','Grade'])
        for segment in steepPolylines:
            cursor.insertRow ((segment.polyline, segment.roadName, segment.roadCode, segment.grade))
        editor.stopOperation()
        editor.stopEditing(True)
    except:
        editor.stopOperation()
        editor.stopEditing(False)
        cleanup()
        raise

cleanup()
