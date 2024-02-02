import arcpy.tn
from setup_gloric import *

#Formatted gauges
stations_gdb = os.path.join(resdir, 'stations_preprocess.gdb')
grdcp_cleanjoin = os.path.join(stations_gdb, "grdc_p_o{}y_cleanjoin".format(min_record_length))

#Network directories
net_gdb = os.path.join(resdir, 'intergauge_network_dist.gdb')
pathcheckcreate(net_gdb)

hydroriv_dir = os.path.join(datdir, 'hydroatlas', 'hydrorivers_cont')

global_netdist_tab = os.path.join(resdir, f"{os.path.split(grdcp_cleanjoin)[1]}_netdist_tab.csv")
global_geodist_tab = os.path.join(resdir, f"{os.path.split(grdcp_cleanjoin)[1]}_geodist_tab.csv")

#---- test
# cont = 'af'
# net_raw = os.path.join(hydroriv_dir, f'HydroRIVERS_v10_{cont}.gdb', f'HydroRIVERS_v10_{cont}')
# in_net = net_raw
# in_points = grdcp_cleanjoin
# in_template = os.path.join(os.path.dirname(os.path.abspath(getsourcefile(lambda: 0))), 'data', 'arcpy_rivnetwork_dataset_template.xml')
# out_gdb = net_gdb
# in_travel_mode = ['upstream_travel', 'downstream_travel']
# max_netdist = 100000
# snap_tolerance = 5000
# max_destination = 10
# crs = 4326
# verbose = True
# overwrite = False
# in_destination_points = None

def overwrite_xml_substr(in_xml, out_xml, old_text, new_text):
    with open(in_xml, 'r',encoding='utf8') as f:
        tree = f.read()
    new_tree = re.sub(old_text,new_text, tree)
    with open(out_xml, 'w', encoding='utf8') as f:
        f.write(new_tree)

def get_netdist_matrix(in_net, in_points, in_template, out_gdb, max_netdist, snap_tolerance, max_destination,
                       in_destination_points = None, in_travel_mode=['upstream_travel', 'downstream_travel'],
                       crs=4326, verbose=True, overwrite=False):

    in_net_basename = os.path.split(in_net)[1]
    output_tab = os.path.join(out_gdb, f'odmatrix_lines_{in_net_basename}')

    if arcpy.Exists(output_tab):
        print(f'{output_tab} already exists. skipping.')
    else:
        # Create network
        net_fd = os.path.join(out_gdb, f'{in_net_basename}_fd')
        net_in_fd = os.path.join(net_fd, in_net_basename)
        net_format = os.path.join(net_fd, f'{in_net_basename}_net')
        out_xml = os.path.join(os.path.split(in_template)[0], 'temp_xml.xml')

        if not arcpy.Exists(net_fd):
            if verbose:
                print('Create feature dataset')
            arcpy.CreateFeatureDataset_management(out_dataset_path=os.path.split(net_fd)[0],
                                                  out_name=os.path.split(net_fd)[1],
                                                  spatial_reference=crs
                                                  )
            arcpy.CopyFeatures_management(in_net, net_in_fd)

        if not arcpy.Exists(net_format):
            if verbose:
                print('Createt network dataset')
            #Edit template xml
            # Cannot instantiate a travel mode from scratch in python - so need to use a network dataset template
            if in_net_basename != 'HydroRIVERS_v10_au':
                overwrite_xml_substr(in_xml=in_template,
                                     out_xml=out_xml,
                                     old_text='HydroRIVERS_v10_au',
                                     new_text=in_net_basename)
            else:
                out_xml=in_template

            arcpy.nax.CreateNetworkDatasetFromTemplate(network_dataset_template=out_xml,
                                                       output_feature_dataset=net_fd)
            arcpy.nax.BuildNetwork(net_format)

        # code from: https://pro.arcgis.com/en/pro-app/latest/tool-reference/network-analyst/make-od-cost-matrix-analysis-layer.htm
        # Create a new OD Cost matrix layer. We want to find all gauges within 100 km of each other
        tab_list = []

        for travel_mode in in_travel_mode:
            arcpy.env.workspace = out_gdb

            if verbose:
                print(f'Compute {travel_mode} distances')

            output_tab_travelmode = os.path.join(out_gdb, f'odmatrix_lines_{in_net_basename}_{travel_mode}')
            if arcpy.Exists(output_tab_travelmode) or overwrite:
                print(f'{output_tab_travelmode} already exists')
            else:
                od_obj = arcpy.na.MakeODCostMatrixAnalysisLayer(network_data_source=net_format,
                                                                layer_name='ODlyr',
                                                                travel_mode=travel_mode,
                                                                cutoff=max_netdist,
                                                                number_of_destinations_to_find=max_destination,
                                                                line_shape='NO_LINES',
                                                                ignore_invalid_locations='SKIP')

                # Get the layer object from the result object. The OD cost matrix layer can
                # now be referenced using the layer object.
                layer_object = od_obj.getOutput(0)

                # Get the names of all the sublayers within the OD cost matrix layer.
                sublayer_names = arcpy.na.GetNAClassNames(layer_object)
                # Stores the layer names that we will use later
                orig_lyrn = sublayer_names["Origins"]
                desti_lyrn = sublayer_names["Destinations"]

                # Subset points to be within the network bounding box
                arcpy.MakeFeatureLayer_management(in_points, out_layer='pts_lyr')
                netext = arcpy.Describe(in_net).extent
                netbbox = arcpy.Polygon(
                    arcpy.Array([netext.lowerLeft, netext.lowerRight, netext.upperLeft, netext.upperRight,
                                 netext.lowerRight,netext.lowerLeft, netext.upperLeft]),
                    arcpy.Describe(in_net).spatialReference)
                temp_gauges = arcpy.SelectLayerByLocation_management(in_layer='pts_lyr',
                                                                     overlap_type='WITHIN',
                                                                     select_features=netbbox)

                # Load the points as origins using a default field mappings and a search tolerance of 5000 Meters.
                if verbose:
                    print(f'---- Add origin and destination points to network dataset')

                field_mappings = arcpy.na.NAClassFieldMappings(layer_object,
                                                               desti_lyrn)
                field_mappings["Name"].mappedFieldName = "grdc_no"
                arcpy.na.AddLocations(layer_object, orig_lyrn,
                                      temp_gauges,
                                      field_mappings,
                                      search_tolerance='5000 meters')

                # Load the points as destinations and map the NOM field from stores features as Name property using field mappings
                if in_destination_points is None:
                    arcpy.na.AddLocations(layer_object, desti_lyrn,
                                          temp_gauges,
                                          field_mappings,
                                          search_tolerance=snap_tolerance)
                else:
                    arcpy.na.AddLocations(layer_object, desti_lyrn,
                                          in_destination_points,
                                          search_tolerance=snap_tolerance)

                # Solve the OD cost matrix layer
                if verbose:
                    print(f'---- Solve origin-destination cost matrix')
                arcpy.na.Solve(layer_object)

                # Save the solved OD cost matrix layer as a layer file on disk
                if verbose:
                    print(f'---- Format tables')
                output_layer_file = os.path.join(resdir, f'odmatrix_lines_{in_net_basename}_{travel_mode}.lyrx')
                {lyr.name: lyr for lyr in layer_object.listLayers()}['Lines'].saveACopy(output_layer_file)
                arcpy.CopyRows_management(output_layer_file, output_tab_travelmode)

                arcpy.AddField_management(output_tab_travelmode, 'travel_mode', 'TEXT')
                with arcpy.da.UpdateCursor(output_tab_travelmode, ['OriginID', 'DestinationID', 'travel_mode']) as cursor:
                    for row in cursor:
                        if row[0]==row[1]:
                            cursor.deleteRow()
                        else:
                            row[2] = travel_mode
                            cursor.updateRow(row)

                arcpy.ClearEnvironment('workspace')
                del od_obj
                arcpy.Delete_management(layer_object)
                arcpy.Delete_management(output_layer_file)

            tab_list.append(output_tab_travelmode)

        #Merge tables and delete them
        arcpy.Merge_management(tab_list, output_tab)

    return (output_tab)

