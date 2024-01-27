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

terra_resdir = os.path.join(resdir, 'terra')
pathcheckcreate(terra_resdir)

stations_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
stations_formatted = getfilelist(stations_gdb, 'grdc_p_o[0-9]*y_cleanjoin$', gdbf=True)[0]

# Create gdb for WaterGAP time-series predictors
pred_tabgdb = os.path.join(terra_resdir, 'terra_tabs.gdb')
pathcheckcreate(path=pred_tabgdb , verbose=True)

stations_ws = f"{stations_formatted}_ws"

#-------------------------------------- Define functions ---------------------------------------------------------------
def flowacc_extract_nc(in_ncpath, in_var, in_template_extentlyr, in_template_resamplelyr,
                       pxarea_grid, uparea_grid, flowdir_grid, out_resdir, scratchgdb, integer_multiplier,
                       in_location_data, id_field, out_tabdir, fieldroot,
                       in_crs=4326, lat_dim='lat', lon_dim='lon', in_mask=None, save_raster=False, save_tab=True):

    out_croppedintnc = os.path.join(out_resdir, f"{in_var}_croppedint.nc")
    LRpred_resgdb = os.path.join(out_resdir, f"{in_var}.gdb")
    pathcheckcreate(LRpred_resgdb)

    if isinstance(in_ncpath, list):
        pred_nc = xr.open_mfdataset(in_ncpath)
    elif isinstance(in_ncpath, str):
        pred_nc = xr.open_dataset(in_ncpath)

    timesteps_list = [pd.to_datetime(t).strftime('%Y%d%m') for t in pred_nc['time'].values]
    out_tablist = [os.path.join(out_tabdir, f"{in_var}_{ts}") for ts in timesteps_list]

    cellsize_ratio = pred_nc.attrs['geospatial_lon_resolution'] / arcpy.Describe(in_template_resamplelyr).meanCellWidth

    #the resolution residual left from aggregating or resampling
    aggregate_residual = (pred_nc.attrs['geospatial_lon_resolution']
                      - math.floor(cellsize_ratio) * arcpy.Describe(in_template_resamplelyr).meanCellWidth)
    if not all([int(arcpy.GetRasterProperties_management(in_template_resamplelyr, "ROWCOUNT").getOutput(0))
                *aggregate_residual<(arcpy.Describe(in_template_resamplelyr).meanCellHeight/2),
            int(arcpy.GetRasterProperties_management(in_template_resamplelyr, "COLUMNCOUNT").getOutput(0))
            * aggregate_residual  < (arcpy.Describe(in_template_resamplelyr).meanCellWidth / 2)]):
        raise ValueError('Resampling would cause a shift in the raster because '
                         'the resolution of the netcdf and template layer are not multiples')

    if not all([arcpy.Exists(out_tab) for out_tab in out_tablist]):
        #Crop netcdf to template extent and get minimum value within that extent
        templateext = arcpy.Describe(in_template_extentlyr).extent
        cropdict = {lon_dim: slice(templateext.XMin, templateext.XMax),
                    lat_dim: slice(templateext.YMax,
                                   templateext.YMin)}  # Lat is from north to south so need to reverse slice order
        pred_nc_cropped = pred_nc.loc[cropdict]

        #Get minimum value
        min_val = int(pred_nc_cropped.PDSI.min().compute() * integer_multiplier)

        # Crop xarray and convert it to integer, making sure it only has positive values for flow accumulation
        out_croppedint = os.path.join(scratchgdb, f"{in_var}_croppedint")
        if not arcpy.Exists(out_croppedint):
            print(f"Producing {out_croppedintnc}")
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
                                           band_dimension=list(pred_nc.dims)[2],
                                           value_selection_method='BY_INDEX',
                                           cell_registration='CENTER')
            output_ras = Raster('tmpras_check')
            arcpy.DefineProjection_management(output_ras, coor_system=in_crs)

            #Aggregate mask layer to subset output raster
            arcpy.env.snapRaster = 'tmpras_check'
            mask_agg = Aggregate(in_raster=in_mask,
                                 cell_factor=round(cellsize_ratio),
                                 aggregation_type='MAXIMUM')

            #Shift raster to positive values for running flow accumulation
            if min_val < 0:
                shiftval = -min_val
            else:
                shiftval = 0

            arcpy.env.mask = mask_agg
            Con(output_ras >= min_val, output_ras+shiftval).save(out_croppedint)

            #Clean up
            arcpy.Delete_management(out_croppedintnc)
            arcpy.Delete_management(mask_agg)
            arcpy.Delete_management('tmpras_check')
            arcpy.ClearEnvironment("mask")
            arcpy.ClearEnvironment("snapRaster")

        # Set environment
        arcpy.env.extent = arcpy.env.snapRaster = in_template_resamplelyr
        arcpy.env.parallelProcessingFactor = "50%"

        # Resample
        out_rsmpnear = os.path.join(pred_tabgdb, f"{in_var}_rsmpnear")
        if not arcpy.Exists(out_rsmpnear):
            print(f"Resampling {out_croppedintnc}")
            arcpy.management.Resample(in_raster=out_croppedint,
                                      out_raster=out_rsmpnear,
                                      cell_size=arcpy.Describe(in_template_resamplelyr).MeanCellWidth,
                                      resampling_type='NEAREST') #Go for nearestneighbor for speed

        arcpy.env.mask = out_rsmpnear
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
                outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=out_rsmpnear,
                                                       in_weight_raster=Raster(valueXarea),
                                                       data_type="FLOAT")
                outFlowAccumulation_2 = Plus(outFlowAccumulation, valueXarea)
                UplandGrid = Int((Divide(outFlowAccumulation_2, Raster(uparea_grid))) + 0.5)

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

    else:
        print("All tables already exists for {}".format(in_var))

    return(out_tablist)

