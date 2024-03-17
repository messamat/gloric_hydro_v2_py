import arcpy

from setup_gloric import *

gires = os.path.join(datdir, 'gires', 'GIRES_v10.gdb', 'GIRES_v10_rivers')
kldiv_tab = getfilelist(os.path.join(resdir, 'figures'), repattern='global_KLdiv_[0-9]{8}[.]csv$')[-1]

gires_kl_gdb = os.path.join(resdir, 'gires_KLdiv.gdb')
pathcheckcreate(gires_kl_gdb)
gires_kl = os.path.join(gires_kl_gdb, 'GIRES_v10_rivers_KLdiv_join')

if not arcpy.Exists(gires_kl):
    arcpy.CopyFeatures_management(gires, gires_kl)

fast_joinfield(in_data=gires_kl,
               in_field='HYRIV_ID',
               join_table=kldiv_tab,
               join_field='HYRIV_ID',
               fields=[['KLdiv_diff', 'KLdiv_diff']])

#Export predictions by drainage area size class
for da in [[0, 10], [10, 100], [100, 1000], [10**3,10**4], [10**4,10**5], [10**5,10**6], [10**6,10**7]]:
    subriver_out = os.path.join(os.path.split(gires_kl)[0],
                                '{0}_DA{1}_{2}'.format(os.path.split(gires_kl)[1],
                                                        re.sub('[.]', '', str(da[0])),
                                                        re.sub('[.]', '', str(da[1]))))
    sqlexp = 'UPLAND_SKM >= {0} AND UPLAND_SKM <= {1}'.format(da[0], da[1])
    print(sqlexp)
    arcpy.MakeFeatureLayer_management(gires_kl, out_layer='subriver', where_clause=sqlexp)
    arcpy.CopyFeatures_management('subriver', subriver_out)
    arcpy.Delete_management('subriver')