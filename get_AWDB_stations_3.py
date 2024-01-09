# --------------------------------------------------------------------
# NAME:     get_AWDB_stations.py
# AUTHOR:   Jarrett Keifer and Lesley Bross
# DATE:     11/13/2014 Updated 02/15/2019
#
# DESC:     Downloads SNOTEL, Snow Course, and USGS stations from the
#           NRCS Air-Water Database, reprojects them, writes them to
#           shapefiles, then publishes them feature services on ArcGIS Online
#
# USAGE:    The script requires no arguments, but some key constants
#           need to set in the settings.py file. Copy the
#           settings_template.py file with the namr settings.py and
#           edit as reqiured.
#
#           Run with python 3
# --------------------------------------------------------------------

# some import statements in functions to speed process generation
from __future__ import print_function, absolute_import
from suds.client import Client
from urllib.error import URLError
from multiprocessing import Process, Lock, Queue
import traceback
import os
import logging


# load settings from settings.py
try:
    import settings
except:
    raise Exception(
        "Please copy the settings_template.py file to " +
        "a file named settings.py and edit the values as required."
    )


# --------------------------------------
#            GLOBAL CONSTANTS
# --------------------------------------

__DEBUG__ = False  # true outputs debug-level messages to stderr

# NRCS AWDB network codes to download
NETWORKS = ["SNTL", "SNOW", "USGS", "COOP", "SCAN", "SNTLT", "OTHER", "BOR",
            "MPRC", "MSNT"]
#NETWORKS = ["USGS"]


## Dictionaries of the station fields
# these fields are required, and are geometry,
# so do not need to be aded to the output FC
REQUIRED_FIELDS = [
    {"field_name": "elevation"},
    {"field_name": "latitude"},
    {"field_name": "longitude"},
]

# these fields will be added to the output FC, but can be null
FIELDS = [
    {"field_name": "actonId",             "field_type": "TEXT", "field_length": 20},  # 0
    {"field_name": "beginDate",           "field_type": "DATE"},                      # 1
    {"field_name": "countyName",          "field_type": "TEXT", "field_length": 25},  # 2
    {"field_name": "endDate",             "field_type": "DATE"},                      # 3
    {"field_name": "fipsCountryCd",       "field_type": "TEXT", "field_length": 5},   # 4
    {"field_name": "fipsCountyCd",        "field_type": "SHORT"},                     # 5
    {"field_name": "fipsStateNumber",     "field_type": "SHORT"},                     # 6
    {"field_name": "huc",                 "field_type": "TEXT", "field_length": 20},  # 7
    {"field_name": "name",                "field_type": "TEXT", "field_length": 100}, # 8
    {"field_name": "shefId",              "field_type": "TEXT", "field_length": 20},  # 9
    {"field_name": "stationDataTimeZone", "field_type": "DOUBLE"},                    # 10
    {"field_name": "stationTimeZone",     "field_type": "DOUBLE"},                    # 11
    {"field_name": "stationTriplet",      "field_type": "TEXT", "field_length": 50},  # 12
    {"field_name": "elevation",           "field_type": "DOUBLE"},                    # 13
    {"field_name": "latitude",            "field_type": "FLOAT"},                     # 14
    {"field_name": "longitude",           "field_type": "FLOAT"}                      # 15
]

## USGS metadata retrival constants
# fields to add: tuple of name and data type
NEW_FIELDS = [
    ("basinarea", "DOUBLE"),
    ("USGS_ID", "TEXT"),
    ("USGSname", "TEXT"),
]
# the stationTriplet field name (used for the ID) is defined in FIELDS above
STATION_ID_FIELD = FIELDS[12]["field_name"]

## Message inserted into queue to signal end of logging message
QUEUE_DONE = "DONE"
MESSAGE_CODE = "MSG"

## Logging constants
# contains debug info
FULL_LOGFILE = os.path.join(settings.LOG_DIR, "AWDB_LOG_3.txt")
# records processed OK/Failed only
SUMMARY_LOGFILE = os.path.join(settings.LOG_DIR, "AWDB_SUMMARY_3.txt")

## Other
# name of temp GDB
TEMP_GDB_NAME = "awdb_temp"


