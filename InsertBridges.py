import csv
import arcpy
albers=arcpy.SpatialReference(3005)
utm=arcpy.SpatialReference(26909)

file=open('N:/Strategic_Group/Projects/21-1547-30 Galore Creek Mine Access Study/Phase/GeoData_Working/Realignment Bridges.csv','r')
reader=csv.reader(file)
rows=[]
for row in reader:
    rows.append(row)

rows=rows[1:]

gdb='G:/Projects/Various_Clients/Galore Creek/WorkingData.gdb'
arcpy.env.workspace = gdb
editor=arcpy.da.Editor(gdb)
editor.startEditing()
editor.startOperation()
cursor=arcpy.da.InsertCursor('Bridges_Proposed',['LOA','Road_Code','SHAPE@'])

try:
    for row in rows:
        x=row[0]
        y=row[1]
        point=arcpy.PointGeometry(arcpy.Point(x, y), utm).projectAs(albers)
        attr=row[2:]
        for i in range(0,len(attr)):
            if attr[i] == '':
                attr[i] = None
        attr.append(point)
        cursor.insertRow(attr)
except:
    editor.stopOperation()
    editor.stopEditing(False)
    raise

editor.stopOperation()
editor.stopEditing(True)