#------------------------------------ Get euclidean distance among gauges --------------------------------------------
if not arcpy.Exists(global_geodist_tab):
    temp_tab = os.path.join(stations_gdb, 'stations_dist')
    arcpy.analysis.GenerateNearTable(in_features=grdcp_cleanjoin,
                                     near_features=grdcp_cleanjoin,
                                     out_table=temp_tab,
                                     closest='ALL',
                                     search_radius='100 Kilometers',
                                     method='GEODESIC',
                                     distance_unit='Kilometers')
    id_dict = {row[0]:row[1] for row in arcpy.da.SearchCursor(grdcp_cleanjoin, ['OID@', 'grdc_no'])}
    arcpy.AddField_management(temp_tab, 'grdc_no_origin')
    arcpy.AddField_management(temp_tab, 'grdc_no_destination')

    with arcpy.da.UpdateCursor(temp_tab, ['IN_FID', 'grdc_no_origin', 'NEAR_FID', 'grdc_no_destination']) as cursor:
        for row in cursor:
            if row[0] in id_dict:
                row[1] = id_dict[row[0]]
            if row[2] in id_dict:
                row[3] = id_dict[row[2]]
            cursor.updateRow(row)

    arcpy.CopyRows_management(temp_tab, global_geodist_tab)
    arcpy.Delete_management(temp_tab)

#------------------------------------ Get network distance among gauges for each continent -----------------------------
#Subset network
if not arcpy.Exists(global_netdist_tab):
    out_tablist = {}
    for cont in ['af','ar', 'au', 'as', 'eu', 'na', 'sa', 'si']:
        print(f'Processing {cont}:')
        net_raw = os.path.join(hydroriv_dir, f'HydroRIVERS_v10_{cont}.gdb', f'HydroRIVERS_v10_{cont}')
        out_tablist[cont] = get_netdist_matrix(
            in_net=net_raw,
            in_points=grdcp_cleanjoin,
            in_template=os.path.join(os.path.dirname(os.path.abspath(getsourcefile(lambda:0))),
                                     'data', 'arcpy_rivnetwork_dataset_template.xml'),
            out_gdb=net_gdb,
            in_travel_mode=['upstream_travel', 'downstream_travel'],
            max_netdist=100000,
            snap_tolerance=5000,
            max_destination=10,
            crs=4326,
            verbose=True,
            overwrite=False,
            in_destination_points=None)

    arcpy.Merge_management(list(out_tablist.values()),
                           output=global_netdist_tab,
                           add_source='ADD_SOURCE_INFO')
    arcpy.CopyRows_management(os.path.splitext(global_netdist_tab)[0], global_netdist_tab)
    arcpy.Delete_management(global_netdist_tab)