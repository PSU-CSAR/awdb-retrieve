import logging
import os

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

## Logging constants

# contains debug info
FULL_LOGFILE = os.path.join(settings.LOG_DIR, "hello_world_LOG.txt")
# records processed OK/Failed only
SUMMARY_LOGFILE = os.path.join(settings.LOG_DIR, "hello_world_SUMMARY.txt")

def main():
    from datetime import datetime
    import shutil
    import arcpy
    from arcpy import env
    from arcpy_extensions import server_admin
    from arcgisscripting import ExecuteError

    start = datetime.now()
    LOGGER.log(15, "\n\n--------------------------------------------------------------\n")
    LOGGER.log(15, "Started at {0}.".format(start))

    #print(sys.path)
	
    servicefoldernames = ['AWDB_ALL', 'AWDB_ACTIVE', 'AWDB_INACTIVE']
    print("Connecting to server admin and stopping all services in {0} folder(s)...".format(servicefoldernames))
    agsconnection = server_admin.AgsAdmin.connectWithoutToken(
            settings.SERVER_ADDRESS,
            settings.SERVER_PORT,
            settings.SERVER_USER,
            settings.SERVER_PASS,
        )
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