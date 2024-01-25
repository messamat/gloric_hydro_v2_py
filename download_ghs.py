from setup_gloric import *

ghspop_dir = os.path.join(datdir, 'anthropo', 'ghspop')
ghsbuilt_dir = os.path.join(datdir, 'anthropo', 'ghsbuilt')
pathcheckcreate(ghspop_dir)
pathcheckcreate(ghsbuilt_dir)

#https://ghsl.jrc.ec.europa.eu/ghs_pop2023.php
#https://ghsl.jrc.ec.europa.eu/download.php?ds=pop

ghspop_webdir = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/"
ghsbuilt_webdir = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/"


for yr in range(1975, 2025, 5):
    in_url = urljoin(
        ghspop_webdir,
        "GHS_POP_E{0}_GLOBE_R2023A_4326_3ss/V1-0/GHS_POP_E{0}_GLOBE_R2023A_4326_3ss_V1_0.zip".format(yr)
    )
    out_file = os.path.join(ghspop_dir, os.path.split(in_url)[1])

    if not arcpy.Exists(out_file):
        standard_download_zip(in_url,
                              out_rootdir=ghspop_dir,
                              out_name=out_file)

for yr in range(1975, 2025, 5):
    in_url = urljoin(
        ghsbuilt_webdir,
        "GHS_BUILT_S_E{0}_GLOBE_R2023A_4326_3ss/V1-0/GHS_BUILT_S_E{0}_GLOBE_R2023A_4326_3ss_V1_0.zip".format(yr)
    )
    out_file = os.path.join(ghsbuilt_dir, os.path.split(in_url)[1])

    if not arcpy.Exists(out_file):
        standard_download_zip(in_url,
                              out_rootdir=ghsbuilt_dir,
                              out_name=out_file)


