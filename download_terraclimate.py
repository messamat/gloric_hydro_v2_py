from setup_gloric import *

#Download data from https://climate.northwestknowledge.net/TERRACLIMATE-DATA/
#Palmer Drought Severity Index - PDSI
#precipitation - ppt
#climatic water deficit - def
#soil water equivalent - swe

#Set up directories
terra_dir = os.path.join(datdir, 'climate', 'terra')
pdsi_dir = os.path.join(terra_dir, 'pdsi')
ppt_dir = os.path.join(terra_dir, 'ppt')
def_dir = os.path.join(terra_dir, 'def')
swe_dir = os.path.join(terra_dir, 'swe')
tmin_dir = os.path.join(terra_dir, 'tmin')
tmax_dir = os.path.join(terra_dir, 'tmax')


pathcheckcreate(pdsi_dir)
pathcheckcreate(ppt_dir)
pathcheckcreate(def_dir)
pathcheckcreate(swe_dir)
pathcheckcreate(tmin_dir)
pathcheckcreate(tmax_dir)

for suffix in ['tmax']: #'ppt', 'def', 'swe'
    for yr in range(1958, 2023):
        in_url ='https://climate.northwestknowledge.net/TERRACLIMATE-DATA/TerraClimate_{0}_{1}.nc'.format(suffix, yr)
        out_dir = os.path.join(terra_dir, suffix.lower())
        out_file = os.path.join(out_dir, os.path.split(in_url)[1])

        if not os.path.exists(out_file):
            with open(out_file, "wb") as file:
            # get request
                print(f"Downloading {Path(in_url).name}")
                response = requests.get(in_url)
                if response.ok:
                    file.write(response.content)
                else:
                    continue
        else:
            print("{} already exists. Skipping...".format(os.path.split(out_file)[1]))