# -------------------------------
#             LOGGING
# -------------------------------

# LOGGING IS SETUP AFTER THE MAIN CHECK BECAUSE OF MULTIPROCESSING


# -------------------------------
#            FUNCTIONS
# -------------------------------

def recursive_asdict(d):
    """
    Convert Suds object into serializable format (dictonary).

    Requires: d -- the input suds object

    Returns:  out -- a dictionary representation of d
    """

    from suds.sudsobject import asdict

    out = {}
    for key, value in asdict(d).items():
        if hasattr(value, '__keylist__'):
            out[key] = recursive_asdict(value)
        elif isinstance(value, list):
            out[key] = []
            for item in value:
                if hasattr(item, '__keylist__'):
                    out[key].append(recursive_asdict(item))
                else:
                    out[key].append(item)
        else:
            out[key] = value

    return out


def grouper(iterable, n, fillvalue=None):
    """
    Takes an iterable and splits it into pieces of n length.
    The last piece will be filled to fit the desired length with
    whatever is specified by the fillvalue argument.

    Requires: iterable -- the iterable to be split
              n -- length of each piece made from iterable

    Optional: fillvalue -- value to use to make last piece length = n
                           If fillvalue is None, last piece will not be filled
                           DEFAULT: None

    Returns:  pieces -- a list of the pieces made from iterable
                        each piece is a list

    Example:  grouper([0, 1, 2, 3, 4, 5, 6, 7], 5) returns [[0, 1, 2, 3, 4], [5, 6, 7]]
              grouper([0, 1, 2, 3, 4, 5, 6, 7], 6, 'f') returns [[0, 1, 2, 3, 4, 5], [6, 7, 'f', 'f', 'f', 'f']]
    """

    from itertools import zip_longest

    args = [iter(iterable)] * n
    pieces = list(zip_longest(*args, fillvalue=fillvalue))

    for i, piece in enumerate(pieces):
        pieces[i] = list(piece)

    # remove any null values from station group
    if fillvalue is None:
        pieces[len(pieces)-1] = \
            [x for x in pieces[len(pieces)-1] if x is not None]

    return pieces


def get_multiple_stations_thread(stations, outQueue, queueLock, recursiveCall=0):
    """
    Gets the metadata for a list of stations from the AWDB web service. Designed to be
    run as a worker process as part of a multiprocessed solution to get stations.
    Called from get_stations().

    Required: stations -- a list of stations to retrieve by station triplet
              outQueue -- the queue object into which retrieved stations should be placed
                          the queue is read by the main process and records are inserted
                          into an FC as they are received
              queueLock -- the lock object used to prevent collisions when writing to the queue

    Optional: recursiveCall -- the number of times the process should recursively call
                               itself to retry any stations that were not retrieved
                               successfully.
                               DEFAULT is 0, so stations are not retried by default.

    Returns:  Error code
    """

    data = None

    try:
        client = Client(settings.WDSL_URL)  # connect to the service definition
        if len(stations) == 1:
            data = [client.service.getStationMetadata(stations[0])]
        else:
            data = client.service.getStationMetadataMultiple(stationTriplets=stations)
    except Exception as e:
        with queueLock:
            outQueue.put((MESSAGE_CODE, 15, e))
            outQueue.put((MESSAGE_CODE, 15, traceback.format_exc()))
    except URLError as e:
        if "Errno 10060" in e:  # this is a connection error -- time out or no response
            with queueLock:
                outQueue.put((MESSAGE_CODE, 15, e))
                outQueue.put((
                    MESSAGE_CODE,
                    15,
                    "Error connecting to server. Retrying...",
                ))
        else:
            with queueLock:
                outQueue.put((MESSAGE_CODE, 15, e))
                outQueue.put((MESSAGE_CODE, 15, traceback.format_exc()))

    if data:
        for station in data:
            station = validate_station_data(recursive_asdict(station))

            if station:
                with queueLock:
                    outQueue.put(station)
                stations.remove(station["stationTriplet"])
            else:
                pass

    if len(stations) and recursiveCall:
        with queueLock:
            outQueue.put((
                MESSAGE_CODE,
                15,
                "Some stations were not successfully retrieved; retrying...",
            ))
        recursiveCall -= 1
        get_multiple_stations_thread(
            stations,
            outQueue,
            queueLock,
            recursiveCall=recursiveCall,
        )
    elif len(stations):
        with queueLock:
            outQueue.put((
                MESSAGE_CODE,
                15,
                "Stations could not be successfully retrieved:\n{0}".format(stations),
            ))

    return 0


