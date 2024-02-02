from setup_gloric import *

grwl_dir = os.path.join(datdir, 'grwl')
pathcheckcreate(grwl_dir)

grwl_url = "https://zenodo.org/api/records/1297434/files-archive"
out_file = os.path.join(grwl_dir, '1297434.zip')
if not arcpy.Exists(out_file):
    standard_download_zip(in_url=grwl_url,
                          out_rootdir=grwl_dir)