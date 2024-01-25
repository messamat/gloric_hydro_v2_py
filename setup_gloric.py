import arcpy
from arcpy.sa import *
from collections import defaultdict
from datetime import date
from inspect import getsourcefile
import math
import numpy as np
import os
import pandas as pd
from pathlib import Path
import re
import requests
import traceback
import sys
import xarray as xr
import zipfile

from bs4 import BeautifulSoup
import ftplib
from urllib.parse import *

arcpy.CheckOutExtension('Spatial')
arcpy.env.overwriteOutput = True
arcpy.env.qualifiedFieldNames = False

pyversion = sys.version_info
if (pyversion.major == 3) and (pyversion.minor >= 7):
    sys.stdout.reconfigure(encoding='utf-8')

#Get current root directory
def get_root_fromsrcdir():
    return(os.path.dirname(os.path.abspath(
        getsourcefile(lambda:0)))).split('\\src')[0]

#Folder structure
rootdir = get_root_fromsrcdir()
datdir = os.path.join(rootdir, 'data')
resdir = os.path.join(rootdir, 'results')
metadatdir = os.path.join(rootdir, 'data', 'metadata')
if not os.path.exists(metadatdir):
    os.mkdir(metadatdir)

#------------------------------------------------ Utility functions ----------------------------------------------------
def getwkspfiles(dir, repattern=None):
    arcpy.env.workspace = dir
    filenames_list = (arcpy.ListDatasets() or []) +\
                     (arcpy.ListTables() or []) +\
                     (arcpy.ListFeatureClasses() or []) # Either LisDatsets or ListTables may return None so need to create empty list alternative
    if not repattern == None:
        filenames_list = [filen for filen in filenames_list if re.search(repattern, filen)]

    return ([os.path.join(dir, f) for f in filenames_list])
    arcpy.ClearEnvironment('workspace')

def getfilelist(dir, repattern=None, nongdbf=True, gdbf=False, fullpath=False):
    """Function to iteratively go through all subdirectories inside 'dir' path
    and retrieve path for each file that matches "repattern"
    gdbf and nongdbf allows the user to choose whether to consider ArcGIS workspaces (GDBs) or not or exclusively"""

    if isinstance(dir, Path):
        dir = str(dir)

    try:
        if arcpy.Describe(dir).dataType == 'Workspace':
            if gdbf == True:
                print('{} is ArcGIS workspace...'.format(dir))
                filenames_list = getwkspfiles(dir, repattern)
            else:
                raise ValueError(
                    "A gdb workspace was given for dir but gdbf=False... either change dir or set gdbf to True")
        else:
            filenames_list = []

            if gdbf == True:
                for (dirpath, dirnames, filenames) in os.walk(dir):
                    for in_dir in dirnames:
                        fpath = os.path.join(dirpath, in_dir)
                        if arcpy.Describe(fpath).dataType == 'Workspace':
                            print('{} is ArcGIS workspace...'.format(fpath))
                            filenames_list.extend(getwkspfiles(dir=fpath, repattern=repattern))
            if nongdbf == True:
                for (dirpath, dirnames, filenames) in os.walk(dir):
                    for file in filenames:
                        if repattern is None:
                            filenames_list.append(os.path.join(dirpath, file))
                        else:
                            if re.search(repattern, file):
                                filenames_list.append(os.path.join(dirpath, file))
        return (filenames_list)

    # Return geoprocessing specific errors
    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
    # Return any other type of error
    except:
        # By default any other errors will be caught here
        e = sys.exc_info()[1]
        print(e.args[0])

def pathcheckcreate(path, verbose=True):
    """"Function that takes a path as input and:
      1. Checks which directories and .gdb exist in the path
      2. Creates the ones that don't exist"""

    dirtocreate = []
    # Loop upstream through path to check which directories exist, adding those that don't exist to dirtocreate list
    while not os.path.exists(os.path.join(path)):
        dirtocreate.append(os.path.split(path)[1])
        path = os.path.split(path)[0]

    dirtocreate.reverse()

    # After reversing list, iterate through directories to create starting with the most upstream one
    for dir in dirtocreate:
        # If gdb doesn't exist yet, use arcpy method to create it and then stop the loop to prevent from trying to create anything inside it
        if os.path.splitext(dir)[1] == '.gdb':
            if verbose:
                print('Create {}...'.format(dir))
            arcpy.management.CreateFileGDB(out_folder_path=path,
                                           out_name=dir)
            break

        # Otherwise, if it is a directory name (no extension), make a new directory
        elif os.path.splitext(dir)[1] == '':
            if verbose:
                print('Create {}...'.format(dir))
            path = os.path.join(path, dir)
            os.mkdir(path)