def get_stations(stationIDs, stationQueue):
    """
    This function calls get_multiple_stations_thread with groups of stations to be
    retrieved as multiple worker processes. It controls how many worker processes
    are running at any given time, keeping that number at or below the WORKER_PROCESSES
    constant.

    Requires: stationIDs -- the complete list of stations to retrieve, by station triplet
              stationQueue -- the queue object that the worker process will write station
                              records to

    Returns:  None
    """

    import time

    queueLock = Lock()
    # list to track running processes
    processes = []
    # split station list into 1000-station chunks to avoid timeouts
    for stationgroup in grouper(stationIDs, settings.MAX_REQUEST):
        # create process to get metadata for each station group
        getProcess = Process(
            target=get_multiple_stations_thread,
            args=(stationgroup, stationQueue, queueLock),
            kwargs={"recursiveCall": settings.RETRY_COUNT}
        )
        getProcess.daemon = True
        getProcess.start()
        processes.append(getProcess)

        # if at max processes, wait until one closes before starting another
        while len(processes) == settings.WORKER_PROCESSES:
            for p in processes:
                if not p.is_alive():
                    # p.is_alive() will be false if process closes
                    processes.remove(p)
            time.sleep(0.5)

    # join on remaining child processes to prevent done message
    # until all records are returned
    for p in processes:
        p.join()

    stationQueue.put(QUEUE_DONE)


def validate_station_data(station):
    """
    Checks a station's data to ensure all required fields are present,
    and inserts a null value into any non-required fields.

    Requires: station -- the station data returned from the server as a dict

    Returns:  station -- the validated station object

    Error condition: if a required field is missing, will return False
    """

    # test to ensure all required fields have a value
    for field in REQUIRED_FIELDS:
        try:
            station[field["field_name"]]
        except:
            return False

    # test all non-required fields for a value; insert null if missing
    for field in FIELDS:
        try:
            station[field["field_name"]]
        except KeyError:
            station[field["field_name"]] = None

    return station


