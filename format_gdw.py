from setup_gloric import *

gdw_gdb = os.path.join(datdir, 'anthropo', 'gdw', 'GDW_v0_3_gamma.gdb')
gdw_pt = os.path.join(gdw_gdb, 'GDW_barriers_v0_3')
gdw_poly = os.path.join(gdw_gdb, 'GDW_reservoirs_v0_3')

up_area = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')
flowdir = os.path.join(datdir, 'hydroatlas', 'flow_dir_15s_global.gdb', 'flow_dir_15s')
natdis = os.path.join(datdir, 'hydroatlas', 'discharge_wg22_1971_2000.gdb', 'dis_nat_wg22_ls_year')

gdw_processgdb = os.path.join(resdir, 'gdw_processing.gdb')
pathcheckcreate(gdw_processgdb)

gdw_pt_edit = os.path.join(gdw_processgdb, 'gdw_pts_edit')
gdw_poly_edit = os.path.join(gdw_processgdb, 'gdw_poly_edit')
cap_mcm_ras = os.path.join(gdw_processgdb, 'gdw_cap_mcm')
dor_ras = os.path.join(gdw_processgdb, 'gdw_dor')

gdw_res_ras = os.path.join(gdw_processgdb, 'gdw_res_ras')
gdw_dor_res = os.path.join(gdw_processgdb, 'gdw_dor_res')
#--------------------------------------------- Analysis ----------------------------------------------------------------
#Set parameters
arcpy.env.extent = arcpy.env.snapRaster = up_area

dist_fn = 'reported_to_actual_ptdist'
areadif_fn = 'DApercdiff'
yr_fn = 'year_gloric'

#Convert Null values to actual Null  -----------------------------------------------------------------------------------
if not arcpy.Exists(gdw_pt_edit):
    arcpy.CopyFeatures_management(gdw_pt, gdw_pt_edit)
    with arcpy.da.UpdateCursor(gdw_pt_edit, '*') as cursor:
        for row in cursor:
            new_row = tuple([None if (val in [-99, -9999, '-99', '-9999', '']) else val for val in row])
            row = new_row
            cursor.updateRow(row)

    #Also checked, and there are no "planned" dam points

    #Make sure that declared coordinates match actual coordinates-------------------------------------------------------
    arcpy.CalculateGeometryAttributes_management(gdw_pt_edit,
                                                 geometry_property=[['x_geo', 'POINT_X'],
                                                                    ['y_geo', 'POINT_Y']])

    if dist_fn not in [f.name for f in arcpy.ListFields(gdw_pt_edit)]:
        distset = set()
        arcpy.AddField_management(gdw_pt_edit, dist_fn, 'FLOAT')
        with arcpy.da.UpdateCursor(gdw_pt_edit, [dist_fn, 'LONG_RIV', 'LAT_RIV', 'x_geo', 'y_geo']) as cursor:
            for row in cursor:
                distval = np.sqrt((row[1]-row[3])**2 + (row[2]-row[4])**2)
                row[0] = distval
                distset.add(distval)
                cursor.updateRow(row)
        if all(x==0 for x in distset):
            arcpy.DeleteField_management(gdw_pt_edit, dist_fn)

    #Make sure that declared catchment area matches locational upstream area from raster--------------------------------
    ExtractMultiValuesToPoints(in_point_features=gdw_pt_edit,
                               in_rasters=up_area,
                               bilinear_interpolate_values='NONE')

    if areadif_fn not in [f.name for f in arcpy.ListFields(gdw_pt_edit)]:
        areadifset = set()
        arcpy.AddField_management(gdw_pt_edit, field_name=areadif_fn, field_type='FLOAT')

        area_ras_fn = os.path.splitext(os.path.split(up_area)[1])[0]
        with arcpy.da.UpdateCursor(gdw_pt_edit, [areadif_fn, 'CATCH_SKM', area_ras_fn]) as cursor:
            for row in cursor:
                if row[2] is not None:
                    if (row[2] < 0.5) and (row[1] == 0):
                        row[0] = 0
                    elif (row[2] < 0.5) and (row[1] > 0):
                        row[0] = (row[1] - row[2]) / row[2]
                    else:
                        row[0] = (row[1]-round(row[2]))/round(row[2])
                    areadifset.add(row[0])
                    cursor.updateRow(row)

        if all(x in [0, None] for x in areadifset):
            arcpy.DeleteField_management(gdw_pt_edit, areadif_fn)

    #Impute building year: if building year is None or negative, assign 1930--------------------------------------------
    if not yr_fn in [f.name for f in arcpy.ListFields(gdw_pt_edit)]:
        arcpy.AddField_management(gdw_pt_edit, yr_fn, 'SHORT')
        with arcpy.da.UpdateCursor(gdw_pt_edit, [yr_fn, 'YEAR_', 'ALT_YEAR']) as cursor:
            for row in cursor:
                if row[2] is not None:
                    refyr = min([row[1], row[2]])
                else:
                    refyr = row[1]

                if (refyr is None):
                    row[0] = 1930
                elif (refyr < 0):
                    row[0] = 1930
                else:
                    row[0] = row[1]
                cursor.updateRow(row)

    #Make sure there are no duplicate points that correspond to the same reservoir -------------------------------------
    duplidict = defaultdict(list)
    with arcpy.da.SearchCursor(gdw_pt_edit, ['GDW_ID', 'OID@', 'YEAR_']) as cursor:
        for row in cursor:
            duplidict[row[0]].append([row[1], row[2]])
    duplidict = {k: v for k,v in duplidict.items() if len(v)>=2}

