import csv
import arcpy

#albers=arcpy.SpatialReference(3005)
albers=arcpy.SpatialReference(26909) # we're not using Albers anymore
utm=arcpy.SpatialReference(26909)

gdb='G:/Projects/Various_Clients/Galore Creek/Mapping_Data.gdb'
arcpy.env.workspace = gdb
editor=arcpy.da.Editor(gdb)
editor.startEditing()
editor.startOperation()

##
# Get bridges from templates layer

cursor=arcpy.da.SearchCursor("FEL2A_LLine/RoadTemplate",
                             ['SHAPE@','RoadName','RoadCode'],
                             u"{} like 'BR%' and {} like '2021-005J%'".format(
                                arcpy.AddFieldDelimiters("FEL2A_LLine/RoadTemplate",'Template'),
                                arcpy.AddFieldDelimiters("FEL2A_LLine/RoadTemplate",'RoadCode')))

results=list(cursor)

cursor=arcpy.da.InsertCursor('Bridges',['RoadName','RoadCode','LOA','SHAPE@'])

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