def get_network_stations(networkCode, fc_name, spatialref, workspace="in_memory"):
    """
    Queries the AWDB to get a list of all stations by station triplet in the network
    specified. Then spawns get_stations() as a child process. get_stations retrieves
    the metadata of the stations, the records of which are placed into the stationQueue.
    As station records are returned, this function reads the records from the queue
    and writes them as features in a feature class created in the specified workspace.

    Requires: networkCode -- the code of the network to retrieve, i.e. SNTL
              fc_name -- the name of the fc to create in the specified workspace
              spatialref -- the spatial reference object to use for the fc

    Optional: workspace -- the workspace in which to create the fc
                           DEFAULT: "in_memory", the ArcGIS RAM workspace

    Returns: fc -- the result object from the CreateFeatureClass function
    """

    from arcpy import AddField_management, CreateFeatureclass_management
    from arcpy.da import InsertCursor

    LOGGER.info("\nGetting stations in the {0} network...".format(networkCode))
    # connect to the service definition
    client = Client(settings.WDSL_URL)
    # get list of station IDs in network
    stationIDs = client.service.getStations(networkCds=networkCode)
    numberofstations = len(stationIDs)
    LOGGER.log(
        15,
        "Found {0} stations in {1} network.".format(numberofstations,
                                                    networkCode)
    )

    # to pass back results from thread
    stationQueue = Queue()

    # create process to get station data
    getStationProcess = Process(target=get_stations,
                                args=(stationIDs, stationQueue))
    # start thread execution
    getStationProcess.start()

    LOGGER.info("Creating feature class in memory...")
    fc = CreateFeatureclass_management(
        workspace, fc_name, "POINT",
        has_z="ENABLED", spatial_reference=spatialref
    )

    LOGGER.info("Adding attribute fields to feature class...")
    for field in FIELDS:
        AddField_management(fc, **field)

    # tuple of fields to access with the insert cursor
    fieldsToAccess = (FIELDS[0]["field_name"],
                      FIELDS[1]["field_name"],
                      FIELDS[2]["field_name"],
                      "SHAPE@Z",
                      FIELDS[3]["field_name"],
                      FIELDS[4]["field_name"],
                      FIELDS[5]["field_name"],
                      FIELDS[6]["field_name"],
                      FIELDS[7]["field_name"],
                      "SHAPE@Y",
                      "SHAPE@X",
                      FIELDS[8]["field_name"],
                      FIELDS[9]["field_name"],
                      FIELDS[10]["field_name"],
                      FIELDS[11]["field_name"],
                      FIELDS[12]["field_name"],
                      FIELDS[13]["field_name"],
                      FIELDS[14]["field_name"],
                      FIELDS[15]["field_name"]
                      )

    countInserted = 0

    LOGGER.info("Writing stations to FC as data are returned from server...")

    # insert cursor to add records to fc
    with InsertCursor(fc, fieldsToAccess) as cursor:
        while True:
            station = stationQueue.get()  # get station data from queue

            if station == QUEUE_DONE:
                break

            try:
                if station[0] == MESSAGE_CODE:
                    LOGGER.log(station[1], station[2])
                    continue
            except KeyError:
                pass

            stationIDs.remove(station["stationTriplet"])

            cursor.insertRow((station[FIELDS[0]["field_name"]],
                              station[FIELDS[1]["field_name"]],
                              station[FIELDS[2]["field_name"]],
                              station["elevation"],
                              station[FIELDS[3]["field_name"]],
                              station[FIELDS[4]["field_name"]],
                              station[FIELDS[5]["field_name"]],
                              station[FIELDS[6]["field_name"]],
                              station[FIELDS[7]["field_name"]],
                              station["latitude"],
                              station["longitude"],
                              station[FIELDS[8]["field_name"]],
                              station[FIELDS[9]["field_name"]],
                              station[FIELDS[10]["field_name"]],
                              station[FIELDS[11]["field_name"]],
                              station[FIELDS[12]["field_name"]],
                              station[FIELDS[13]["field_name"]],
                              station[FIELDS[14]["field_name"]],
                              station[FIELDS[15]["field_name"]]
                              ))
            countInserted += 1

    LOGGER.info(
        "Successfully inserted {0} of {1} records into {2}.".format(
            countInserted, numberofstations, fc_name
        )
    )

    if countInserted != numberofstations:
        raise Exception("ERROR: Failed to get all stations for unknown reason.")

    return fc


def archive_GDB_FC(fc, outdir):
    """
    Copies an input FC from a geodatabase into a temp folder in shapefile format.
    Creates a zip file in the outdir, and copies the shapefile files into that
    zip archive. Deletes the temp folder after archiving.

    Requires: fc -- the feature class in a GDB to archive as a zip
              outdir -- the output location of the zip file

    Returns:  zippath -- the path to the created zip archive
    """

    import zipfile
    import glob
    import errno

    from datetime import datetime
    from arcpy import CopyFeatures_management
    from tempfile import mkdtemp
    from shutil import rmtree

    fc_name = os.path.basename(fc)
    today = datetime.today()

    tempfolder = mkdtemp()

    CopyFeatures_management(fc, os.path.join(tempfolder, fc_name))

    filelist = glob.glob(os.path.join(tempfolder, fc_name + ".*"))

    # the path to the output zipfile is ARCHIVE_WS/YYYY/MM/DD/fc_name.zip
    zippath = os.path.join(
        settings.ARCHIVE_WORKSPACE,
        today.strftime(
            "%Y{0}%m{0}%d{0}%Y-%m-%d_{1}.zip".format(os.path.sep, fc_name)
        )
    )

    # if full directory path does not exist we need to make it
    # so we try and ignore the error if it is already there
    try:
        os.makedirs(os.path.dirname(zippath))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e

    with zipfile.ZipFile(zippath, mode='w', compression=zipfile.ZIP_DEFLATED) as zfile:
        for f in filelist:
            if not f.upper().endswith('.LOCK'):
                newfile = today.strftime(
                    "%Y-%m-%d_{}".format(os.path.basename(f))
                )
                zfile.write(f, newfile)

    rmtree(tempfolder)

    return zippath

