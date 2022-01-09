import csv
import arcpy
albers=arcpy.SpatialReference(3005)
utm=arcpy.SpatialReference(26909)

gdb='G:/Projects/Various_Clients/Galore Creek/WorkingData.gdb'
arcpy.env.workspace = gdb
editor=arcpy.da.Editor(gdb)
editor.startEditing()
editor.startOperation()

##
# Get bridges from templates layer

cursor=arcpy.da.SearchCursor("FEL2A_LLine_RoadTemplateSections",
                             ['SHAPE@','Road_Name','Road_Code'],
                             u"{} like 'BR%' and {} in ('South More','Anuk')".format(
                                arcpy.AddFieldDelimiters("FEL2A_LLine_RoadTemplateSections",'Template'),
                                arcpy.AddFieldDelimiters("FEL2A_LLine_RoadTemplateSections",'Road_Name')))

results=list(cursor)

cursor=arcpy.da.InsertCursor('Bridges_Proposed',['Road_Name','Road_Code','LOA','SHAPE@'])

try:
    for row in results:
        start=row[0].firstPoint
        end=row[0].lastPoint
        midpoint=arcpy.PointGeometry(arcpy.Point((start.X + end.X)/2,(start.Y + end.Y)/2),albers)

        attr=list(row[1:])
        for i in range(0,len(attr)):
            if attr[i] == '':
                attr[i] = None
        attr.append(round(row[0].length,1))
        attr.append(midpoint)
        cursor.insertRow(attr)
except:
    editor.stopOperation()
    editor.stopEditing(False)
    raise

editor.stopOperation()
editor.stopEditing(True)
