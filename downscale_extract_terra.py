import arcpy

from setup_gloric import *

pxarea_grid = os.path.join(datdir, 'hydroatlas', 'pixel_area_skm_15s.gdb', 'px_area_skm_15s')
uparea_grid = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')

flowdir_global = os.path.join(datdir, 'hydroatlas', 'flow_dir_15s_global.gdb', 'flow_dir_15s')
flowdir_gdb = os.path.join(datdir, 'hydroatlas', 'flow_dir_15s_by_continent.gdb')
flowdir_griddict = {re.split('_', os.path.split(path)[1])[0]: path for path in getfilelist(flowdir_gdb, gdbf=True)}

terra_dir = os.path.join(datdir, 'climate', 'terra')
pdsi_dir = os.path.join(terra_dir, 'pdsi')
ppt_dir = os.path.join(terra_dir, 'ppt')
def_dir = os.path.join(terra_dir, 'def')
swe_dir = os.path.join(terra_dir, 'swe')
tmin_dir = os.path.join(terra_dir, 'tmin')
tmax_dir = os.path.join(terra_dir, 'tmax')

terra_resdir = os.path.join(resdir, 'terra')
pathcheckcreate(terra_resdir)

stations_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
stations_formatted = getfilelist(stations_gdb, 'grdc_p_o[0-9]*y_cleanjoin$', gdbf=True)[0]

# Create gdb
pred_tabgdb = os.path.join(terra_resdir, 'terra_tabs.gdb')
pathcheckcreate(path=pred_tabgdb , verbose=True)

#Output layers
stations_ws = f"{stations_formatted}_ws"

#-------------------------------------- Get temperature data at the location of stations --------------------------------
#Make a simple point dataframe from the stations
gpoints_dict = pd.DataFrame.from_dict(
    {row[0]:(row[1], row[2])
     for row in arcpy.da.SearchCursor(stations_formatted, ['grdc_no', 'x_geo', 'y_geo'])},
    orient='index',
    columns=['x_geo', 'y_geo']). \
    reset_index(). \
    rename(columns={'index': 'grdc_no'})

for var in ['tmin', 'tmax']:
    out_tab = os.path.join(resdir, f'{os.path.split(stations_formatted)[1]}_terra_{var}.csv')
    if not arcpy.Exists(out_tab):
        print(f'Extracting {var} and writing {out_tab}')
        t_filelist = getfilelist(os.path.join(terra_dir, var), 'TerraClimate_tm(in|ax)_[0-9]{4}[.]nc$')
        t_xr = xr.open_mfdataset(t_filelist)
        gauges_t_df = extract_xr_by_point(in_xr=t_xr,
                                          in_pointdf=gpoints_dict,
                                          in_df_id='grdc_no',
                                          in_xr_lon_dimname='lon', in_xr_lat_dimname='lat',
                                          in_df_lon_dimname='x_geo', in_df_lat_dimname='y_geo'
                                          )
        gauges_t_df.to_csv(os.path.join(resdir, f'{os.path.split(stations_formatted)[1]}_terra_{var}.csv'),
                           index=False)