def get_LRpred_pd(in_gdbtab, in_fieldroot, in_dtype, last_col=False):
                print(in_gdbtab)

                var_colname = "{0}_{1}".format(
                    in_fieldroot,
                    re.findall('[0-9]{1,3}$', os.path.split(in_gdbtab)[1])[0])

                if last_col:
                    step_pd = pd.DataFrame(data=arcpy.da.SearchCursor(in_gdbtab,
                                                                      [f.name for f in arcpy.ListFields(in_gdbtab)][-1]),
                                           dtype=in_dtype)
                    step_pd.columns = [var_colname]
                else:
                    rcols = ['DRYVER_RIVID', var_colname]
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
    if var in ['PDSI', 'ppt']:
        scratchgdb_var = os.path.join(terra_resdir, 'scratch_{}.gdb'.format(var))
        pathcheckcreate(scratchgdb_var)

        final_csvtab = os.path.join(terra_resdir, "{}.csv".format(var))

        nclist = getfilelist(terra_dir, "TerraClimate_{0}_[0-9]{1}[.]nc$".format(var, "{4}"), gdbf=False)

        if var == 'PDSI':
            integer_multiplier = 100
        else:
            integer_multiplier = 1

        if arcpy.Exists(final_csvtab):
            print("{} already exists...".format(final_csvtab))

        else :
            for continent in flowdir_griddict:
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
                # in_location_data = stations_formatted
                # out_tabdir = scratchgdb_var
                # id_field = 'grdc_no'
                # fieldroot = var
                # in_mask = mask_ws_cont
                # save_raster = False
                # save_tab = True
                # lat_dim='lat'
                # lon_dim='lon'
                # in_crs = 4326

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
                                                 in_location_data=stations_formatted,
                                                 out_tabdir = scratchgdb_var,
                                                 id_field='grdc_no',
                                                 fieldroot= var,
                                                 in_mask=mask_ws_cont,
                                                 save_raster=False,
                                                 save_tab=True)

            pred_nc = xr.open_dataset(LRpred_vardict[var][0])
            new_variable_name = re.sub('\\s', '_', list(pred_nc.variables)[-1])
            out_tablist = [os.path.join(LRpred_tabgdb, f'{in_var_formatted}_{i + 1}') for i in
                           range(pred_nc.coords.dims['Time (Month)'])]

            if all([arcpy.Exists(out_tab) for out_tab in out_tablist]):
                print("Concatenating tables...")
                out_tab = get_LRpred_pd(in_gdbtab=out_tablist[0],
                                        in_fieldroot=var,
                                        in_dtype=np.int32)

                invar_types = {'qrdifoverql': np.int32,
                               'wetdays': np.int16}

                for in_tab in out_tablist[1:]:
                    temp_tab = get_LRpred_pd(in_gdbtab=in_tab,
                                             in_fieldroot=var,
                                             in_dtype=invar_types[fieldroot],
                                             last_col=True)
                    if len(temp_tab) == len(out_tab):
                        out_tab = pd.concat([out_tab, temp_tab], axis=1)
                    else:
                        raise Exception("gdb table is not the same length as main table")

                print("Writing out {}...".format(final_csvtab))
                out_tab.to_csv(final_csvtab)


########################
# for ts in pred_vardict :
#     if re.findall('PDSI', ts):
#         pred_vardict[ts].append(pow(10,2))
#     else:
#         pred_vardict[ts].append(1)
# for ts in pred_vardict:
#     pred_vardict[ts].append(re.sub('(TerraClimate_)|(_[0-9]{4})', '', ts))
#     pred_vardict[ts].append(int(re.findall('.*([0-9]{4})', ts)[0]))




#
#
#
#
#         # arcpy.Delete_management(out_croppedint)
#         # arcpy.Delete_management(out_rsmpbi)