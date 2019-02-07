# -*- coding: utf-8 -*- 
import arcpy
import os, sys
from arcgis.gis import GIS

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

# Update the following variables to match:
portal = "http://www.arcgis.com" # Can also reference a local portal

# Set sharing options
shrOrg = False
shrEveryone = True
shrGroups = ""

### End setting variables

def update_feature_services(project_path, sd_fs_name):
    # Local paths to create temporary content
    relPath = sys.path[0]
    sddraft = os.path.join(settings.repo, "temp\WebUpdate.sddraft")
    sd = os.path.join(settings.repo, "temp\WebUpdate.sd")

    # Create a new SDDraft and stage to SD
    print("Creating SD file")
    arcpy.env.overwriteOutput = True
    prj = arcpy.mp.ArcGISProject(project_path)
    mp = prj.listMaps()[0]
    arcpy.mp.CreateWebLayerSDDraft(mp, sddraft, sd_fs_name, "MY_HOSTED_SERVICES", "FEATURE_ACCESS","", True, True)
    arcpy.StageService_server(sddraft, sd)

    print("Connecting to {}".format(portal))
    gis = GIS(portal, settings.AGO_USER, settings.AGO_PASSWORD)

    # Find the SD, update it, publish /w overwrite and set sharing and metadata
    print("Search for original SD on portal...")
    sdItem = gis.content.search("{} AND owner:{}".format(sd_fs_name, settings.AGO_USER), item_type="Service Definition")[0]
    print("Found SD: {}, ID: {} n Uploading and overwriting…".format(sdItem.title, sdItem.id))
    sdItem.update(data=sd)
    print("Overwriting existing feature service...")
    fs = sdItem.publish(overwrite=True)

    if shrOrg or shrEveryone or shrGroups:
      print("Setting sharing options...")
      fs.share(org=shrOrg, everyone=shrEveryone, groups=shrGroups)

    print("Finished updating: {} – ID: {}".format(fs.title, fs.id))

def main():
    print ("Calling update")
    update_feature_services()

if __name__ == '__main__':
  # call main
  sys.exit(main())