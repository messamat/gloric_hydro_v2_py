from setup_gloric import *

ghspop_dir = os.path.join(datdir, 'anthropo', 'ghspop')
ghsbuilt_dir = os.path.join(datdir, 'anthropo', 'ghsbuilt')

flowdir = os.path.join(datdir, 'hydroatlas', 'flow_dir_15s_global.gdb', 'flow_dir_15s')
up_area = os.path.join(datdir, 'hydroatlas', 'upstream_area_skm_15s.gdb', 'up_area_skm_15s')

ghspop_processgdb = os.path.join(resdir, 'ghspop_processing.gdb')
ghsbuilt_processgdb = os.path.join(resdir, 'ghsbuilt_processing.gdb')
pathcheckcreate(ghspop_processgdb)
pathcheckcreate(ghsbuilt_processgdb)

pop_raw_ts = {}
for lyr in getfilelist(ghspop_dir,
                       repattern='GHS_POP_E[0-9]{4}_GLOBE_R2023A_4326_3ss_V1_0.tif$',
                       gdbf=True):
    yr = int(
        re.findall('GHS_POP_E([0-9]{4})_GLOBE_R2023A_4326_3ss_V1_0.tif$',
                   os.path.split(lyr)[1])[0]
    )
    pop_raw_ts[yr] = lyr
    
built_raw_ts = {}
for lyr in getfilelist(ghsbuilt_dir,
                       repattern='GHS_BUILT_S_E[0-9]{4}_GLOBE_R2023A_4326_3ss_V1_0.tif$',
                       gdbf=True):
    yr = int(
        re.findall('GHS_BUILT_S_E([0-9]{4})_GLOBE_R2023A_4326_3ss_V1_0.tif$',
                   os.path.split(lyr)[1])[0]
    )
    built_raw_ts[yr] = lyr

#Determine aggregation factor
if 2000 in pop_raw_ts:
    orig_res = arcpy.Describe(pop_raw_ts[2000]).meanCellWidth
elif 2000 in built_raw_ts:
    orig_res = arcpy.Describe(built_raw_ts[2000]).meanCellWidth

cellsize_ratio = arcpy.Describe(flowdir).meanCellWidth / orig_res
print('Aggregating worldpop by cell size ratio of {0} would lead to a difference in resolution of {1} m'.format(
    math.floor(cellsize_ratio),
    111000 * (arcpy.Describe(flowdir).meanCellWidth - math.floor(cellsize_ratio) * orig_res)
))

arcpy.env.snapRaster = flowdir

#Aggregate pop tiles
pop_ag_dict = {}
for yr in pop_raw_ts:
    out_pop_ag = os.path.join(ghspop_processgdb,
                              "{0}_aggregated".format(os.path.splitext(os.path.split(pop_raw_ts[yr])[1])[0]))
    if not arcpy.Exists(out_pop_ag):
        print("Aggregating {0} by a factor of {1}".format(pop_raw_ts[yr], int(round(cellsize_ratio))))
        Aggregate(in_raster=pop_raw_ts[yr], cell_factor= int(round(cellsize_ratio)), aggregation_type='SUM'
                  ).save(out_pop_ag)
    pop_ag_dict[yr] = out_pop_ag

#Accumulate pop downstream
for yr in pop_ag_dict:
    out_pop_acc = os.path.join(ghspop_processgdb,
                               "{0}_acc".format(os.path.splitext(os.path.split(pop_raw_ts[yr])[1])[0]))
    # Multiply input grid by pixel area
    if not arcpy.Exists(out_pop_acc):
        print(f"Running flow accumulation for {pop_ag_dict[yr]}")
        outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=flowdir,
                                               in_weight_raster=Raster(pop_ag_dict[yr]),
                                               data_type="INTEGER")
        Plus(outFlowAccumulation, Raster(pop_ag_dict[yr])).save(out_pop_acc)

#Aggregate built lu tiles
built_ag_dict = {}
for yr in built_raw_ts:
    out_built_ag = os.path.join(ghsbuilt_processgdb,
                              "{0}_aggregated".format(os.path.splitext(os.path.split(built_raw_ts[yr])[1])[0]))
    print("Aggregating {0} by a factor of {1}".format(built_raw_ts[yr], int(round(cellsize_ratio))))
    if not arcpy.Exists(out_built_ag):
        Aggregate(in_raster=built_raw_ts[yr], cell_factor= int(round(cellsize_ratio)), aggregation_type='SUM'
                  ).save(out_built_ag)
    built_ag_dict[yr] = out_built_ag

#Accumulate built lu downstream
for yr in built_ag_dict:
    print(f"Running flow accumulation for {built_ag_dict[yr]}")
    out_built_acc = os.path.join(ghsbuilt_processgdb,
                               "{0}_acc".format(os.path.splitext(os.path.split(built_raw_ts[yr])[1])[0]))
    # Multiply input grid by pixel area
    if not arcpy.Exists(out_built_acc):
        scaled_valueras = Raster(built_ag_dict[yr])/1000
        outFlowAccumulation = FlowAccumulation(in_flow_direction_raster=flowdir,
                                               in_weight_raster=scaled_valueras,
                                               data_type="FLOAT")
        conv_factor = 100*1000*100/1000000 #100*re-scaling*conversion from ratio to %/conversion from km2 to m2
        Int(conv_factor*(Plus(outFlowAccumulation, scaled_valueras)/Raster(up_area))+0.5).save(out_built_acc)
        #The resulting raster is in 100 x % built extent - should be comprised between 0 and 1000