#-------------------------------------- Define functions ---------------------------------------------------------------
def flowacc_extract_nc(in_ncpath, in_var, in_template_extentlyr, in_template_resamplelyr,
                       pxarea_grid, uparea_grid, flowdir_grid, out_resdir, scratchgdb, integer_multiplier,
                       in_location_data, id_field, out_tabdir, fieldroot, time_averaging_factor=None,
                       time_averaging_function=None, in_crs=4326, lat_dim='lat', lon_dim='lon', time_dim='time',
                       in_mask=None, save_raster=False, save_tab=True, scratch_to_memory=True):

    out_croppedintnc = os.path.join(out_resdir, f"{in_var}_croppedint.nc")
    LRpred_resgdb = os.path.join(out_resdir, f"{in_var}.gdb")
    pathcheckcreate(LRpred_resgdb)

    #Set scratch workspace to in_memory
    if scratch_to_memory:
        arcpy.env.scratchWorkspace = 'memory'
    else:
        arcpy.env.scratchWorkspace = scratchgdb

    #Read nc
    if isinstance(in_ncpath, list):
        pred_nc = xr.open_mfdataset(in_ncpath)
    elif isinstance(in_ncpath, str):
        pred_nc = xr.open_dataset(in_ncpath)

    #Get resolution
    nc_resolution = pred_nc.attrs['geospatial_lon_resolution']

    # Aggregate over time to keep less time steps-----------------------------------------------------------------------
    if time_averaging_factor is not None:
        if time_averaging_factor > 1:
            if time_averaging_function == 'mean':
                pred_nc = pred_nc.resample(time=f'{time_averaging_factor}M', closed='left').mean()
            elif time_averaging_function == 'sum':
                pred_nc = pred_nc.resample(time=f'{time_averaging_factor}M', closed='left').sum()
            else:
                raise ValueError('time_averaging_function can either be mean or sum, otherwise need to edit the function')

    #Get time step and output table names-------------------------------------------------------------------------------
    timesteps_list = [pd.to_datetime(t).strftime('%Y%m%d') for t in pred_nc['time'].values]
    out_tablist = [os.path.join(out_tabdir, f"{in_var}_stats_{ts}") for ts in timesteps_list]

    #Make sure the resolution of the NC is a multiple of the resolution of the template layer-----------------------
    templ_desc =  arcpy.Describe(in_template_resamplelyr)
    cellsize_ratio = nc_resolution / templ_desc.meanCellWidth
    aggregate_residual = (nc_resolution - math.floor(cellsize_ratio) * templ_desc.meanCellWidth) #the resolution residual left from aggregating or resampling
    if not all([(int(arcpy.GetRasterProperties_management(in_template_resamplelyr, "ROWCOUNT").getOutput(0))
                 * aggregate_residual) < (templ_desc.meanCellHeight/2),
                (int(arcpy.GetRasterProperties_management(in_template_resamplelyr, "COLUMNCOUNT").getOutput(0))
                 * aggregate_residual)  < (templ_desc.meanCellWidth / 2)]):
        raise ValueError('Resampling would cause a shift in the raster because '
                         'the resolution of the netcdf and template layer are not multiples')

    #Pre-format the netCDF to a file geodatabase raster that is ready to be resampled ----------------------------------
    # (by masking it and adjusting its values)
    if not all([arcpy.Exists(out_tab) for out_tab in out_tablist]):
        #Crop netcdf to template extent and get minimum value within that extent
        templateext = arcpy.Describe(in_template_extentlyr).extent
        cropdict = {lon_dim: slice(templateext.XMin, templateext.XMax),
                    lat_dim: slice(templateext.YMax,
                                   templateext.YMin)}  # Lat is from north to south so need to reverse slice order
        pred_nc_cropped = pred_nc.loc[cropdict]

        #Get minimum value
        min_val = int(pred_nc_cropped.PDSI.min().compute() * integer_multiplier)

        # Shift raster to positive values for running flow accumulation
        if min_val < 0:
            shiftval = -min_val
        else:
            shiftval = 0

        # Crop xarray and convert it to integer, making sure it only has positive values for flow accumulation-------------------------
        out_croppedint = os.path.join(scratchgdb, f"{in_var}_croppedint")
        if not arcpy.Exists(out_croppedint):
            print(f"Producing {out_croppedintnc}")
            if not arcpy.Exists(out_croppedintnc):
                (pred_nc_cropped * integer_multiplier). \
                    astype(np.intc). \
                    to_netcdf(out_croppedintnc)

            print(f"Saving {out_croppedintnc} to {out_croppedint} through mask")
            ncvar = re.split('_', in_var)[0]
            arcpy.md.MakeNetCDFRasterLayer(in_netCDF_file=out_croppedintnc,
                                           variable=ncvar,
                                           x_dimension=lon_dim,
                                           y_dimension=lat_dim,
                                           out_raster_layer='tmpras_check',
                                           band_dimension=time_dim,
                                           value_selection_method='BY_INDEX',
                                           cell_registration='CENTER')
            output_ras = Raster('tmpras_check')
            arcpy.DefineProjection_management(output_ras, coor_system=in_crs)

            #Aggregate mask layer to subset output raster
            arcpy.env.snapRaster = 'tmpras_check'
            mask_agg = Aggregate(in_raster=in_mask,
                                 cell_factor=round(cellsize_ratio),
                                 aggregation_type='MAXIMUM')

            arcpy.env.mask = mask_agg
            Con(output_ras >= min_val, output_ras+shiftval).save(out_croppedint)

            #Clean up
            #arcpy.Delete_management(out_croppedintnc)
            arcpy.Delete_management(mask_agg)
            arcpy.Delete_management('tmpras_check')
            arcpy.Delete_management(output_ras)
            arcpy.ClearEnvironment("mask")
            arcpy.ClearEnvironment("snapRaster")

        del pred_nc
        del pred_nc_cropped

        # Set environment
        arcpy.env.extent = arcpy.env.snapRaster = in_template_resamplelyr

        # Resample -----------------------------------------------------------------------------------------------------
        out_rsmpnear = os.path.join(pred_tabgdb, f"{in_var}_rsmpnear")
        if not arcpy.Exists(out_rsmpnear):
            print(f"Resampling {out_croppedintnc}")
            arcpy.management.Resample(in_raster=out_croppedint,
                                      out_raster=out_rsmpnear,
                                      cell_size=templ_desc.MeanCellWidth,
                                      resampling_type='NEAREST') #Go for nearestneighbor for speed

        #Iterate through all the bands to run flow accumulation and extract the accumulated value for each gauge-------
        arcpy.env.mask = mask_ws_cont
        arcpy.env.parallelProcessingFactor = '95%'
        for i in range(int(arcpy.management.GetRasterProperties(out_rsmpnear, 'BANDCOUNT').getOutput(0))):
            ts = timesteps_list[i]

            # Run weighting
            value_grid = os.path.join(out_rsmpnear, f'Band_{i + 1}')
            out_grid = os.path.join(LRpred_resgdb, f'{in_var}_{ts}')
            out_table = os.path.join(out_tabdir, f'{in_var}_stats_{ts}')

            if ((not arcpy.Exists(out_grid)) and save_raster) or \
                    ((not arcpy.Exists(out_table)) and save_tab):
                print(f"Running flow accumulation for {value_grid}")
                # Multiply input grid by pixel area
                start = time.time()
                valueXarea = Times(Raster(value_grid), Raster(pxarea_grid))
                outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=flowdir_grid,
                                                       in_weight_raster=valueXarea,
                                                       data_type="FLOAT")
                outFlowAccumulation_2 = Plus(outFlowAccumulation, valueXarea)
                UplandGrid = Int((Divide(outFlowAccumulation_2, Raster(uparea_grid))) + 0.5)-shiftval

                if save_raster:
                    UplandGrid.save(out_grid)
                if save_tab:
                    Sample(in_rasters=UplandGrid, in_location_data=in_location_data, out_table=out_table,
                           resampling_type='NEAREST', unique_id_field=id_field, layout='COLUMN_WISE',
                           generate_feature_class='TABLE')

                    arcpy.management.AlterField(out_table, field=os.path.split(in_location_data)[1],
                                                new_field_name=id_field, new_field_alias=id_field)

                    field_to_rename = [f.name for f in arcpy.ListFields(out_table) if f.name not in
                                       [id_field, 'X', 'Y', arcpy.Describe(out_table).OIDFieldName]]
                    arcpy.management.AlterField(out_table,
                                                field=field_to_rename[0],
                                                new_field_name=f'{fieldroot}_{ts}',
                                                new_field_alias=f'{fieldroot}_{ts}'
                                                )
                end = time.time()
                print(end - start)

                if scratch_to_memory:
                    arcpy.Delete_management('memory')
                else:
                    arcpy.Delete_management(valueXarea)
                    arcpy.Delete_management(outFlowAccumulation)
                    arcpy.Delete_management(outFlowAccumulation_2)
                    arcpy.Delete_management(UplandGrid)

    else:
        print("All tables already exists for {}".format(in_var))

    arcpy.ResetEnvironments()

    return(out_tablist)

