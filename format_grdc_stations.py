import arcpy

from setup_gloric import *

wgs84 = arcpy.SpatialReference(4326)

#----------------------------------------- Input variables -------------------------------------------------------------
stations_dir = os.path.join(datdir, 'gauges')
pre_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
pathcheckcreate(pre_gdb)

#---- Original data from GRDC
stations_xltab = os.path.join(stations_dir, 'grdc', 'GRDC_Stations.xlsx')
stations_qdat = os.path.join(stations_dir, 'grdc', 'q_day')

#---- Data from Messager et al. 2021
gires_stationsp = os.path.join(stations_dir, 'gires', 'gires.gdb', 'grdcstations_riverjoinedit')

#---- Data from HydroATLAS
hydroriv = os.path.join(datdir, 'hydroatlas', 'HydroRIVERS_v10.gdb', 'HydroRIVERS_v10')
up_area = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')

#---- Others already checked
others_checked = os.path.join(pre_gdb, "grdc_p_o20y_tocheck_snap_riverjoin_edit_20240125")

#----------------------------------------- Output variables ------------------------------------------------------------
grdcp_all = os.path.join(pre_gdb, 'grdc_p_all')
grdcp_sub = os.path.join(pre_gdb, 'grdc_p_o{}y'.format(min_record_length)) #min_record_length in setup_gloric.py


grdcp_already_checked = "{}_checked".format(grdcp_sub)
grdcp_to_check = "{}_tocheck".format(grdcp_sub)
grdcp_to_check_snap = "{}_snap_riverjoin".format(grdcp_to_check)
grdcp_to_check_edit = "{}_snap_riverjoin_edit".format(grdcp_to_check)
grdcp_merge = "{}_merged".format(grdcp_sub)
grdcp_clean = "{}_clean".format(grdcp_sub)
grdcp_cleanjoin = "{}_cleanjoin".format(grdcp_sub)

grdcp_cleanjoin_tab = os.path.join(resdir, '{}.csv'.format(
    os.path.split(grdcp_cleanjoin)[1]
))

#----------------------------------------- Analysis --------------------------------------------------------------------
def create_points_from_pd(in_pd, x, y, scratch_dir, out_fc, crs, overwrite=False):
    if (not arcpy.Exists(out_fc)) or overwrite:
        print('Creating {}'.format(out_fc))
        p_csv = os.path.join(scratch_dir, 'tab_temp.csv')
        in_pd.to_csv(p_csv)
        arcpy.XYTableToPoint_management(in_table=p_csv,
                                        out_feature_class=out_fc,
                                        x_field=x,
                                        y_field=y,
                                        coordinate_system=crs)
        arcpy.Delete_management(p_csv)
    else:
        print("{} already exists")


#Create points for all grdc stations ----------------
stations_pd = pd.read_excel(stations_xltab)

create_points_from_pd(in_pd=stations_pd,
                      x='long', y='lat',
                      scratch_dir=resdir,
                      out_fc=grdcp_all,
                      crs=wgs84,
                      overwrite=True)

#Create points for grdc stations that meet minimum record length for daily data ----------------
stations_sub_pd = stations_pd[
    ((stations_pd['d_yrs']>=min_record_length) &
     ~((stations_pd['d_yrs']<(min_record_length+10)) & (stations_pd['d_miss'] > 50)))
]
create_points_from_pd(in_pd=stations_sub_pd,
                      x='long', y='lat',
                      scratch_dir=resdir,
                      out_fc=grdcp_sub,
                      crs=wgs84,
                      overwrite=True)

#Identify grdc stations that have already been geographically QCed by Messager et al. 2021 or Doll et al. 2024 ----------------
if not arcpy.Exists(grdcp_already_checked):
    arcpy.Merge_management(inputs=[gires_stationsp], #, others_checked],
                           output=grdcp_already_checked,
                           add_source=True)

#Remove them form the set of gauges to identify those that still need to be checked
if not arcpy.Exists(grdcp_to_check):
    arcpy.CopyFeatures_management(grdcp_sub, grdcp_to_check)
    gires_checked_list = {row[0] for row in arcpy.da.SearchCursor(grdcp_already_checked, 'GRDC_NO')}

    with arcpy.da.UpdateCursor(grdcp_to_check, 'grdc_no') as cursor:
        for row in cursor:
            if (str(row[0]) in gires_checked_list):
                cursor.deleteRow()

