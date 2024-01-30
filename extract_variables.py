from setup_gloric import *

#Formatted gauges
stations_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
grdcp_cleanjoin = os.path.join(stations_gdb, "grdc_p_o{}y_cleanjoin".format(min_record_length))


#Databases of anthropogenic variables
ghspop_gdb = os.path.join(resdir, 'ghspop_processing.gdb')
ghsbuilt_gdb = os.path.join(resdir, 'ghsbuilt_processing.gdb')
aei_gdb = os.path.join(resdir, 'aei_processing.gdb')
gdw_gdb = os.path.join(resdir, 'gdw_processing.gdb')
hyde_gdb = os.path.join(resdir, 'hyde_processing.gdb')

#Extract to table
anthropo_stats_tab = os.path.join(stations_gdb, 'stations_anthropo_stats_upst')
if not arcpy.Exists(anthropo_stats_tab):
    # Get files to extract
    tabs_to_extract = getfilelist(ghspop_gdb, 'GHS_POP_E[0-9]{4}_GLOBE_R2023A_4326_3ss_V1_0_acc', gdbf=True) \
                      + getfilelist(ghsbuilt_gdb, 'GHS_BUILT_S_E[0-9]{4}_GLOBE_R2023A_4326_3ss_V1_0_acc', gdbf=True) \
                      + getfilelist(aei_gdb, 'G_AEI_[0-9]{4}_acc', gdbf=True) \
                      + getfilelist(hyde_gdb, 'cropland[0-9]{4}AD_acc', gdbf=True) \
                      + getfilelist(gdw_gdb, 'gdw_dor_res_[0-9]{4}', gdbf=True)

    Sample(in_rasters=tabs_to_extract,
           in_location_data=grdcp_cleanjoin,
           out_table=anthropo_stats_tab,
           resampling_type='NEAREST',
           unique_id_field='grdc_no'
           )

anthropo_stats_csv = os.path.join(resdir, f'{os.path.split(anthropo_stats_tab)[1]}.csv')
if not arcpy.Exists(anthropo_stats_csv):
    arcpy.CopyRows_management(anthropo_stats_tab,
                              anthropo_stats_csv)