import arcpy

from setup_gloric import *

wgs84 = arcpy.SpatialReference(4326)

#----------------------------------------- Input variables -------------------------------------------------------------
stations_dir = os.path.join(datdir, 'gauges')

#---- Original data from GRDC
stations_xltab = os.path.join(stations_dir, 'grdc', 'GRDC_Stations.xlsx')
stations_qdat = os.path.join(stations_dir, 'grdc', 'q_day')

#---- Data from Messager et al. 2021
gires_stationsp = os.path.join(stations_dir, 'gires', 'gires.gdb', 'grdcstations_riverjoinedit')

#---- Data from Doll et al. 2024
dryver_newstations_raw = os.path.join(stations_dir, 'dryver', 'eu_stations_newgrdc_raw.shp')
dryver_newstationsp = os.path.join(stations_dir, 'dryver', 'eu_stations_newgrdc_preprocessed.shp')

#---- Data from HydroATLAS
hydroriv = os.path.join(datdir, 'hydroatlas', 'HydroRIVERS_v10.gdb', 'HydroRIVERS_v10')
up_area = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')

#----------------------------------------- Output variables ------------------------------------------------------------
pre_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
pathcheckcreate(pre_gdb)

grdcp_all = os.path.join(pre_gdb, 'grdc_p_all')
min_record_length = 20
grdcp_sub = os.path.join(pre_gdb, 'grdc_p_o{}y'.format(min_record_length))


grdcp_already_checked = "{}_checked".format(grdcp_sub)
grdcp_to_check = "{}_tocheck".format(grdcp_sub)
grdcp_to_check_snap = "{}_snap_riverjoin".format(grdcp_to_check)
grdcp_to_check_edit = "{}_snap_riverjoin_edit".format(grdcp_to_check)
grdcp_merge = "{}_merged".format(grdcp_sub)
grdcp_clean = "{}_clean".format(grdcp_sub)

#----------------------------------------- Analysis --------------------------------------------------------------------
def create_points_from_pd(in_pd, x, y, scratch_dir, out_fc, crs, overwrite=True):
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
    arcpy.Merge_management(inputs=[gires_stationsp, dryver_newstationsp],
                           output=grdcp_already_checked,
                           add_source=True)

#Remove them form the set of gauges to identify those that still need to be checked
if not arcpy.Exists(grdcp_to_check):
    arcpy.CopyFeatures_management(grdcp_sub, grdcp_to_check)
    gires_checked_list = {row[0] for row in arcpy.da.SearchCursor(grdcp_already_checked, 'GRDC_NO')}
    dryver_checked_list = {row[0] for row in arcpy.da.SearchCursor(dryver_newstations_raw, 'grdc_no')}

    with arcpy.da.UpdateCursor(grdcp_to_check, 'grdc_no') as cursor:
        for row in cursor:
            if (str(row[0]) in gires_checked_list) or (row[0] in dryver_checked_list):
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

#Merge to check and checked, then remove -1
if not arcpy.Exists(grdcp_merge):
    arcpy.Merge_management([grdcp_to_check_edit, grdcp_already_checked],
                           output=grdcp_merge)

if not arcpy.Exists(grdcp_clean):
    [f.name for f in arcpy.ListFields(grdcp_merge)]

    with arcpy.da.UpdateCursor(grdcp_merge, ['manualsnap_mathis'])



if not arcpy.Exists(grdcpjoinedit):
    arcpy.CopyFeatures_management(grdcpjoin, grdcpjoinedit)

#Delete all fields, re-snap, re-join, export table



