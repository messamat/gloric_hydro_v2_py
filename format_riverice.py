import arcpy
import pandas as pd

from setup_gloric import *

riverice_dir = os.path.join(datdir, 'riverice')
riverice_tab = os.path.join(riverice_dir, 'global_river_ice_dataset.csv')
landsat_tiles = os.path.join(riverice_dir, "WRS2_descending.shp")

#Formatted gauges
stations_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
grdcp_clean = os.path.join(stations_gdb, "grdc_p_o{}y_clean".format(min_record_length))

#
ice_processgdb = os.path.join(resdir, 'riverice_processing.gdb')
pathcheckcreate(ice_processgdb)


#Outputs
landsat_subice = os.path.join(ice_processgdb, 'landsat_tiles_subice')
landsat_subgauges = os.path.join(ice_processgdb, 'landsat_tiles_subicegauges')


#Subset tiles based on those that have river ice at some point
riverice_df = pd.read_csv(riverice_tab)
#Use the same criteria as Yang et al. 2020 +  only keep those records with ice to subset tiles
if not arcpy.Exists(landsat_subice):
    riverice_df_sub = riverice_df.loc[((riverice_df['N_clear_river_pixel']>333)
                                       & (riverice_df['topo_shadow']>=0.95)
                                       & (riverice_df['cloud_fraction']<=0.25)
                                       )]

    riverice_95perc = riverice_df_sub.groupby(['ROW', 'PATH'])['river_ice_fraction'].quantile(.95).reset_index()


    subtiles = set(riverice_95perc["PATH"].astype(str) + '_' + riverice_95perc["ROW"].astype(str))

    arcpy.CopyFeatures_management(landsat_tiles, landsat_subice)
    arcpy.AddField_management(landsat_subice, 'ice95perc', 'FLOAT')
    with arcpy.da.UpdateCursor(landsat_subice, ['PATH', 'ROW', 'ice95perc']) as cursor:
        for row in cursor:
            if f'{row[0]}_{row[1]}' in subtiles:
                row[2] =  riverice_95perc.loc[
                    (riverice_95perc['PATH']==row[0]) & (riverice_95perc['ROW']==row[1]),
                    'river_ice_fraction'].values[0]
                cursor.updateRow(row)

#Join gauges to tiles
grdcp_landsatjoin = os.path.join(stations_gdb, f'{grdcp_clean}_landsatjoin')
if not arcpy.Exists(grdcp_landsatjoin):
    arcpy.SpatialJoin_analysis(target_features=grdcp_clean,
                               join_features=landsat_tiles,
                               out_feature_class=grdcp_landsatjoin,
                               join_operation='JOIN_ONE_TO_MANY',
                               join_type='KEEP_COMMON',
                               match_option='WITHIN')

landsat_grdcp_sub = os.path.join(ice_processgdb, f'landsat_{os.path.split(grdcp_clean)[1]}_sub')
if not arcpy.Exists(landsat_grdcp_sub):
    arcpy.MakeFeatureLayer_management(landsat_subice, 'landsat_subice_lyr',
                                      where_clause='ice95perc >= 0.1')
    arcpy.SelectLayerByLocation_management('landsat_subice_lyr',
                                           overlap_type='INTERSECT',
                                           select_features=grdcp_clean
                                           )
    arcpy.CopyFeatures_management('landsat_subice_lyr', landsat_grdcp_sub)

#Convert tiles to river pixels by mask
Con(255)

DN = 255

#Extract average elevation within those pixels
