import os.path

import arcpy
import pandas as pd

from setup_gloric import *

riverice_dir = os.path.join(datdir, 'riverice')
riverice_tab = os.path.join(riverice_dir, 'global_river_ice_dataset.csv')
landsat_tiles = os.path.join(riverice_dir, "WRS2_descending.shp")

grwl_dir = os.path.join(datdir, 'grwl')
grwl_processgdb = os.path.join(resdir, 'grwl_preprocess.gdb')
pathcheckcreate(grwl_processgdb)
grwl_simple= os.path.join(grwl_dir, 'GRWL_summaryStats.shp')

hydrosheds_dem = os.path.join(datdir, 'hydroatlas', 'hyd_glo_dem_15s', 'hyd_glo_dem_15s.tif')

#Formatted gauges
stations_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
grdcp_clean = os.path.join(stations_gdb, "grdc_p_o{}y_clean".format(min_record_length))

#
ice_processgdb = os.path.join(resdir, 'riverice_processing.gdb')
pathcheckcreate(ice_processgdb)


#Outputs
landsat_subice = os.path.join(ice_processgdb, 'landsat_tiles_subice')
landsat_grdcp_sub = os.path.join(ice_processgdb, f'landsat_{os.path.split(grdcp_clean)[1]}_sub')
grwl_landsatinters = os.path.join(ice_processgdb, 'grwl_landsatinters')
landsat_subtiles_elvstats = os.path.join(resdir, f'landsat_{os.path.split(grdcp_clean)[1]}_sub_elvstats.csv')

#---------------------------------- Analysis --------------------------------------------------------------------------
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

if not arcpy.Exists(landsat_grdcp_sub):
    arcpy.MakeFeatureLayer_management(landsat_subice, 'landsat_subice_lyr',
                                      where_clause='ice95perc >= 0.1')
    arcpy.SelectLayerByLocation_management('landsat_subice_lyr',
                                           overlap_type='INTERSECT',
                                           select_features=grdcp_clean
                                           )
    arcpy.CopyFeatures_management('landsat_subice_lyr', landsat_grdcp_sub)


#Intersect grwl with landsat tiles
if not arcpy.Exists(grwl_landsatinters):
    arcpy.Intersect_analysis([grwl_simple, landsat_grdcp_sub],
                             out_feature_class=grwl_landsatinters,
                             join_attributes='ALL')

#Get median elevation from HydroSHEDS for lines intersecting each tile
if not arcpy.Exists(landsat_subtiles_elvstats):
    u_tiles = {row[0] for row in arcpy.da.SearchCursor(grwl_landsatinters, 'SEQUENCE')}
    stats_dict = {}
    for tile in u_tiles:
        print(tile)
        out_stats = os.path.join(grwl_processgdb, f'{os.path.split(grwl_landsatinters)[1]}_{tile}_elv')

        arcpy.MakeFeatureLayer_management(grwl_landsatinters, 'tile_lines_lyr', where_clause=f'SEQUENCE = {tile}')
        oidfn = arcpy.Describe('tile_lines_lyr').OIDFieldName

        if not arcpy.Exists(out_stats):
            Sample(in_rasters=hydrosheds_dem,
                   in_location_data='tile_lines_lyr',
                   out_table=out_stats,
                   resampling_type='NEAREST',
                   statistics_type='MEDIAN',
                   unique_id_field=oidfn)

        arcpy.AddJoin_management('tile_lines_lyr', in_field=oidfn,
                                 join_table=out_stats, join_field=f'{oidfn}')

        pxfn= f'{os.path.split(grwl_landsatinters)[1]}.nSegPx'
        statfn = f'{os.path.split(out_stats)[1]}.{os.path.splitext(os.path.split(hydrosheds_dem)[1])[0]}'
        sum_px = sum([row[0] for row in arcpy.da.SearchCursor('tile_lines_lyr', pxfn)])
        wsum_elv = sum([row[0]*row[1]
                        for row in arcpy.da.SearchCursor('tile_lines_lyr', [pxfn, statfn])
                        if row[1] is not None])
        stats_dict[tile] = wsum_elv/sum_px
        arcpy.Delete_management('tile_lines_lyr')

    #Join to tile layer and export to csv
    outfn = 'mean_elv'
    if not outfn in [f.name for f in arcpy.ListFields(landsat_grdcp_sub)]:
        arcpy.AddField_management(landsat_grdcp_sub, outfn, 'FLOAT')

    with arcpy.da.UpdateCursor(landsat_grdcp_sub, ['SEQUENCE', outfn]) as cursor:
        for row in cursor:
            if row[0] in stats_dict:
                row[1] = stats_dict[row[0]]
                cursor.updateRow(row)

    arcpy.CopyRows_management(landsat_grdcp_sub, landsat_subtiles_elvstats)