################################################################# STUFF FROM OTHER PROJECTS ############################
#Stations
grdcstations = os.path.join(datdir, 'grdc_curated', 'high_qual_daily_stations.csv')
grdc_disdatdir = os.path.join(datdir, 'GRDCdat_day')
grdcp = os.path.join(outgdb, 'grdcstations')
grdcpjoin = os.path.join(outgdb, 'grdcstations_riverjoin')
grdcpclean = os.path.join(outgdb, 'grdcstations_clean')
grdcpcleanjoin = os.path.join(outgdb, 'grdcstations_cleanjoin')
basin5grdcpjoin = os.path.join(outgdb, 'BasinATLAS_v10_lev05_GRDCstations_join')

#Create points for grdc stations
if not arcpy.Exists(grdcp):
    print('Create points for grdc stations')
    stations_coords = {row[0]:[row[1], row[2], row[3]]
                       for row in arcpy.da.SearchCursor(grdcstations, ['GRDC_NO', 'LONG_NEW', 'LAT_NEW', 'AREA'])}
    arcpy.CreateFeatureclass_management(os.path.split(grdcp)[0], os.path.split(grdcp)[1],
                                        geometry_type='POINT', spatial_reference=wgs84)
    arcpy.AddField_management(grdcp, 'GRDC_NO', 'TEXT')
    arcpy.AddField_management(grdcp, 'GRDC_AREA', 'DOUBLE')

    with arcpy.da.InsertCursor(grdcp, ['GRDC_NO', 'GRDC_AREA', 'SHAPE@XY']) as cursor:
        for k, v in stations_coords.items():
            cursor.insertRow([k, v[2], arcpy.Point(v[0], v[1])])

#Join grdc stations to nearest river reach in RiverAtlas
if not arcpy.Exists(grdcpjoin):
    print('Join grdc stations to nearest river reach in RiverAtlas')
    arcpy.SpatialJoin_analysis(grdcp, riveratlas, grdcpjoin, join_operation='JOIN_ONE_TO_ONE', join_type="KEEP_COMMON",
                               match_option='CLOSEST_GEODESIC', search_radius=0.0005,
                               distance_field_name='station_river_distance')

    arcpy.AddField_management(grdcpjoin, field_name='DApercdiff', field_type='FLOAT')
    arcpy.CalculateField_management(grdcpjoin, field='DApercdiff',
                                    expression='(!GRDC_AREA!-!UPLAND_SKM!)/!UPLAND_SKM!',
                                    expression_type='PYTHON')

#Check and correct all those that are more than 50 meters OR whose |DApercdiff| > 0.10
if not arcpy.Exists(grdcpjoinedit):
    arcpy.CopyFeatures_management(grdcpjoin, grdcpjoinedit)
    arcpy.AddField_management(grdcpjoinedit, 'manualsnap_mathis', 'SHORT')
    arcpy.AddField_management(grdcpjoinedit, 'snap_comment_mathis', 'TEXT')

#Join grdc stations to nearest river reach in RiverAtlas
if not arcpy.Exists(grdcpjoin):
    print('Join grdc stations to nearest river reach in RiverAtlas')
    arcpy.SpatialJoin_analysis(grdcp, riveratlas, grdcpjoin, join_operation='JOIN_ONE_TO_ONE', join_type="KEEP_COMMON",
                               match_option='CLOSEST_GEODESIC', search_radius=0.0005,
                               distance_field_name='station_river_distance')

    arcpy.AddField_management(grdcpjoin, field_name='DApercdiff', field_type='FLOAT')
    arcpy.CalculateField_management(grdcpjoin, field='DApercdiff',
                                    expression='(!GRDC_AREA!-!UPLAND_SKM!)/!UPLAND_SKM!',
                                    expression_type='PYTHON')

#Check and correct all those that are more than 50 meters OR whose |DApercdiff| > 0.10
if not arcpy.Exists(grdcpjoinedit):
    arcpy.CopyFeatures_management(grdcpjoin, grdcpjoinedit)
    arcpy.AddField_management(grdcpjoinedit, 'manualsnap_mathis', 'SHORT')
    arcpy.AddField_management(grdcpjoinedit, 'snap_comment_mathis', 'TEXT')