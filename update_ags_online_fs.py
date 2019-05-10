# -*- coding: utf-8 -*- 
import arcpy
import os, sys
from arcgis.gis import GIS
import logging
import datetime


# load settings from settings_ags_online.py
# user name, password, project path, and feature service name are in this file
try:
    import settings
except:
    raise Exception(
        "Please copy the settings_template.py file to " +
        "a file named settings.py and edit the values as required."
    )

### Start setting variables

# Set sharing options
shrOrg = False
shrEveryone = True
shrGroups = ""

### End setting variables

def update_feature_services(project_path, sd_fs_name):
    # Get handle to logger
    LOGGER = logging.getLogger(__name__)
    start = datetime.datetime.now()
    LOGGER.info("\n\n--------------------------------------------------------------\n")
    LOGGER.info("update_feature_services started at {0}.".format(start))


    # Local paths to create temporary content
    relPath = sys.path[0]
    sddraft = os.path.join(settings.repo, "temp\WebUpdate.sddraft")
    sd = os.path.join(settings.repo, "temp\WebUpdate.sd")

    # Create a new SDDraft and stage to SD
    LOGGER.info("Creating SD file")
    arcpy.env.overwriteOutput = True
    prj = arcpy.mp.ArcGISProject(project_path)

    mp = None
    map_list = prj.listMaps()
    for a_map in map_list:
        if a_map.name == sd_fs_name:
            mp = a_map
            break
    if mp is not None:
      arcpy.mp.CreateWebLayerSDDraft(mp, sddraft, sd_fs_name, "MY_HOSTED_SERVICES", "FEATURE_ACCESS","", True, True)
      arcpy.StageService_server(sddraft, sd)

      LOGGER.debug("Connecting to {}".format(settings.AGO_PORTAL))
      gis = GIS(settings.AGO_PORTAL, settings.AGO_USER, settings.AGO_PASSWORD)

      # Find the SD, update it, publish /w overwrite and set sharing and metadata
      LOGGER.debug("Search for original SD on portal...")
      sdItem = gis.content.search("{} AND owner:{}".format(sd_fs_name, settings.AGO_USER), item_type="Service Definition")[0]
      LOGGER.debug("Found SD: {}, ID: {} n Uploading and overwriting…".format(sdItem.title, sdItem.id))
      sdItem.update(data=sd)
      LOGGER.info("Overwriting existing feature service...")
      fs = sdItem.publish(overwrite=True)

      if shrOrg or shrEveryone or shrGroups:
        LOGGER.debug("Setting sharing options...")
        fs.share(org=shrOrg, everyone=shrEveryone, groups=shrGroups)

      LOGGER.info("Finished updating: {} – ID: {}".format(fs.title, fs.id))
    else:
      LOGGER.info("Could not find map!")

    end = datetime.datetime.now()
    LOGGER.info("update_feature_services time finished: {0}.".format(end))
    LOGGER.info("Time elapsed: {0}.".format(end-start))

def main():
    print ("Calling update")
    update_feature_services()

if __name__ == '__main__':
  # call main
  sys.exit(main())