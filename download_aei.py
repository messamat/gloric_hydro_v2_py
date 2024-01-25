
from setup_gloric import *

#Set up directories
aei_dir = os.path.join(datdir, 'anthropo', 'aei')
pathcheckcreate(aei_dir)

#Record
"https://zenodo.org/records/7809342"

for yr in range(1900, 2020, 5):
    in_url ='https://zenodo.org/records/7809342/files/G_AEI_{}.ASC'.format(yr)
    out_file = os.path.join(aei_dir, os.path.split(in_url)[1])

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

for yr in range(1900, 2020, 5):
    in_url ='https://zenodo.org/records/7809342/files/MEIER_G_AEI_{}.ASC'.format(yr)
    out_file = os.path.join(aei_dir, os.path.split(in_url)[1])

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