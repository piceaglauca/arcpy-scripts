import csv
import arcpy
import datetime

def uniqueNumber():
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')

albers=arcpy.SpatialReference(3005)
utm=arcpy.SpatialReference(26909)

file=open('N:/Strategic_Group/Projects/21-1547-30 Galore Creek Mine Access Study/Phase/GeoData_Working/Road Template Sections.csv','r')
reader=csv.reader(file)
rows=[]
for row in reader:
    rows.append(row)
file.close()

rows=rows[2:]

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


#########
### Insert split points into temp feature class

def mkPoint(x, y):
    return arcpy.PointGeometry(arcpy.Point(x, y), utm).projectAs(albers)

fc_splitpoints = 'temp_{}'.format(uniqueNumber())
templateSegments = []
splitpoints = []
try:
    arcpy.CreateFeatureclass_management(gdb, fc_splitpoints, "POINT", spatial_reference=albers)
    cleanup_fcs.append(fc_splitpoints)

    editor.startEditing()
    editor.startOperation()
    cursor=arcpy.da.InsertCursor(fc_splitpoints,['SHAPE@'])

    road = rows[0][3]
    template = rows[0][2]
    templateSegments = [[road, template, mkPoint(rows[0][0], rows[0][1])]]
    for i in range(1, len(rows)):
        if road != rows[i][3]:
            templateSegments[-1].append(mkPoint (rows[i-1][0],rows[i-1][1]))
            template = rows[i][2]
            road = rows[i][3]
            templateSegments.append([road, template, mkPoint(rows[i][0], rows[i][1])])
            continue

        if template != rows[i][2]:
            point = mkPoint (rows[i][0], rows[i][1])

            templateSegments[-1].append(point)
            template = rows[i][2]
            templateSegments.append([road, template, point])
            splitpoints.append(point)

            cursor.insertRow(point)
    templateSegments[-1].append(mkPoint(rows[-1][0],rows[-1][1]))

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
    arcpy.SplitLineAtPoint_management('FEL2A_LLine_Prelim', fc_splitpoints, fc_splitroad, "0.1 Meter")
    cleanup_fcs.append(fc_splitroad)
except:
    editor.stopOperation()
    editor.stopEditing(False)
    cleanup()
    raise

#########
### Get template segments from fc_splitroad

def isCoincident(line, points, tolerance=1):
    "Return True if the beginning and end of line is in points"

    def approxEqual(p1, p2):
        return abs(p1.X - p2.X) < tolerance and abs(p1.Y - p2.Y) < tolerance

    return (approxEqual(line.firstPoint, points[0].firstPoint) and
                approxEqual(line.lastPoint, points[1].firstPoint)) or \
           (approxEqual(line.lastPoint, points[0].firstPoint) and
                approxEqual(line.firstPoint, points[1].firstPoint)) 

search = arcpy.da.SearchCursor(fc_splitroad, ['SHAPE@','Road_Name','Road_Code'])
templatePolylines = []
lonelySegments = []
for templateSegment in templateSegments:
    foundSegment = False
    for segment in search:
        if isCoincident(segment[0], templateSegment[2:]):
            templatePolylines.append(segment + (templateSegment[1],))
            foundSegment = True
            break
        if isCoincident(segment[0], templateSegment[2:], 5):
            templatePolylines.append(segment + (templateSegment[1],))
            foundSegment = True
            break
    if not foundSegment:
        lonelySegments.append (templateSegment)
    search.reset()

#########
### Insert steep segments into FEL2A_LLine_SteepGrades

fc_templatesections = 'FEL2A_LLine_RoadTemplateSections'
try:
    editor.startEditing()
    editor.startOperation()
    cursor=arcpy.da.InsertCursor(fc_templatesections, ['SHAPE@','Road_Name','Road_Code','Template'])
    for segment in templatePolylines:
        cursor.insertRow (segment)
    editor.stopOperation()
    editor.stopEditing(True)
except:
    editor.stopOperation()
    editor.stopEditing(False)
    cleanup()
    raise

cleanup()