def get_LRpred_pd(in_gdbtab, in_fieldroot, in_dtype, last_col=False):
                print(in_gdbtab)

                var_colname = "{0}_{1}".format(
                    in_fieldroot,
                    re.findall('[0-9]{1,8}$', os.path.split(in_gdbtab)[1])[0])

                if last_col:
                    step_pd = pd.DataFrame(data=arcpy.da.SearchCursor(in_gdbtab,
                                                                      [f.name for f in arcpy.ListFields(in_gdbtab)][-1]),
                                           dtype=in_dtype)
                    step_pd.columns = [var_colname]
                else:
                    rcols = ['grdc_no', var_colname]
                    step_pd = pd.DataFrame(data=arcpy.da.SearchCursor(in_gdbtab, rcols),
                                           columns=rcols,
                                           dtype=in_dtype)
                return(step_pd)

# ---------------------------------- Analysis --------------------------------------------------------------------------
#Extract the watershed of stations
if not arcpy.Exists(stations_ws):
    Watershed(in_flow_direction_raster=flowdir_global,
              in_pour_point_data=stations_formatted,
              pour_point_field='grdc_no').save(stations_ws)

#Get variables (netcef and multiplier to convert variable to integer)
pred_vardict = {os.path.splitext(os.path.split(f)[1])[0]: [f] for f in getfilelist(terra_dir, ".*[.]nc$")}
unique_vars = set([re.sub('(TerraClimate_)|(_[0-9]{4})', '', k) for k in pred_vardict])

