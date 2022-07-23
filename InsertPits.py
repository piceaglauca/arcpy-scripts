import csv
import arcpy
albers=arcpy.SpatialReference(3005)
utm=arcpy.SpatialReference(26909)

file=open('N:/Strategic_Group/Projects/21-1547-30 Galore Creek Mine Access Study/Phase/GeoData_Working/bq_000_pits.csv','r')
reader=csv.reader(file)
rows=[]
for row in reader:
    rows.append(row)

rows=rows[1:]

gdb='G:/Projects/Various_Clients/Galore Creek/Mapping_Data.gdb'
arcpy.env.workspace = gdb
editor=arcpy.da.Editor(gdb)
editor.startEditing()
editor.startOperation()
cursor=arcpy.da.InsertCursor('Pits_SpoilSites',['RoadCode','CHAINAGE','RoadName','SHAPE@'])

try:
    for row in rows:
        x=row[2]
        y=row[3]
        road=row[0]
        chainage=row[1]
        point=arcpy.PointGeometry(arcpy.Point(x, y), utm).projectAs(albers)
        cursor.insertRow((road, chainage, 'Bob Quinn', point))
except:
    editor.stopOperation()
    editor.stopEditing(False)
    raise

editor.stopOperation()
editor.stopEditing(True)