###################### NOT USED ########################################################################################
# arcpy.env.scratchWorkspace = ice_processgdb
# lyr = getfilelist(grwl_dir, '.*[.]tif$')[0]
# grwl_extdict = {lyr: project_extent(in_dataset=lyr, out_coor_system=4326, out_dataset=None)
#                 for lyr in getfilelist(grwl_dir, '.*[.]tif$')}
# grwl_seltiles = list()
# with arcpy.da.SearchCursor(landsat_grdcp_sub, 'SHAPE@') as cursor:
#     for row in cursor:
#         ls_tilext = row[0].extent
#         print(ls_tilext)
#         grwl_seltiles.extend(get_inters_tiles(ref_extent=ls_tilext,
#                                               tileiterator=grwl_extdict,
#                                               containsonly=True))
#
# #Convert tiles to river pixe elevation by mask
# grwl_seltiles_u = set(grwl_seltiles)
#
# #Get cell size ratio
# arcpy.Project_management(in_dataset=grwl_seltiles[0],
#                          out_dataset=os.path.join(ice_processgdb, 'temp_tile'),
#                          out_coor_system=hydrosheds_dem,
#                          in_coor_system=arcpy.Describe(grwl_seltiles[0]).SpatialReference)
# tiles_res = arcpy.Describe(grwl_seltiles[0]).MeanCellWidth
# cellsize_ratio = arcpy.Describe(hydrosheds_dem).meanCellWidth/tiles_res
#
#
# for tile in grwl_seltiles_u:
#     print(tile)
#     arcpy.Project_management(in_dataset=tile,
#                              out_dataset=os.path.join(ice_processgdb, 'temp_tile'),
#                              out_coor_system=hydrosheds_dem,
#                              in_coor_system=arcpy.Describe(tile).SpatialReference)
#     arcpy.env.snapRaster = hydrosheds_dem
#     Aggregate(Con(grwl_seltiles == 255, 1),
#               cell_factor=cellsize_ratio,
#               aggregation_type='MEDIAN')

# #Buffer lines to their corresponding width
# buff_list = []
# x=0
# for tile in diss_list:
#     print(x)
#     out_buffer = f'{tile}_buff'
#     if not arcpy.Exists(out_buffer):
#         arcpy.AddField_management(tile, 'buffer_size', 'TEXT')
#         with arcpy.da.UpdateCursor(tile, ['width_m', 'buffer_size']) as cursor:
#             for row in cursor:
#                 row[1] = f'{row[0]} Meters'
#                 cursor.updateRow(row)
#
#         arcpy.Buffer_analysis(tile,
#                               out_feature_class=out_buffer,
#                               buffer_distance_or_field='buffer_size',
#                               line_end_type='FLAT',
#                               method='GEODESIC',
#                               dissolve_option='ALL'
#         )
#     buff_list.append(out_buffer)
#     x+=1

# if not arcpy.Exists(grwl_sub_mosaic):
#     sublist_tab = os.path.join(resdir, 'grwl_lst_list.csv')
#     if not arcpy.Exists(sublist_tab):
#         arcpy.env.scratchWorkspace = ice_processgdb
#         lyr = getfilelist(grwl_dir, '.*[.]shp$')[0]
#         grwl_extdict = {lyr: project_extent(in_dataset=lyr, out_coor_system=4326, out_dataset=None)
#                         for lyr in getfilelist(grwl_dir, '.*[.]shp$')}
#         grwl_seltiles = list()
#         with arcpy.da.SearchCursor(landsat_grdcp_sub, 'SHAPE@') as cursor:
#             for row in cursor:
#                 ls_tilext = row[0].extent
#                 print(ls_tilext)
#                 grwl_seltiles.extend(get_inters_tiles(ref_extent=ls_tilext,
#                                                       tileiterator=grwl_extdict,
#                                                       containsonly=True))
#         grwl_seltiles_u = set(grwl_seltiles)
#
#         with open(sublist_tab, 'w') as file:
#             for line in grwl_seltiles_u:
#                 file.write(f"{line},\n")
#     else:
#         grwl_seltiles_u = set(i[0] for i in pd.read_csv(sublist_tab).values.tolist())
#
#     #Dissolve to reduce size
#     diss_list = []
#     for tile in grwl_seltiles_u:
#         out_diss = os.path.join(grwl_processgdb, f'{os.path.splitext(os.path.split(tile)[1])[0]}_diss')
#         if not arcpy.Exists(out_diss):
#             print(tile)
#             #Round field
#             arcpy.MakeFeatureLayer_management(tile, 'tile_lyr')
#             with arcpy.da.UpdateCursor('tile_lyr', 'width_m') as cursor:
#                 for row in cursor:
#                     row[0] = 10*round(row[0]/10)
#                     cursor.updateRow(row)
#             arcpy.Dissolve_management('tile_lyr',
#                                       out_feature_class=out_diss,
#                                       dissolve_field='width_m',
#                                       unsplit_lines='UNSPLIT_LINES')
#         diss_list.append(out_diss)
#
#     stats_list = []
#     for tile in diss_list:
#         out_stats = os.path.join(grwl_processgdb, f'{os.path.splitext(os.path.split(tile)[1])[0]}_elv')
#         Sample(in_rasters=hydrosheds_dem,
#                in_location_data=tile,
#                out_table=out_stats,
#                resampling_type='NEAREST',
#                statistics_type='MEDIAN'
#                )
#
#
#
#
# #Merge lines across all tiles
# if not arcpy.Exists(grwl_sub_mosaic):
#     arcpy.MosaicToNewRaster_management(input_rasters=zstats_list,
#                                        output_location=os.path.split(grwl_sub_mosaic)[0],
#                                        raster_dataset_name_with_extension=os.path.split(grwl_sub_mosaic)[1],
#                                        number_of_bands=1,
#                                        mosaic_method='MAXIMUM'
#                                        )