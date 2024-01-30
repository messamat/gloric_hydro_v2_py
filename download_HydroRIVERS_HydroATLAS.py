from setup_gloric import *

HydroRIVERS_url = "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10.gdb.zip"
RiverATLAS_url = "https://figshare.com/ndownloader/files/20087321"

zip_path_HydroRIVERS = os.path.join(datdir, 'hydroatlas', 'HydroRIVERS_v10.gdb.zip')
zip_path_RiverATLAS = os.path.join(datdir, 'hydroatlas', 'RiverATLAS_Data_v10.gdb.zip')

#Download continential hydrorivers
continent_dir = os.path.join(datdir, 'hydroatlas', 'hydrorivers_cont')
pathcheckcreate(continent_dir)
for continent in ['af', 'ar', 'as', 'au', 'eu', 'na', 'sa', 'si']:
    in_url = f"https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_{continent}.gdb.zip"
    out_f = os.path.join(continent_dir, os.path.split(in_url)[1])
    if not arcpy.Exists(out_f):
        standard_download_zip(in_url=in_url,
                              out_rootdir=continent_dir)
    with zipfile.ZipFile(out_f, 'r') as zip_ref:
        zip_ref.extractall(os.path.dirname(out_f))

#Download global hydrorivers
if not os.path.exists(zip_path_HydroRIVERS):
    with open(zip_path_HydroRIVERS, "wb") as file:
        # get request
        print(f"Downloading HydroRIVERs")
        response = requests.get(HydroRIVERS_url, verify=False)
        file.write(response.content)
else:
    print(zip_path_HydroRIVERS, "already exists... Skipping download.")

with zipfile.ZipFile(zip_path_HydroRIVERS, 'r') as zip_ref:
    zip_ref.extractall(os.path.dirname(zip_path_HydroRIVERS))

#Download global RiverATLAS
if not os.path.exists(zip_path_RiverATLAS):
    with open(zip_path_RiverATLAS, "wb") as file:
        # get request
        print(f"Downloading HydroRIVERs")
        response = requests.get(RiverATLAS_url, verify=False)
        file.write(response.content)
else:
    print(zip_path_RiverATLAS, "already exists... Skipping download.")

with zipfile.ZipFile(zip_path_RiverATLAS, 'r') as zip_ref:
    zip_ref.extractall(os.path.dirname(zip_path_RiverATLAS))

arcpy.management.CopyRows(
    os.path.join(os.path.splitext(zip_path_RiverATLAS)[0], 'RiverATLAS_v10'),
    out_table = os.path.join(resdir, 'RiverATLAS_v10tab.csv')
)