def save_FC(fc, outdir):
    """
    Copies an input FC from a geodatabase into a specified folder in shapefile format.
    Saves an input FC into a specified folder (outdir)

    Requires: fc -- the feature class to save
              outdir -- the output location for the feature class

    """
    from arcpy import CopyFeatures_management

    fc_name = os.path.basename(fc)

    CopyFeatures_management(fc, os.path.join(outdir, fc_name))

    return os.path.join(outdir, fc_name)

def create_active_only_FC(inpath):
    """
    Copies an input FC applying timestamp filters to create active-only shapefiles

    Requires: inpath -- the path of the source feature class with all records
              outdir -- the output location for the FGDB

    """
    from arcpy import FeatureClassToFeatureClass_conversion

    fc_name = os.path.basename(inpath)
    active_fc_name = "active_" + fc_name

    FeatureClassToFeatureClass_conversion(inpath, 
                                          os.path.dirname(inpath), 
                                          active_fc_name, " enddate = timestamp '2100-01-01 00:00:00'")


def replace_wfs_data(newdata, target_workspace):
    """
    Copy the new FC into the target workspace.

    Requires: newdata -- the FC to be copied
              target_workspace -- the location into which the data will be copied

    Returns:  None
    """
    from arcpy import CopyFeatures_management
    from arcpy import env
    env.overwriteOutput = True
    CopyFeatures_management(
        newdata,
        os.path.join(
            target_workspace,
            os.path.splitext(os.path.basename(newdata))[0]
        )
    )

def create_temp_workspace(directory, name, is_gdb=True):
    """
    Creates a temp workspace for processing. If is_gdb, will create a GDB.
    Else a folder will be created.

    Required: directory -- the directory in which to create the temp GDB
              name -- the name of the temp GDB

    Optional: is_gdb -- whether or not to create a GDB. Default is True.

    Returns:  path -- the full path to the temp workspace
    """
    import shutil
    from arcpy import CreateFileGDB_management

    LOGGER.info("Creating temp workspace {0} in {1}...".format(name,
                                                               directory))

    path = os.path.join(directory, name)

    if is_gdb:
        LOGGER.log(15, "Workspace will be format GDB.")
        path = path + ".gdb"

    if os.path.isdir(path):
        LOGGER.log(15, "Temp workspace already exists; removing...")
        shutil.rmtree(path)

    if is_gdb:
        CreateFileGDB_management(directory, name)
    else:
        os.mkdir(path)

    return path


