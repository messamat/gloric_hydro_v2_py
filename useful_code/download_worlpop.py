from setup_gloric import *
#pip install git+https://github.com/wpgp/wpgpDownloadPy

wp_outdir = os.path.join(datdir, 'anthropo', 'worldpop')
pathcheckcreate(wp_outdir)

#Download 2020 - 1km dataset
url_worldpop1km="ftp://ftp.worldpop.org.uk/GIS/Population/Global_2000_2020/2020/0_Mosaicked/ppp_2020_1km_Aggregated.tif"
#get_ftpfile(url=url_worldpop1km, outdir=wp_outdir)

#Download 2020 - 100m dataset by country
url_worldpop_topdownconstrained_BGSM = "ftp://ftp.worldpop.org//GIS//Population//Global_2000_2020_Constrained//2020//BSGM//"

def geturl_worldpop_100m(rooturl, abrv):
    out_url = urljoin(rooturl,
                               "{0}//{1}_ppp_2020_constrained.tif".format(abrv.upper(), abrv.lower()))
    return(out_url)

#Get all country abbreviations
for country in list_ftpfiles(url_worldpop_topdownconstrained_BGSM):
    print(country)
    country_url = geturl_worldpop_100m(rooturl=url_worldpop_topdownconstrained_BGSM, abrv=country)
    print(country_url)
    get_ftpfile(url=country_url, outdir=wp_outdir)


##Import maxar ones
maxardirs_url = "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/maxar_v1/"

def listFD(url, ext=''):
    page = requests.get(url).text
    print page
    soup = BeautifulSoup(page, 'html.parser')
    return [url + '/' + node.get('href') for node in soup.find_all('a') if node.get('href').endswith(ext)]

for popdir in listFD(maxardirs_url):
    if re.match('.*data[.]worldpop[.]org[/]GIS[/]Population[/]Global_2000_2020_Constrained[/]2020[/]maxar_v1[/]{2}[A-Z]{3}[/]',
                popdir):
        outfile = "{}_ppp_2020_constrained.tif".format(popdir[-4:-1].lower())
        in_url = urlparse.urljoin(popdir, outfile)
        print(in_url)
        dlfile(in_url, outpath = wp_outdir, outfile = outfile, ignore_downloadable=True)









