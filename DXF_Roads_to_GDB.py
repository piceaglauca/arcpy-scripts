import arcpy

gdb='G:/Projects/Various_Clients/Galore Creek/WorkingData.gdb'
arcpy.env.workspace = gdb
editor = arcpy.da.Editor(gdb)
editor.startEditing()
editor.startOperation()
insertCursor = arcpy.da.InsertCursor('FEL2A_LLine_Prelim',['Road_Code','SHAPE@'])
mxd = arcpy.mapping.MapDocument("CURRENT")
#roads=['AN_000','AN_006','AN_018','AN_029','BC_000','BC_015','BC_032','BC_039','BC_048','BC_056','BC_067','BC_073','BC_083','BC_089','BC_098','BC_104','BC_111','BC_122']

try:
    group = 'FEL2A L-Line DXF'
    for lyr in arcpy.mapping.ListLayers(mxd):
        if lyr.name == group:
            layers = arcpy.mapping.ListLayers(lyr)[1:]
            break

    for lyr in layers:
        if lyr.name.endswith ('.dxf Polyline'):
            where_clause = u'{} = \'ALIGNMENT\' and {} <> \'Insert\''.format(arcpy.AddFieldDelimiters(lyr, 'Layer'), arcpy.AddFieldDelimiters(lyr, 'Entity'))
            searchCursor = arcpy.da.SearchCursor(lyr, 'SHAPE@', where_clause)
            
            merged = None
            for row in searchCursor:
                if merged is None:
                    merged = row[0]
                else:
                    merged = merged.union(row[0])

            insertCursor.insertRow((lyr.name[:6],merged))

except:
    editor.stopOperation()
    editor.stopEditing(False)
    raise

editor.stopOperation()
editor.stopEditing(True)
