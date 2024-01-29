from setup_gloric import *

aei_dir = os.path.join(datdir, 'anthropo', 'aei')

up_area = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')
flowdir = os.path.join(datdir, 'hydroatlas', 'flow_dir_15s_global.gdb', 'flow_dir_15s')

aei_processgdb = os.path.join(resdir, 'aei_processing.gdb')
pathcheckcreate(aei_processgdb)

aei_raw_ts = {}
for lyr in getfilelist(aei_dir,
                       repattern='^G_AEI_[0-9]{4}[.]ASC$',
                       gdbf=False):
    yr = int(re.findall('G_AEI_([0-9]{4})[.]ASC$', os.path.split(lyr)[1])[0])
    aei_raw_ts[yr] = lyr

# Set environment
arcpy.env.extent = arcpy.env.snapRaster = flowdir
# Resample
for yr in aei_raw_ts:
    out_flowacc = os.path.join(aei_processgdb, f"{rootname}_acc")
    if not arcpy.Exists(out_flowacc):
        start = time.time()
        rootname = os.path.splitext(os.path.split(aei_raw_ts[yr])[1])[0]
        out_rsmpbi = os.path.join(aei_processgdb,
                                  f"{rootname}_rsmpbi")

        if not arcpy.Exists(out_rsmpbi):
            print(f"Resampling {aei_raw_ts[yr]}")
            arcpy.management.Resample(in_raster=aei_raw_ts[yr],
                                      out_raster=out_rsmpbi,
                                      cell_size=arcpy.Describe(flowdir).MeanCellWidth,
                                      resampling_type='BILINEAR')

        print(f"Flow accumulating {out_rsmpbi}")
        scaled_valueras = Raster(out_rsmpbi)/(400*100) #Conversion from 5 arc-min to 15 arc-sec resolution and from ha to km2
        outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=flowdir,
                                               in_weight_raster=scaled_valueras,
                                               data_type="FLOAT")
        conv_factor = 100*100 #100*conversion from ratio to %
        Int(conv_factor*(Plus(outFlowAccumulation, scaled_valueras)/Raster(up_area))+0.5).save(out_flowacc)

