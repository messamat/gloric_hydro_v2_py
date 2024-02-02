import os.path

from setup_gloric import *

riverice_dir = os.path.join(datdir, 'riverice')
pathcheckcreate(riverice_dir)

#Download river ice table
riverice_url = "https://zenodo.org/records/3372709/files/global_river_ice_dataset.csv"
riverice_tab = os.path.join(riverice_dir, os.path.split(riverice_url)[1])
if not os.path.exists(riverice_tab):
    df_raw = pd.read_csv(riverice_url)
    df_raw.to_csv(riverice_tab)

#Download spatial info on landsat scenes for Landsat 4-9 (> 1984 corresponding to the river ice metadata)
#metadata: https://www.usgs.gov/landsat-missions/landsat-shapefiles-and-kml-files
landsat_url = "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/atoms/files/WRS2_descending_0.zip"
standard_download_zip(in_url=landsat_url,
                      out_rootdir=riverice_dir)