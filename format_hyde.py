import arcpy
#https://public.yoda.uu.nl/geo/UU01/MO2FF3.html

from setup_gloric import *

hyde_dir = os.path.join(datdir, 'anthropo', 'hyde')

pxarea_grid = os.path.join(datdir, 'hydroatlas', 'pixel_area_skm_15s.gdb', 'px_area_skm_15s')
up_area = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')
flowdir = os.path.join(datdir, 'hydroatlas', 'flow_dir_15s_global.gdb', 'flow_dir_15s')

hyde_processgdb = os.path.join(resdir, 'hyde_processing.gdb')
pathcheckcreate(hyde_processgdb)

hyde_raw_ts = {}
for lyr in getfilelist(hyde_dir,
                       repattern='^cropland[0-9]{4}AD.asc$',
                       gdbf=True):
    yr = int(re.findall('^cropland([0-9]{4})AD.asc$', os.path.split(lyr)[1])[0])
    hyde_raw_ts[yr] = lyr


# Set environment
arcpy.env.extent = arcpy.env.snapRaster = flowdir
templ_res = arcpy.Describe(flowdir).MeanCellWidth

# Resample
for yr in hyde_raw_ts:
    start = time.time()
    rootname = os.path.splitext(os.path.split(hyde_raw_ts[yr])[1])[0]
    out_rsmpbi = os.path.join(hyde_processgdb,
                              f"{rootname}_rsmpbi")
    cellsize_ratio = arcpy.Describe(hyde_raw_ts[yr]).meanCellWidth/templ_res

    out_flowacc = os.path.join(hyde_processgdb,  f"{rootname}_acc")
    if not arcpy.Exists(out_flowacc):
        if not arcpy.Exists(out_rsmpbi):
            print(f"Resampling {hyde_raw_ts[yr]}")
            scaled_coarseras = Raster(hyde_raw_ts[yr])/(round(cellsize_ratio)**2) #Hydr is in km2, so divide by the number of cells that will be in each
            arcpy.management.Resample(in_raster=scaled_coarseras,
                                      out_raster=out_rsmpbi,
                                      cell_size=arcpy.Describe(flowdir).MeanCellWidth,
                                      resampling_type='BILINEAR')

        print(f"Flow accumulating {out_rsmpbi}")
        outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=flowdir,
                                               in_weight_raster=out_rsmpbi,
                                               data_type="FLOAT")
        outFlowAccumulation_2 = Plus(outFlowAccumulation, out_rsmpbi)
        UplandGrid = Int(100*(Divide(outFlowAccumulation_2, Raster(up_area))) + 0.5)
        UplandGrid.save(out_flowacc)
        