def get_USGS_metadata(usgs_fc):
    """
    Access the USGS site information REST API to get the basin area
    for all applicable sites. Adds the basinarea field to the FC and
    writes the data returned from the REST serivce.

    Required: usgs_fc -- the feature class of records from the AWDB

    Returns:  None
    """

    import urllib
    import gzip
    from re import search
    from arcpy import ListFields, AddField_management
    from arcpy.da import SearchCursor, UpdateCursor
    import io

    # check for area field and add if missing
    fields = ListFields(usgs_fc)

    for fieldname, datatype in NEW_FIELDS:
        for field in fields:
            if field.name == fieldname:
                break
        else:
            AddField_management(usgs_fc, fieldname, datatype)

    # get a list of station IDs in the FC
    stationIDs = []
    with SearchCursor(usgs_fc, STATION_ID_FIELD) as cursor:
        for row in cursor:
            sid = row[0].split(":")[0]
            # valid USGS station IDs are between 8 and 15 char and are numerical
            if len(sid) >= 8 and not search('[a-zA-Z]', sid):
                stationIDs.append(sid)

    # setup and get the HTTP request
    request = urllib.request.Request(
        settings.USGS_URL,
        urllib.parse.urlencode({
            "format": "rdb",  # get the data in USGS rdb format
            "sites": ",".join(stationIDs),  # the site IDs to get, separated by commas
            "siteOutput": "expanded"  # expanded output includes basin area
            #"modifiedSince": "P" + str(SCRIPT_FREQUENCY) + "D"  # only get records modified since last run
        }).encode('utf-8')
    )

    # allow gzipped response
    request.add_header('Accept-encoding', 'gzip')
    response = urllib.request.urlopen(request)

    # check to see if response is gzipped and decompress if yes
    if response.info().get('Content-Encoding') == 'gzip':
        buf = io.BytesIO(response.read())
        data = gzip.GzipFile(fileobj=buf)
    else:
        data = response

    # parse the response and create a dictionary keyed on the station ID
    stationAreas = {}
    for line in data.readlines():
        line = line.decode('utf-8')
        if line.startswith('USGS'):
            # data elements in line (station record) are separated by tabs
            line = line.split('\t')
            # the 2nd element is the station ID, 3rd is the name,
            # and the 30th is the area
            # order in the tuple is important,
            # so data is entered into the correct fields in the table
            stationAreas[line[1]] = (line[29], line[1], line[2])

    # write the response data to the FC
    fieldsToAccess = [STATION_ID_FIELD]+[name for name, datatype in NEW_FIELDS]
    with UpdateCursor(usgs_fc, fieldsToAccess) as cursor:
        for row in cursor:
            stationid = row[0].split(":")[0]

            try:
                # row[1] is area
                row[1] = float(stationAreas[stationid][0])
            except KeyError:
                # in case no record was returned for ID
                # skip to next record
                continue
            except ValueError:
                # in case area returned is ""
                pass

            try:
                # row[2] is the USGS station ID
                row[2] = stationAreas[stationid][1]
            except ValueError:
                # in case ID returned is ""
                pass

            try:
                # row[3] is the USGS station name
                row[3] = stationAreas[stationid][2]
            except ValueError:
                # in case name returned is ""
                pass

            # no exception so data valid, update row
            cursor.updateRow(row)

def create_forecast_point_ws():
    from arcpy import CopyFeatures_management
    import arcpy

    bUSGSExists = False
    bBORExists = False
    LOGGER.info("create_forecast_point_ws...")

    USGS_Active = "active_stations_USGS"
    if arcpy.Exists(os.path.join(settings.AWDB_FGDB_PATH, USGS_Active)):
        bUSGSExists = True
    BOR_Active = "active_stations_BOR"
    if arcpy.Exists(os.path.join(settings.AWDB_FGDB_PATH, BOR_Active)):
        bBORExists = True
    FCST_Active = "active_stations_FCST"

    if (bUSGSExists and bBORExists):
      client = Client(settings.WDSL_URL)
      # get list of station IDs in network
      data = None
      forecastIDs = [] 
      data = client.service.getForecastPoints(networkCds="USGS",logicalAnd="true")
      if data:
        for station in data:
          try:
            forecastIDs.append(station["stationTriplet"])
          except:
            pass
      numberofstations = len(data)
      LOGGER.info('We processed %d records', numberofstations)
      LOGGER.info('%d records in array', len(forecastIDs))
      BOR_Temp_Active = "temp_" + BOR_Active
      sourceFc = os.path.join(settings.AWDB_FGDB_PATH, USGS_Active)
      targetFc = os.path.join(settings.AWDB_FGDB_PATH, FCST_Active)
      CopyFeatures_management(sourceFc, targetFc)
      LOGGER.info("Before %d records", getCount(targetFc))
      with arcpy.da.UpdateCursor(targetFc, ('stationTriplet')) as curs:
          for row in curs:
                test_triplet = row[0]
                if (test_triplet not in forecastIDs):                
                    curs.deleteRow()
      LOGGER.info("After %d records", getCount(targetFc))
      sourceFc = os.path.join(settings.AWDB_FGDB_PATH, BOR_Active)
      targetFc = os.path.join(settings.AWDB_FGDB_PATH, BOR_Temp_Active)
      CopyFeatures_management(sourceFc, targetFc)
      forecastIDs.clear()
      data = client.service.getForecastPoints(networkCds="BOR",logicalAnd="true")
      if data:
        for station in data:
          try:
            forecastIDs.append(station["stationTriplet"])
          except:
            pass
      numberofstations = len(data)
      LOGGER.info('%d records in array', len(forecastIDs))
      with arcpy.da.UpdateCursor(targetFc, ('stationTriplet')) as curs:
          for row in curs:
                test_triplet = row[0]
                if (test_triplet not in forecastIDs):                
                    curs.deleteRow()
      LOGGER.info("After %d records", getCount(targetFc))




    else:
      LOGGER.error("unable to locate {0} and or {1}. Forecast service will not be updated".format(USGS_Active, BOM_Active))