#Compare whether two layers' spatial references are the same
def compsr(lyr1, lyr2):
    return(arcpy.Describe(lyr1).SpatialReference.exportToString() ==
           arcpy.Describe(lyr2).SpatialReference.exportToString())


def unzip(infile):
    # Unzip folder
    if zipfile.is_zipfile(infile):
        print('Unzipping {}...'.format(os.path.split(infile)[1]))
        outdir = Path(os.path.splitext(infile)[0])
        if not outdir.exists():
            outdir.mkdir()

        with zipfile.ZipFile(infile) as zipf:
            zipfilelist = [info.filename for info in zipf.infolist()]
            listcheck = [f for f in zipfilelist if Path(outdir, f).exists()]
            if len(listcheck) > 0:
                print('Overwriting {}...'.format(', '.join(listcheck)))
            for name in zipf.namelist():
                zipf.extract(name, outdir)
        del zipf
    else:
        raise ValueError('Not a zip file')

def standard_download_zip(in_url, out_rootdir, out_name):
    download_dir = os.path.join(out_rootdir, out_name)
    if not os.path.exists(download_dir):
        os.mkdir(download_dir)

    zip_path = os.path.join(download_dir, os.path.split(in_url)[1])
    unzipped_path = os.path.splitext(zip_path)[0]
    if not (os.path.exists(zip_path) or os.path.exists(unzipped_path)):
        print(f"Downloading {Path(in_url).name}")
        response = requests.get(in_url, verify=False)
        with open(zip_path, "wb") as file:
            # get request
            file.write(response.content)
    else:
        print("{} already exists. Skipping...".format(unzipped_path))

def list_ftpfiles(url):
    urlp = urlparse(os.path.split(url)[0])
    ftp = ftplib.FTP(urlp.netloc)
    ftp.login()
    ftp.cwd(urlp.path)

    try:
        files = ftp.nlst()
    except ftplib.error_perm as resp:
        if str(resp) == "550 No files found":
            print("No files in this directory")
        else:
            raise
    return(files)

def get_ftpfile(url, outdir):
    outfile=os.path.join(outdir, os.path.split(url)[1])
    urlp = urlparse.urlparse(os.path.split(url)[0])
    ftp = ftplib.FTP(urlp.netloc)
    ftp.login()
    ftp.cwd(urlp.path)

    if not os.path.exists(outfile):
        # Download it
        with open(outfile, 'wb') as fobj:  # using 'w' as mode argument will create invalid zip files
            ftp.retrbinary('RETR {}'.format(os.path.split(outfile)[1]), fobj.write)

###### MODIFIED FUNCTION FROM https://stackoverflow.com/questions/52081545/python-3-flattening-nested-dictionaries-and-lists-within-dictionaries
# TO MAKE SURE EACH COMPRESSED KEY IS UNIQUE.
def flatten(d, uid=0):
    out = {}
    for key, val in d.items():
        uid += 1
        if isinstance(val, dict):
            val = [val]
        if isinstance(val, list):
            for subdict in val:
                uid += 1
                deeper = flatten(subdict, uid=uid).items()
                out.update({key + str(uid) + '_' + key2 + str(uid): val2 for key2, val2 in deeper})
        else:
            out[key + str(uid) + '_'] = val
    return out


#Split a string by a separator and strip each sub-part of blank spaces on the ends
def split_strip(in_record, sep=','):
    if isinstance(in_record.split(sep), list):
        return([cat.strip() for cat in in_record.split(sep)])
    else:
        in_record.strip()

# Regex search dictionary keys and return values associated with matches
# max_i limits the number of matches
# in_pattern can be either as a simple string or as a list where the first element is the pattern and the second is max_i
def re_search_dict(in_dict, in_pattern, max_i=0):
    if isinstance(in_pattern, list):
        max_i = in_pattern[1]
        in_pattern = in_pattern[0]

    out_list = [in_dict[k] for k in in_dict if re.search(in_pattern, k)]
    if out_list:
        if max_i == 0:
            return (out_list[0])
        else:
            return (out_list[:max_i])


