from setup_gloric import *

hyde_dir = os.path.join(datdir, 'anthropo', 'hyde')

up_area = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')
flowdir = os.path.join(datdir, 'hydroatlas', 'flow_dir_15s_global.gdb', 'flow_dir_15s')

hyde_processgdb = os.path.join(resdir, 'hyde_processing.gdb')
pathcheckcreate(hyde_processgdb)

hyde_raw_ts = {}
for lyr in getfilelist(hyde_dir,
                       repattern='cropland[0-9]{4]AD.asc$',
                       gdbf=True):
    yr = int(re.findall('cropland([0-9]{4])AD.asc$', os.path.split(lyr)[1])[0])
    hyde_raw_ts[yr] = lyr

# Set environment
arcpy.env.extent = arcpy.env.snapRaster = flowdir
# Resample
for yr in hyde_raw_ts:
    start = time.time()
    out_rsmpbi = os.path.join(hyde_processgdb,
                              f"{os.path.split(hyde_raw_ts[yr])[1]}_rsmpbi")

    if not arcpy.Exists(out_rsmpbi):
        print(f"Resampling {hyde_raw_ts[yr]}")
        arcpy.management.Resample(in_raster=hyde_raw_ts[yr],
                                  out_raster=out_rsmpbi,
                                  cell_size=arcpy.Describe(flowdir).MeanCellWidth,
                                  resampling_type='BILINEAR')

    out_flowacc = os.path.join(hyde_processgdb,
                               f"{os.path.split(hyde_raw_ts[yr])[1]}_acc")
    if not arcpy.Exists(out_flowacc):
        print(f"Flow accumulating {out_rsmpbi}")
        outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=flowdir,
                                               in_weight_raster=Int(100*Raster(out_rsmpbi)),
                                               data_type="LONG")
        Plus(outFlowAccumulation, Int(100*Raster(out_rsmpbi))).save(out_flowacc)