def getCount(fc):
    import arcpy
    return int(arcpy.GetCount_management(fc).getOutput(0))

def write_to_summary_log(message):
    """
    Write a message string to the summary logfile.

    Requires: message -- the message string to write to the log

    Returns:  None
    """
    with open(SUMMARY_LOGFILE, 'a') as summary:
        summary.write(message + "\n")


# ----------------------------
#             MAIN
# ----------------------------

def main():
    from datetime import datetime
    import shutil
    import arcpy
    from arcpy import env
    import update_ags_online_fs

    start = datetime.now()
    LOGGER.log(15, "\n\n--------------------------------------------------------------\n")
    LOGGER.log(15, "Started at {0}.".format(start))

    # create spatial ref objects
    # spatial ref WKID 4326: WGS 1984 GCS
    unprjSR = arcpy.SpatialReference(4326)
    # spatial ref WKID 102039: USA_Contiguous_Albers_Equal_Area_Conic_USGS_version
    prjSR = arcpy.SpatialReference(102039)

    # arcpy variable to allow overwriting existing files
    env.overwriteOutput = True

    # create temp processing workspace
    try:
        templocation = create_temp_workspace(
            settings.TEMP_WORKSPACE,
            TEMP_GDB_NAME,
        )
    except ExecuteError as e:
        if "ERROR 000732" in e.message:
            os.makedirs(settings.TEMP_WORKSPACE)
            templocation = create_temp_workspace(
                settings.TEMP_WORKSPACE,
                TEMP_GDB_NAME,
            )
        else:
            raise e

    LOGGER.log(15, "Temporary location is {0}.".format(templocation))

    wfsupdatelist = []  # list of wfs data to update
    archiveerror = 0
    copyerror = 0

    # process stations in each network
    for network in NETWORKS:
        fc = None
        fc_name = "stations_" + network
        try_count = 0
        archiveerror += 1  # add error to be removed after successful execution
        copyerror += 1 # add error to be removed after successful execution

        while try_count <= settings.RETRY_COUNT:
            try:
                try_count += 1
                fc = get_network_stations(network, fc_name, unprjSR)
            except Exception as e:
                LOGGER.log(15, e)
                LOGGER.log(15, traceback.format_exc())
                LOGGER.warning("\nError. Retrying...\n")
            else:
                break

        if fc:
            LOGGER.info("Reprojecting station data and writing to output...")
        else:
            LOGGER.error("ERROR: Failed to retrieve all stations from {0}. Skipping to next network...".format(network))
            write_to_summary_log("{}: stations_{} processing FAILED".format(datetime.now(), network))
            continue

        #if network == "USGS":
        #    LOGGER.info("USGS data requires area from USGS web service. Retreiving...")
        #    try:
        #        get_USGS_metadata(fc)
        #    except Exception as e:
        #        LOGGER.log(15, e)
        #        LOGGER.log(15, traceback.format_exc())
        #        LOGGER.error("Failed to retrieve the USGS area data. Could not continue.")
        #        write_to_summary_log("{}: stations_{} processing FAILED".format(datetime.now(), network))
        #        continue

        try:
            projectedfc = arcpy.Project_management(fc, os.path.join(templocation, fc_name), prjSR)  # from unprjSR to prjSR
        except Exception as e:
            LOGGER.log(15, e)
            LOGGER.log(15, traceback.format_exc())
            LOGGER.error("Failed to reproject the data. Could not continue.")
            write_to_summary_log("{}: stations_{} processing FAILED".format(datetime.now(), network))
            continue

        write_to_summary_log("{}: stations_{} processed OK".format(datetime.now(), network))

        # remove in_memory temp FC
        try:
            arcpy.Delete_management(fc)
        except:
            pass

        try:
            LOGGER.info("Saving the data to a FGDB ...")
            source_path = save_FC(projectedfc.getOutput(0),
                              settings.AWDB_FGDB_PATH)
            write_to_summary_log("{}: stations_{} saved OK".format(datetime.now(), network))
        except Exception as e:
            LOGGER.log(15, e)
            LOGGER.log(15, traceback.format_exc())
            LOGGER.error("Failed to archive the data.")
        else:
            archiveerror -= 1  # executed successfully, so no error

        try:
            LOGGER.info("Copying the data to active FGDB ...")
            create_active_only_FC(source_path)
            write_to_summary_log("{}: stations_{} copied for active".format(datetime.now(), network))
        except Exception as e:
            LOGGER.log(15, e)
            LOGGER.log(15, traceback.format_exc())
            LOGGER.error("Failed to make copies for inactive and active.")
        else:
            copyerror -= 1  # executed successfully, so no error

        LOGGER.info("Adding data to WFS update list...")
        wfsupdatelist.append(projectedfc.getOutput(0))

        # end processing of network

        # create forecast webservice
        # Commenting out. Not ready to use yet
        # create_forecast_point_ws()
        
    if wfsupdatelist:
        LOGGER.info("\nUpdating AGOL feature services in update list...")
        for wfspath in wfsupdatelist:
          fc_name = os.path.basename(wfspath) + "_" + settings.AGO_SUFFIX_ACTIVE
          LOGGER.log(15, "About to update {0}.".format(fc_name))
          update_ags_online_fs.update_feature_services(settings.PRO_PROJECT_PATH, fc_name)

    else:
        LOGGER.error("\nNo web services to update. Aborting...")
        return 300

    if archiveerror:
        LOGGER.info("\nOne or more FCs were not successfully archived. Script is aborting before temp data is removed...")
        write_to_summary_log("{}: {} web services FAILED".format(datetime.now(), archiveerror))
    elif copyerror:
        LOGGER.info("\nActive stations files were not created for one or more FCs.")
        write_to_summary_log("{}: {} web services FAILED".format(datetime.now(), archiveerror))
    else:
        LOGGER.info("\nAll processes executed successfully.")
        write_to_summary_log("{}: all web services updated OK".format(datetime.now()))
        try:
            LOGGER.info("Removing temp data...")
            shutil.rmtree(templocation)
        except Exception as e:
            LOGGER.log(15, e)
            LOGGER.log(15, traceback.format_exc())
            LOGGER.error("Could not remove temp data.")

    end = datetime.now()
    LOGGER.info("\nTime finished: {0}.".format(end))
    LOGGER.info("Time elapsed: {0}.".format(end-start))

    return 0