for var in unique_vars: #Using the list(dict.keys()) allows to slice it the keys
    if var in ['PDSI']: #, 'ppt'
        scratchgdb_var = os.path.join(terra_resdir, 'scratch_{}.gdb'.format(var))
        pathcheckcreate(scratchgdb_var)

        final_csvtab = os.path.join(terra_resdir, "{}.csv".format(var))

        nclist = getfilelist(terra_dir, "TerraClimate_{0}_[0-9]{1}[.]nc$".format(var, "{4}"), gdbf=False)

        if var == 'PDSI':
            integer_multiplier = 100
            in_avg_func = 'mean'
        elif var == 'ppt':
            integer_multiplier = 1
            in_avg_func = 'sum'

        if arcpy.Exists(final_csvtab):
            print("{} already exists...".format(final_csvtab))

        else :
            cont_tablist = []
            for continent in flowdir_griddict:
                if continent != 'gr':
                    out_cont_tab = f'{os.path.splitext(final_csvtab)[0]}_{continent}.csv'
                    if not arcpy.Exists(out_cont_tab):
                        print(f'Processing {continent}...')
                        mask_ws_cont = os.path.join(scratchgdb_var, f'{os.path.split(stations_ws)[1]}_{continent}')
                        if not arcpy.Exists(mask_ws_cont):
                            Con(Raster(flowdir_griddict[continent])>0,
                                Raster(stations_ws)>0).save(mask_ws_cont)

                        # in_ncpath = nclist
                        # in_var = f"{var}_{continent}"
                        # in_template_extentlyr = flowdir_griddict[continent]
                        # in_template_resamplelyr = flowdir_griddict[continent]
                        # pxarea_grid = pxarea_grid
                        # uparea_grid = uparea_grid
                        # flowdir_grid = flowdir_griddict[continent]
                        # out_resdir = terra_resdir
                        # scratchgdb = scratchgdb_var
                        # integer_multiplier = integer_multiplier
                        # time_averaging_factor = 3
                        # time_averaging_function='mean'
                        # in_location_data = stations_formatted
                        # out_tabdir = scratchgdb_var
                        # id_field = 'grdc_no'
                        # fieldroot = var
                        # in_mask = mask_ws_cont
                        # save_raster = False
                        # save_tab = True
                        # in_crs = 4326
                        # lat_dim = 'lat'
                        # lon_dim = 'lon'
                        # time_dim = 'time'
                        # scratch_to_memory = True

                        out_tablist = flowacc_extract_nc(in_ncpath=nclist,
                                                         in_var=f"{var}_{continent}",
                                                         in_template_extentlyr=flowdir_griddict[continent],
                                                         in_template_resamplelyr=flowdir_griddict[continent],
                                                         pxarea_grid=pxarea_grid,
                                                         uparea_grid=uparea_grid,
                                                         flowdir_grid=flowdir_griddict[continent],
                                                         out_resdir=terra_resdir,
                                                         scratchgdb=scratchgdb_var,
                                                         integer_multiplier=integer_multiplier,
                                                         time_averaging_factor = 3,
                                                         time_averaging_function = in_avg_func,
                                                         in_location_data=stations_formatted,
                                                         out_tabdir = scratchgdb_var,
                                                         id_field='grdc_no',
                                                         fieldroot= var,
                                                         in_mask=mask_ws_cont,
                                                         save_raster=False,
                                                         save_tab=True,
                                                         scratch_to_memory = True)


                        out_tablist = getfilelist(scratchgdb_var,
                                                  "{0}_{1}_stats_[0-9]{2}$".format(var, continent, "{8}"),
                                                  gdbf=True)

                        #if all([arcpy.Exists(out_tab) for out_tab in out_tablist]):
                        print("Concatenating tables...")
                        out_tab = get_LRpred_pd(in_gdbtab=out_tablist[0],
                                                in_fieldroot=var,
                                                in_dtype=np.int32
                                                )

                        for in_tab in out_tablist[1:]:
                            temp_tab = get_LRpred_pd(in_gdbtab=in_tab,
                                                     in_fieldroot=var,
                                                     in_dtype=np.int32,
                                                     last_col=True)
                            if len(temp_tab) == len(out_tab):
                                out_tab = pd.concat([out_tab, temp_tab], axis=1)
                            else:
                                raise Exception("gdb table is not the same length as main table")

                        print("Writing out {}...".format(out_cont_tab))
                        out_tab.to_csv(out_cont_tab)

                    cont_tablist.append(out_cont_tab)

            pd.concat([pd.read_csv(tab) for tab in cont_tablist], axis=0).to_csv(final_csvtab)
