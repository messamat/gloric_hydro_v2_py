from setup_gloric import *

#Formatted gauges
stations_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
grdcp_cleanjoin = os.path.join(stations_gdb, "grdc_p_o{}y_cleanjoin".format(min_record_length))

#Network directories
net_gdb = os.path.join(resdir, 'intergauge_network_dist.gdb')
pathcheckcreate(net_gdb)

hydroriv_dir = os.path.join(datdir, 'hydroatlas', 'hydrorivers_cont')

#Subset network
cont = 'au'
net_raw = os.path.join(hydroriv_dir, f'HydroRIVERS_v10_{cont}.gdb', f'HydroRIVERS_v10_{cont}')

#Create network
net_fd = os.path.join(net_gdb, f'{cont}_fd')
net_format = os.path.join(net_fd, f'{cont}_net')
if not arcpy.Exists(net_fd):
    arcpy.CreateFeatureDataset_management(out_dataset_path=os.path.split(net_fd)[0],
                                          out_name=os.path.split(net_fd)[1],
                                          spatial_reference=4326
                                          )

arcpy.CopyFeatures_management(net_raw, os.path.join(net_fd, os.path.split(net_raw)[1]))
if not arcpy.Exists(net_format):
    arcpy.na.CreateNetworkDataset(feature_dataset=os.path.split(net_format)[0],
                                  out_name=os.path.split(net_format)[1],
                                  source_feature_class_names=os.path.split(net_raw)[1],
                                  elevation_model='NO_ELEVATION')
    arcpy.na.BuildNetwork(net_format)

#MakeNetworkDatasetLayer
net_lyr = arcpy.nax.MakeNetworkDatasetLayer(net_format, os.path.split(net_format)[1])

#Create TravelMode
travel_mode_net = arcpy.nax.TravelMode
travel_mode_net.distanceAttributeName = 'Meters'
travel_mode_net.impedance = 'Meters'
travel_mode_net.name = 'hydro_travel'
travel_mode_net.useHierarchy = 'NO_HIERARCHY'

#code from: https://pro.arcgis.com/en/pro-app/latest/tool-reference/network-analyst/make-od-cost-matrix-analysis-layer.htm
#Create a new OD Cost matrix layer. We want to find all gauges within 100 km of each other
od_obj = arcpy.na.MakeODCostMatrixAnalysisLayer(network_data_source=net_format,
                                               layer_name='ODlyr',
                                               cutoff=100000,
                                               number_of_destinations_to_find=4,
                                               line_shape='NO_LINES',
                                               ignore_invalid_locations='SKIP')

#Get the layer object from the result object. The OD cost matrix layer can
#now be referenced using the layer object.
layer_object = od_obj.getOutput(0)

# Get the names of all the sublayers within the OD cost matrix layer.
sublayer_names = arcpy.na.GetNAClassNames(layer_object)
# Stores the layer names that we will use later
origins_layer_name = sublayer_names["Origins"]
destinations_layer_name = sublayer_names["Destinations"]

#Load the warehouse locations as origins using a default field mappings and
    #a search tolerance of 5000 Meters.
arcpy.na.AddLocations(layer_object, origins_layer_name,
                      grdcp_cleanjoin,
                      search_tolerance='5000 meters')

#Load the store locations as destinations and map the NOM field from stores
    #features as Name property using field mappings
field_mappings = arcpy.na.NAClassFieldMappings(layer_object,
                                               destinations_layer_name)
field_mappings["Name"].mappedFieldName = "grdc_no"
arcpy.na.AddLocations(layer_object, destinations_layer_name,
                      grdcp_cleanjoin,
                      field_mappings,
                      search_tolerance='5000 meters')

#Solve the OD cost matrix layer
arcpy.na.Solve(layer_object)

#Save the solved OD cost matrix layer as a layer file on disk
output_layer_file = os.path.join(resdir, f'test_od_matrix_{cont}.lyrx')
layer_object.saveACopy(output_layer_file)

"""
For best performance when using a network dataset, use the name of a network dataset layer when initializing your analysis. 
If you use a catalog path, the network dataset is opened each time the analysis is initialized. Opening a network dataset
 is time-consuming, as datasets contain advanced data structures and tables that are read and cached. A network dataset
  layer opens the dataset one time and performs better when the same layer is used."""




#create function for a given network

#subset HydroRIVERS by continent

#run for each continent with max distance


#-----------------------#get status: upstream, downstream or unconnected -----------------------------------------------



#----------------------- determine whether a dam in between ------------------------------------------------------------
#