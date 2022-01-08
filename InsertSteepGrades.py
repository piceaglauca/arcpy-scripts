import csv
import arcpy
import datetime

def uniqueNumber():
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')

albers=arcpy.SpatialReference(3005)
utm=arcpy.SpatialReference(26909)

file=open('N:/Strategic_Group/Projects/21-1547-30 Galore Creek Mine Access Study/Phase/GeoData_Working/Anuk_Grades.csv','r')
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

fc_splitpoints = 'temp_{}'.format(uniqueNumber())
steepSegments = []
try:
    arcpy.CreateFeatureclass_management(gdb, fc_splitpoints, "POINT", spatial_reference=albers)
    cleanup_fcs.append(fc_splitpoints)

    editor.startEditing()
    editor.startOperation()
    cursor=arcpy.da.InsertCursor(fc_splitpoints,['SHAPE@'])
    inSteepSegment=False
    for row in rows:
        x=row[0]
        y=row[1]
        point=arcpy.PointGeometry(arcpy.Point(x, y), utm).projectAs(albers)

        if row[2] == '':
            break

        grade=abs(int(row[2]))
        if not inSteepSegment and grade <= 20:
            continue
        elif inSteepSegment and grade > 20:
            continue
        elif not inSteepSegment and grade > 20:
            inSteepSegment = True
            steepSegments.append([point])
        elif inSteepSegment and grade <= 20:
            inSteepSegment = False
            steepSegments[-1].append(point)
        cursor.insertRow(point)

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
    arcpy.SplitLineAtPoint_management('FEL2A_LLine_Prelim', fc_splitpoints, fc_splitroad, "1 Meter")
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
        if isCoincident(segment[0], steepSegment):
            steepPolylines.append(segment)
    search.reset()

#########
### Insert steep segments into FEL2A_LLine_SteepGrades

fc_steepgrades = 'FEL2A_LLine_SteepGrades'
try:
    editor.startEditing()
    editor.startOperation()
    cursor=arcpy.da.InsertCursor(fc_steepgrades, ['SHAPE@','Road_Name','Road_Code'])
    for segment in steepPolylines:
        cursor.insertRow (segment)
    editor.stopOperation()
    editor.stopEditing(True)
except:
    editor.stopOperation()
    editor.stopEditing(False)
    cleanup()
    raise

cleanup()