# --------------------------------
#            MAIN CHECK
# --------------------------------

# WARNING: main is ABSOULTELY NECESSARY on Windows when using multiprocessing.
# FAILURE TO USE THE MAIN CHECK WILL FILL ALL RAM AND CRASH THE ENTIRE SYSTEM.

if __name__ == '__main__':
    import sys

    # -------------------------------
    #             LOGGING
    # -------------------------------

    # in case user calls file with debug disabled override __DEBUG__ setting
    if not __debug__:
        __DEBUG__ = False

    # DEBUG level is 15; using logging.DEBUG writes SUDS to log

    # setup basic logger for file
    LOGGER = logging.getLogger()
    LOGGER.setLevel(15)

    # to write logging at debug level to file
    try:
        fl = logging.FileHandler(FULL_LOGFILE)
    except IOError:
        os.makedirs(os.path.dirname(FULL_LOGFILE))
        fl = logging.FileHandler(FULL_LOGFILE)

    # to write logging at specified level to stderr
    pr = logging.StreamHandler()

    # set stderr level
    if __DEBUG__:
        pr.setLevel(15)
    else:
        pr.setLevel(logging.INFO)

    # add handlers to logger
    LOGGER.addHandler(fl)
    LOGGER.addHandler(pr)

    # -------------------------------

    # call main
    sys.exit(main())
