import csv
import arcpy
import datetime

def uniqueNumber():
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')

albers=arcpy.SpatialReference(3005)
utm=arcpy.SpatialReference(26909)

file=open('N:/Strategic_Group/Projects/21-1547-30 Galore Creek Mine Access Study/Phase/GeoData_Working/grades.csv','r')
reader=csv.reader(file)
rows=[]
for row in reader:
    rows.append(row)
file.close()

rows=rows[1:]

gdb='G:/Projects/Various_Clients/Galore Creek/WorkingData.gdb'
arcpy.env.workspace = gdb
editor=arcpy.da.Editor(gdb)
cleanup_fcs=[]

#########
### Cleanup by removing temp files

def cleanup():
    mxd = arcpy.mapping.MapDocument('CURRENT')
    df = mxd.activeDataFrame

    for fc in cleanup_fcs:
        lyr = arcpy.mapping.ListLayers(mxd, fc, df)

        if len(lyr) == 1 and type(lyr[0]) is arcpy.mapping.Layer:
            arcpy.mapping.RemoveLayer(df, lyr[0])
            arcpy.Delete_management(fc)
        else:
            raise ("problem cleaning up")


class SteepSegment:
    def __init__(self, road, grade, start, end):
        self.roadName = None
        self.roadCode = road
        self.grade = grade
        self.start = start
        self.end = end
        self.polyline = None


#########
### Insert split points into temp feature class

fc_splitpoints = 'temp_{}'.format(uniqueNumber())
steepSegments = []
try:
    arcpy.CreateFeatureclass_management(gdb, fc_splitpoints, "POINT", spatial_reference=albers)
    cleanup_fcs.append(fc_splitpoints)

    editor.startEditing()
    editor.startOperation()
    cursor=arcpy.da.InsertCursor(fc_splitpoints,['SHAPE@'])
    splitPoints = []
    for row in rows:
        road=row[0]
        grade=abs(int(row[1]))
        startX=row[2]
        startY=row[3]
        endX=row[4]
        endY=row[5]
        start=arcpy.PointGeometry(arcpy.Point(startX, startY), utm).projectAs(albers)
        end=arcpy.PointGeometry(arcpy.Point(endX, endY), utm).projectAs(albers)

        if start not in splitPoints:
            splitPoints.append(start)
            cursor.insertRow(start)
        if end not in splitPoints:
            splitPoints.append(end)
            cursor.insertRow(end)

        steepSegments.append(SteepSegment(road, grade, start, end))

    editor.stopOperation()
    editor.stopEditing(True)
except:
    editor.stopOperation()
    editor.stopEditing(False)
    cleanup()
    raise


#########
### Split FEL2A_LLine_Prelim at split points

fc_splitroad = 'temp_{}'.format(uniqueNumber())
try:
    arcpy.SplitLineAtPoint_management('FEL2A_LLine_MAPPING_PURPOSES', fc_splitpoints, fc_splitroad, "1 Meter")
    cleanup_fcs.append(fc_splitroad)
except:
    editor.stopOperation()
    editor.stopEditing(False)
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

search = arcpy.da.SearchCursor(fc_splitroad, ['SHAPE@','Road_Name','Road_Code'])
steepPolylines = []
for steepSegment in steepSegments:
    for segment in search:
        if isCoincident(segment[0], (steepSegment.start, steepSegment.end)):
            steepSegment.polyline = segment[0]
            steepSegment.roadName = segment[1]
            steepPolylines.append(steepSegment)
    search.reset()

#########
### Insert steep segments into FEL2A_LLine_SteepGrades

fc_steepgrades_anuk = 'FEL2A_LLine_SteepGrades_Anuk'
fc_steepgrades_asr = 'FEL2A_LLine_SteepGrades'
try:
    editor.startEditing()
    editor.startOperation()
    anuk_cursor=arcpy.da.InsertCursor(fc_steepgrades_anuk, ['SHAPE@','Road_Name','Road_Code','Grade'])
    asr_cursor=arcpy.da.InsertCursor(fc_steepgrades_asr, ['SHAPE@','Road_Name','Road_Code','Grade'])
    for segment in steepPolylines:
        cursor = None
        if segment.roadCode.startswith('AN'):
            cursor = anuk_cursor
        else:
            cursor = asr_cursor
        cursor.insertRow ((segment.polyline, segment.roadName, segment.roadCode, segment.grade))
    editor.stopOperation()
    editor.stopEditing(True)
except:
    editor.stopOperation()
    editor.stopEditing(False)
    cleanup()
    raise

cleanup()
