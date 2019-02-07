# settings_template.py
# The settings template file for the PSU CSAR AWDB Retrive tool.
# Please add all required values and edit any necessary defaults
# and save this file as settings.py.

# the dir containing this file
import os
repo = os.path.abspath(os.path.dirname(__file__))


## ArcGIS Server Settings
SERVER_ADDRESS =  # hostname of server
SERVER_PORT =  # port to connect to ArcGIS server
SERVER_USER =  # ArcGIS admin account user name
SERVER_PASS =  # ArcGIS admin account password


## Output Directories
ARCHIVE_WORKSPACE = r"C:\inetpub\ftproot\AWDB\Stations"  # zip each shapefile here for FTP access
TEMP_WORKSPACE = os.path.join(repo, "temp")  # location for intermediate files
LOG_DIR = os.path.join(repo, "log")  # location for log files
MAP_DIR = os.path.join(repo, "maps")  # location for map mxds


## SDE target database -- for WFSs
SDE_WORKSPACE = os.path.join(repo, "awdb.sde")  # ownership SDE database connection
SDE_READONLY = os.path.join(repo, "awdb_readonly.sde")  # readonly SDE database connection
SDE_DATABASE = "awdbprod"
SDE_USERNAME = "awdb"
FDS_SDE_PREFIX = SDE_DATABASE + "." + SDE_USERNAME + "."  # do not edit

# name of output feature dataset
FDS_NAME = "AWDB"  # set to None to write to DB root, not dataset


## Source Web Service URLs
# url of the NRCS AWDB SOAP WDSL (defines the web API connection)
WDSL_URL = "https://wcc.sc.egov.usda.gov/awdbWebService/services?WSDL"
# url of the USGS site information REST service
USGS_URL = "https://waterservices.usgs.gov/nwis/site/"


# number of worker processes to get station records (max number of processes)
WORKER_PROCESSES = 10

# maximum number of records per metadata request
# (larger is faster but more likely to timeout)
MAX_REQUEST = 250

# number of attempts to retry getting station
RETRY_COUNT = 2

## ArcGIS Online Settings
USER = # ArcGIS Online user name
PASSWORD = # ArcGIS Online password
## Path to ArcGIS Pro project that contains the maps
PROJECT_PATH = os.path.join(repo,r"projects\awdb\awdb.aprx")
# Suffixes for feature services
WFS_SUFFIXES = ["ALL", "ACTIVE", "INACTIVE"]
