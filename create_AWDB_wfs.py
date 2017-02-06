import os
import arcpy
from arcpy import mapping
from arcpy import env

# load settings from settings.py
try:
    import settings
except:
    raise Exception(
        "Please copy the settings_template.py file to " +
        "a file named settings.py and edit the values as required."
    )


ACTIVE_QUERY = "enddate = timestamp '2100-01-01 00:00:00'"
INACTIVE_QUERY = "enddate <> timestamp '2100-01-01 00:00:00'"

ALL = "ALL"
ACTIVE = "ACTIVE"
INACTIVE = "INACTIVE"

CONNECTION_FILE_NAME = "awdb.ags"

mxd_path = os.path.join(settings.repo, "blank_map.mxd")
map_dir = settings.MAP_DIR


# create map dir if not present
if not os.path.isdir(map_dir):
    os.makedirs(map_dir)

###########################################################
### This us useful if one can figure out how to properly
### update the SD draft that can be generated from an mxd.
### Otherwise it is useless and will remain commented out.
## create server connection file
#mapping.CreateGISServerConnectionFile(
#    "PUBLISH_GIS_SERVICES",
#    map_dir,
#    CONNECTION_FILE_NAME,
#    "http://{}:{}/arcgis/admin".format(
#        settings.SERVER_ADDRESS,
#        settings.SERVER_PORT
#    ),
#    "ARCGIS_SERVER",
#    username=settings.SERVER_USER,
#    password=settings.SERVER_PASS,
#)
###########################################################

connection_file = os.path.join(map_dir, CONNECTION_FILE_NAME)

# get the AWDB fcs in the SDE database
env.workspace = os.path.join(
    # this should use a read-only database connection file
    # to prevent any possibility of unintended data manipulation
    settings.SDE_READONLY,
    settings.FDS_SDE_PREFIX + settings.FDS_NAME
)

fcs = arcpy.ListFeatureClasses()

# iterate through the fcs and create map docs, publishing each as a WFS
for fc in fcs:
    # fc name is the whole SDE path, including DB, schema, and FDS names
    # splitting on . and taking last piece gives the actual FC name
    fc_name = fc.split(".")[-1]

    # we want to make three layers for each FC:
    # one with all stations, one with only active stations,
    # and one with only inactive stations
    lyrs = {
        # all stations
        ALL: arcpy.MakeFeatureLayer_management(
            fc,
            "{}_{}".format(fc_name, ALL)
        ),
        # only active stations
        ACTIVE: arcpy.MakeFeatureLayer_management(
            fc,
            "{}_{}".format(fc_name, ACTIVE),
            ACTIVE_QUERY
        ),
        # only inactive stations
        INACTIVE: arcpy.MakeFeatureLayer_management(
            fc,
            "{}_{}".format(fc_name, INACTIVE),
            INACTIVE_QUERY
        ),
    }

    # now we want to make a map for each
    for lyr_name, lyr in lyrs.iteritems():
        # the result stored in lyr is a result object, not a layer object
        # getOutput(0) gets the first (and only) output from the
        # MakeFeatureLayer commands, which happens to be a layer object
        lyr = lyr.getOutput(0)

        # open the blank mxd because we can't create them reasonably
        mxd = mapping.MapDocument(mxd_path)

        # have to get the first (and only) dataframe
        df = mapping.ListDataFrames(mxd)[0]

        # now we can add the layer object we pulled out above
        mapping.AddLayer(df, lyr)

        # let's save the modified mxd to a new file
        outmxd = os.path.join(map_dir, "{}_{}.mxd".format(fc_name, lyr_name))
        print "Writing map doc {}".format(outmxd)
        mxd.saveACopy(outmxd)

        # clean up the mxd object
        del mxd

#########################################################################
### The below would be useful if it made any sense whatsoever as to
### what one needs to do with a sddraft file to setup the sd as
### required for the AWDB services. Without knowing how to do that,
### I've decided it is not worth automating at this time.
### If something changes and someone understands this, just uncomment and
### fix as needed.
#        # output file for sddraft
#        outsddraft = os.path.join(
#            map_dir,
#            "{}_{}.sddraft".format(fc_name, lyr_name)
#        )
#
#        outsd = os.path.join(
#            map_dir,
#            "{}_{}.sd".format(fc_name, lyr_name)
#        )
#
#        # create the sddraft from the mxd previously created
#        sddraft = mapping.CreateMapSDDraft(
#            outmxd,
#            outsddraft,
#            "{}_{}".format(fc_name, lyr_name),
#            "ARCGIS_SERVER",
#            connection_file,
#            folder_name="AWDB_{}".format(lyr_name),
#        )
#
#        # stage and upload the service if the
#        # sddraft analysis did not contain errors
#        if sddraft['errors'] == {}:
#            # Execute StageService
#            #arcpy.StageService_server(outsddraft, outsd)
#            # Execute UploadServiceDefinition
#            #arcpy.UploadServiceDefinition_server(outsd, connection_file)
#            print "no errors"
#        else:
#            # if the sddraft analysis contained errors, display them
#            print sddraft['errors']