#Snap stations to nearest river reach in RiverAtlas
if not arcpy.Exists(grdcp_to_check_snap):
    arcpy.SpatialJoin_analysis(grdcp_to_check, hydroriv, grdcp_to_check_snap,
                               join_operation='JOIN_ONE_TO_ONE', join_type="KEEP_COMMON",
                               match_option='CLOSEST_GEODESIC',
                               distance_field_name='station_river_distance')
    snapenv = [[hydroriv, 'EDGE', '1000 meters']]
    arcpy.edit.Snap(grdcp_to_check_snap, snapenv)

    ExtractMultiValuesToPoints(in_point_features=grdcp_to_check_snap,
                               in_rasters=up_area,
                               bilinear_interpolate_values='NONE')

    arcpy.AddField_management(grdcp_to_check_snap, field_name='DApercdiff', field_type='FLOAT')
    arcpy.CalculateField_management(grdcp_to_check_snap, field='DApercdiff',
                                    expression='(!area!-!up_area_skm_15s!)/!up_area_skm_15s!',
                                    expression_type='PYTHON')

#Check and correct all those that were more than 200 meters OR whose |DApercdiff| > 0.10
if not arcpy.Exists(grdcp_to_check_edit):
    arcpy.CopyFeatures_management(grdcp_to_check_snap, grdcp_to_check_edit)
    arcpy.AddField_management(grdcp_to_check_edit, 'manualsnap_mathis', 'SHORT')
    arcpy.AddField_management(grdcp_to_check_edit, 'snap_comment_mathis', 'TEXT')

    with arcpy.da.UpdateCursor(grdcp_to_check_edit,
                               ['station_river_distance', 'DApercdiff', 'manualsnap_mathis']) as cursor:
        for row in cursor:
            if (row[0] > 200) or (abs(row[1]) > 0.1):
                row[2] = '-2'
                cursor.updateRow(row)

#Extract characteristics for actual gauges locations, not the downstream end of reaches
#as long as within the same size and the same river, probably within a few kilometers, keep the station even
#if we don't know the exact location. discharge will be normalized anyways -- the hydrographic looks the same

#Checked and included the small ones that were excluded in GIRES

#Merge the ones "to check" and "checked", then remove -1
if not arcpy.Exists(grdcp_merge):
    arcpy.Merge_management([
        sorted(getfilelist(pre_gdb, os.path.split(grdcp_to_check_edit)[1], gdbf=True))[-1],
        grdcp_already_checked],
        output=grdcp_merge)

if not arcpy.Exists(grdcp_clean):
    arcpy.CopyFeatures_management(grdcp_merge, grdcp_clean)
    with arcpy.da.UpdateCursor(grdcp_clean, ['manualsnap_mathis']) as cursor:
        for row in cursor:
            if row[0] == -1:
                cursor.deleteRow()

    ftodelete_list = [f.name for f in arcpy.ListFields(grdcp_clean) if f.name not in
                      [arcpy.Describe(grdcp_clean).OIDFieldName, 'manualsnap_mathis', 'snap_comment_mathis', 'grdc_no',
                       arcpy.Describe(grdcp_clean).shapeFieldName]]
    arcpy.DeleteField_management(grdcp_clean, ftodelete_list)

 #Delete all fields, re-snap, re-join, export table
    if not arcpy.Exists(grdcp_cleanjoin):
        arcpy.SpatialJoin_analysis(grdcp_clean, hydroriv, grdcp_cleanjoin,
                                   join_operation='JOIN_ONE_TO_ONE', join_type="KEEP_ALL",
                                   match_option='CLOSEST_GEODESIC', search_radius='100 meters',
                                   distance_field_name='station_river_distance')
        snapenv = [[hydroriv, 'EDGE', '100 meters']]
        arcpy.edit.Snap(grdcp_cleanjoin, snapenv)

        ExtractMultiValuesToPoints(in_point_features=grdcp_cleanjoin,
                                   in_rasters=up_area,
                                   bilinear_interpolate_values='NONE')

        arcpy.CalculateGeometryAttributes_management(in_features=grdcp_cleanjoin,
                                                     geometry_property=[['x_geo', 'POINT_X'],
                                                                        ['y_geo', 'POINT_Y']],
                                                     coordinate_format='DD')

        CopyRows_pd(grdcp_cleanjoin, grdcp_cleanjoin_tab,
                    fields_to_copy=[f.name for f in arcpy.ListFields(grdcp_cleanjoin)])