#Export attribute table from an ESRI-compatible feature class to csv
def CopyRows_pd(in_table, out_table, fields_to_copy):
    #Make sure fields_to_copy is a list
    if type(fields_to_copy) == str:
        fields_to_copy = [fields_to_copy]

    if type(fields_to_copy) == dict:
        dict_for_renaming = fields_to_copy
        fields_to_copy = list(fields_to_copy.keys())

    fields_to_copy_valid = []
    intable_flist = [f2.name for f2 in arcpy.ListFields(in_table)]
    for f1 in fields_to_copy:
        if f1 in intable_flist:
            fields_to_copy_valid.append(f1)
        else:
            print("{0} field is not present in {1}".format(f1, in_table))

    rows_to_copy_dict = defaultdict(float)
    with arcpy.da.SearchCursor(in_table, ['OID@']+fields_to_copy_valid) as cursor: #Other fields are badly entered
        for row in cursor:
            rows_to_copy_dict[row[0]] = list(row[1:])

    out_pd = pd.DataFrame.from_dict(data=rows_to_copy_dict, orient='index')
    out_pd.columns = fields_to_copy_valid
    if 'dict_for_renaming' in locals():
        out_pd.rename(columns={k:v for k,v in dict_for_renaming.items() if k in fields_to_copy_valid},
                      inplace=True)
    out_pd.to_csv(out_table, index=False)


# Resample a dictionary of rasters (in_vardict) to the resolution of a template raster (in_hydrotemplate), outputting
# the resampled rasters to paths contained in another dictionary (out_vardict) by keys
#See resample tool for resampling_type options (BILINEAR, CUBIC, NEAREST, MAJORITY)
def hydroresample(in_vardict, out_vardict, in_hydrotemplate, resampling_type='NEAREST'):
    templatedesc = arcpy.Describe(in_hydrotemplate)

    # Check that all in_vardict keys are in out_vardict (that each input path has a matching output path)
    keymatch = {l: l in out_vardict for l in in_vardict}
    if not all(keymatch.values()):
        raise ValueError('All keys in in_vardict are not in out_vardict: {}'.format(
            [l for l in keymatch if not keymatch[l]]))

    # Iterate through input rasters
    for var in in_vardict:
        outresample = out_vardict[var]

        if not arcpy.Exists(outresample):
            print('Processing {}...'.format(outresample))
            arcpy.env.extent = arcpy.env.snapRaster = in_hydrotemplate
            arcpy.env.XYResolution = "0.0000000000000001 degrees"
            arcpy.env.cellSize = templatedesc.meanCellWidth
            print('%.17f' % float(arcpy.env.cellSize))

            try:
                arcpy.management.Resample(in_raster=in_vardict[var],
                                          out_raster=outresample,
                                          cell_size=templatedesc.meanCellWidth,
                                          resampling_type=resampling_type)
            except Exception:
                print("Exception in user code:")
                traceback.print_exc(file=sys.stdout)
                arcpy.ResetEnvironments()

        else:
            print('{} already exists...'.format(outresample))

        # Check whether everything is the same
        maskdesc = arcpy.Describe(outresample)

        extentcomp = maskdesc.extent.JSON == templatedesc.extent.JSON
        print('Equal extents? {}'.format(extentcomp))
        if not extentcomp: print("{0} != {1}".format(maskdesc.extent, templatedesc.extent))

        cscomp = maskdesc.meanCellWidth == templatedesc.meanCellWidth
        print('Equal cell size? {}'.format(cscomp))
        if not cscomp: print("{0} != {1}".format(maskdesc.meanCellWidth, templatedesc.meanCellWidth))

        srcomp = compsr(outresample, in_hydrotemplate)
        print('Same Spatial Reference? {}'.format(srcomp))
        if not srcomp: print("{0} != {1}".format(maskdesc.SpatialReference.name, templatedesc.SpatialReference.name))

    arcpy.ResetEnvironments()

#Extract xarray values by point
def extract_xr_by_point(in_xr, in_pointdf, in_df_id,
                        in_xr_lon_dimname='lon', in_xr_lat_dimname='lat',
                        in_df_lon_dimname='POINT_X', in_df_lat_dimname='POINT_Y'
                        ):
    df_asxr = in_pointdf.set_index(in_df_id).to_xarray()

    isel_dict = {in_xr_lon_dimname: df_asxr[in_df_lon_dimname],
                 in_xr_lat_dimname: df_asxr[in_df_lat_dimname],}
    pixel_values = in_xr.sel(isel_dict , method="nearest")
    pixel_values_df = pixel_values.reset_coords(drop=True). \
        to_dataframe(). \
        reset_index()
    return(pixel_values_df)

def spatiotemporal_chunk_optimized_acrosstime(in_xr, lat_dimname='lat', lon_dimname='lon', time_dimname='time'):
    #This function rechunks xarray in chunks of 1,000,000 elements (ideal chunk size) — https://xarray.pydata.org/en/v0.10.2/dask.html
    n_timesteps = in_xr.dims[time_dimname]
    spatial_chunk_size = np.ceil((1000000/n_timesteps)**(1/2))
    kwargs = {
        time_dimname: n_timesteps,
        lat_dimname: spatial_chunk_size,
        lon_dimname: spatial_chunk_size
    }
    return(in_xr.chunk(chunks=kwargs))