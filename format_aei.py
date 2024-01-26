from setup_gloric import *

aei_dir = os.path.join(datdir, 'anthropo', 'aei')

up_area = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')
flowdir = os.path.join(datdir, 'hydroatlas', 'flow_dir_15s_global.gdb', 'flow_dir_15s')

aei_processgdb = os.path.join(resdir, 'aei_processing.gdb')
pathcheckcreate(aei_processgdb)

aei_raw_ts = {}
for lyr in getfilelist(aei_dir,
                       repattern='G_AEI_[0-9]{4].ASC$',
                       gdbf=True):
    yr = int(re.findall('G_AEI_([0-9]{4]).ASC$', os.path.split(lyr)[1])[0])
    aei_raw_ts[yr] = lyr

# Set environment
arcpy.env.extent = arcpy.env.snapRaster = flowdir
# Resample
for yr in aei_raw_ts:
    start = time.time()
    out_rsmpbi = os.path.join(aei_processgdb,
                              f"{os.path.split(aei_raw_ts[yr])[1]}_rsmpbi")

    if not arcpy.Exists(out_rsmpbi):
        print(f"Resampling {aei_raw_ts[yr]}")
        arcpy.management.Resample(in_raster=aei_raw_ts[yr],
                                  out_raster=out_rsmpbi,
                                  cell_size=arcpy.Describe(flowdir).MeanCellWidth,
                                  resampling_type='BILINEAR')

    out_flowacc = os.path.join(aei_processgdb,
                               f"{os.path.split(aei_raw_ts[yr])[1]}_acc")
    if not arcpy.Exists(out_flowacc):
        print(f"Flow accumulating {out_rsmpbi}")
        outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=flowdir,
                                               in_weight_raster=Int(100*Raster(out_rsmpbi)),
                                               data_type="LONG")
        Plus(outFlowAccumulation, Int(100*Raster(out_rsmpbi))).save(out_flowacc)