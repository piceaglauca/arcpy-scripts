import csv
import arcpy
albers=arcpy.SpatialReference(3005)
utm=arcpy.SpatialReference(26909)

file=open('N:/Strategic_Group/Projects/21-1547-30 Galore Creek Mine Access Study/Phase/GeoData_Working/Base Case Elevations.csv','r')
reader=csv.reader(file)
rows=[]
for row in reader:
    rows.append(row)

rows=rows[2:]

gdb='G:/Projects/Various_Clients/Galore Creek/WorkingData.gdb'
arcpy.env.workspace = gdb
editor=arcpy.da.Editor(gdb)
editor.startEditing()
editor.startOperation()
cursor=arcpy.da.InsertCursor('FEL2A_LLine_Elevations',['Chainage','Elevation','Road_Code','SHAPE@'])

try:
    for row in rows:
        x=row[0]
        y=row[1]
        point=arcpy.PointGeometry(arcpy.Point(x, y), utm).projectAs(albers)
        attr=[float(row[2]),float(row[3]),row[4]]
        attr.append(point)
        cursor.insertRow(attr)
except:
    editor.stopOperation()
    editor.stopEditing(False)
    raise

editor.stopOperation()
editor.stopEditing(True)