#Make a raster of storage every 5 years:--------------------------------------------------------------------------------
out_cap_raslist = {}
for yr in range(1900, 2025, 5):
    out_cap_ras = "{0}_{1}".format(cap_mcm_ras, yr)
    if not arcpy.Exists(out_cap_ras):
        arcpy.MakeFeatureLayer_management(gdw_pt_edit,
                                          out_layer='gdw_yr',
                                          where_clause="{0} <= {1}".format(yr_fn, yr))
        temp_ras = os.path.join(gdw_processgdb, 'temp_ras_{}'.format(yr))
        arcpy.CopyFeatures_management('gdw_yr', temp_ras)
        print('Producing {}'.format(out_cap_ras))
        arcpy.PointToRaster_conversion(in_features=temp_ras,
                                       value_field='CAP_MCM',
                                       out_rasterdataset=out_cap_ras,
                                       cell_assignment='MAXIMUM',
                                       cellsize=up_area
                                       )
        arcpy.Delete_management(temp_ras)
        arcpy.Delete_management('gdw_yr')

    out_cap_raslist[yr] = out_cap_ras


#Accumulate storage value downstream and compute Degree of Regulation (DOR) --------------------------------------------
out_dor_list = {}
# conversion factor for the denominator:
# from thousandth of a m3/s to million m3/yr (3600*24*365.25)/(1000*1000000)
# then divided by 100 to be in percent and again by 10 to get integers in the result
convfact = (1000*1000000*10*100)/(3600*24*365.25)

for yr in range(1900, 2025, 5):
    out_dor_ras = "{0}_{1}".format(dor_ras, yr)
    if not arcpy.Exists(out_dor_ras):
        print('Producing {}'.format(out_dor_ras))
        startt = time.time()
        cap_ras = out_cap_raslist[yr]
        outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=flowdir,
                                               in_weight_raster=Raster(cap_ras),
                                               data_type="DOUBLE")

        #COmpute DOR
        CellStatistics( #Cap the output value at 10,000 (1000%)
            [
                Con(Raster(natdis)>0,
                    Int(convfact*(
                            Con(IsNull(Raster(cap_ras)),
                                outFlowAccumulation,
                                Plus(outFlowAccumulation, Raster(cap_ras)))
                            /Raster(natdis)))
                    ),
                10000], 'MINIMUM', 'NODATA'
        ).save(out_dor_ras)

        arcpy.Delete_management(outFlowAccumulation)
        print(round(time.time()-startt))

    out_dor_list[yr] = out_dor_ras


#Expand DOR values to entire surface of reservoirs to make sure that gauges that fall within them because of
#mismatch in placement account for that influence

#Create a copy of reservoirs to join point data from
if not arcpy.Exists(gdw_poly_edit):
    arcpy.CopyFeatures_management(gdw_poly, gdw_poly_edit)
    fast_joinfield(in_data=gdw_poly_edit,
                   in_field='GDW_ID',
                   join_table=gdw_pt_edit,
                   join_field='GDW_ID',
                   fields=[[yr_fn,yr_fn]])

#Rasterize reservoirs
for yr in range(1900, 2025, 5):
    out_dor_res = "{0}_{1}".format(gdw_dor_res, yr)
    if not arcpy.Exists(out_dor_res):
        print('Producing {}'.format(out_dor_res))
        arcpy.MakeFeatureLayer_management(gdw_poly_edit,
                                          out_layer='gdw_yr',
                                          where_clause="{0} <= {1}".format(yr_fn, yr))
        temp_ras = os.path.join(gdw_processgdb, 'temp_ras_{}'.format(yr))
        arcpy.CopyFeatures_management('gdw_yr', temp_ras)

        arcpy.PolygonToRaster_conversion(in_features=temp_ras,
                                         value_field='GDW_ID',
                                         out_rasterdataset=gdw_res_ras,
                                         cellsize=up_area)
        arcpy.Delete_management(temp_ras)
        arcpy.Delete_management('gdw_yr')

        #Expand the reservoir rasters by one pixel because they sometimes don't overlap with network or have
        #convoluted shapes that create holes with the raster resolution
        res_exp = arcpy.ia.FocalStatistics(
            in_raster=gdw_res_ras,
            neighborhood="Rectangle 3 3 CELL",
            statistics_type="MAJORITY",
            ignore_nodata="DATA"
        )

        zonal_dor = ZonalStatistics(in_zone_data=res_exp,
                                    zone_field='Value',
                                    in_value_raster=out_dor_list[yr],
                                    statistics_type='MAXIMUM',
                                    ignore_nodata="DATA"
                                    )
        Con(Raster(out_dor_list[yr])==0,
            zonal_dor,
            Raster(out_dor_list[yr])).save(out_dor_res)

        arcpy.Delete_management(zonal_dor)
        arcpy.Delete_management(gdw_res_ras)

