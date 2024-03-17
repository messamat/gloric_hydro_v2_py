import arcpy.management

from setup_gloric import *

gires_dir = os.path.join(datdir, 'gires')
pathcheckcreate(gires_dir)

gires_url = "https://figshare.com/ndownloader/articles/14633022/versions/1"
out_file = os.path.join(gires_dir, 'GIRES_v10_gdb.zip')
if not arcpy.Exists(out_file):
    standard_download_zip(in_url=gires_url,
                          out_rootdir=gires_dir)
#Export to table
gires_tab = os.path.join(datdir, 'gires', 'GIRES_v10_rivers.csv')
if not arcpy.Exists(gires_tab):
    arcpy.management.CopyRows(in_rows=os.path.join(os.path.splitext(out_file)[0], 'GIRES_v10_rivers'),
                              out_table=gires_tab)
