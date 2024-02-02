from setup_gloric import *

fr_dir = os.path.join(datdir, 'gauges', 'ref_fr')
us_dir = os.path.join(datdir, 'gauges', 'ref_us')
uk_dir = os.path.join(datdir, 'gauges', 'ref_uk')
au_dir = os.path.join(datdir, 'gauges', 'ref_au')

for f in [fr_dir, us_dir, uk_dir, au_dir]:
    pathcheckcreate(f)

#France-----------------------------------------------------------------------------------------------------------------
#https://geo.data.gouv.fr/fr/datasets/29819c27c73f29ee1a962450da7c2d49f6e11c15
#only those with at least 40 years of data
"""
(a) at least 40 years of daily records; (b) the gauging station controls a catchment with no appreciable direct human 
influence on river flow; (c) data quality is suitable for low flow analysis.
Statistical trend and step-change analysis on a number of streamflow indices"""

standard_download_zip(
    in_url="https://transcode.geo.data.gouv.fr/links/5e2a1e86fa4268bc2554280e/downloads/5e2a24a91a984285a539f9da?format=SHP&projection=WGS84",
    out_rootdir=fr_dir,
    out_name="RRSE_METROPOLE.zip"
)

"https://files.geo.data.gouv.fr/link-proxy/www.data.eaufrance.fr/2020-01-23/5e2a24a91a98421c9539f9db/rrse-metropole.zip/metadonnees-rrse-metropole.pdf"

#USA--------------------------------------------------------------------------------------------------------------------
#GAGES-II Falcone et al. 2011
#Catalog entry: https://www.sciencebase.gov/catalog/item/631405bbd34e36012efa304a
#No copiable  link on the page

standard_download_zip(
    in_url="https://www.sciencebase.gov/catalog/file/get/631405bbd34e36012efa304a",
    out_rootdir=us_dir,
    out_name="GAGES_II_Geospa.zip"
)


#UK---------------------------------------------------------------------------------------------------------------------
#https://nrfa.ceh.ac.uk/benchmark-network
"""Use is made of the National River Flow Archive’s (NRFA) broad definition of ‘natural’ catchments. 
These are defined as ‘having no abstractions or discharges, or that the net variation due to such impacts is so 
limited that the gauged flow is considered to be within 10% of the natural flow at, or in excess of, 
the 95 percentile flow’. 

No minimum record length: "Ideally, a continuous record of, say, 25 years, would be desirable. Where sites have a similar 
response to a nearby site, the longer record was generally accepted. Stations with short records (< 10 years) were
 considered if they satisfied the other criteria and were strategically located."
""" #(Bradford and Marsh 2003).

#Metadata for stations: https://nrfa.ceh.ac.uk/sites/default/files/UKBN_Station_List_vUKBN2.0_1.xlsx
#User guide: http://nrfa.ceh.ac.uk/sites/default/files/UKBN2_User_Guide_APR2018.pdf

uk_metadata = os.path.join(uk_dir, 'UKBN_Station_List_vUKBN2.0_1.xlsx')
uk_url = "https://nrfa.ceh.ac.uk/sites/default/files/UKBN_Station_List_vUKBN2.0_1.xlsx"
if not os.path.exists(uk_metadata):
    with open(uk_metadata, "wb") as file:
        # get request
        print(f"Downloading {Path(uk_url).name}")
        response = requests.get(uk_url, verify=False)
        if response.ok:
            file.write(response.content)



#Australia -------------------------------------------------------------------------------------------------------------
"""
The 222 HRSs were selected from a preliminary list of potential streamflow stations across Australia according to the 
HRS selection guideline (SKM, 2010). These guidelines specified four criteria for identifying the high-quality reference
 stations, namely unregulated catchments with minimal land use change, a long period of record (greater than 30 years) 
 of high-quality streamflow observations, spatial representativeness of all hydroclimate regions and the importance of 
 site as assessed by stakeholders.
""" #Zhang et al. 2016

#http://www.bom.gov.au/water/hrs/
#Station details (4 digit precision on coordinates): http://www.bom.gov.au/water/hrs/content/hrs_station_details.csv
#Other metadata (3-digit precision on coordinates): http://www.bom.gov.au/water/hrs/content/hrs_station_facts.csv
#Forbidden 403: not possible to download programmatically