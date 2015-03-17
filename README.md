awdb-retrieve
=============

Script to download stations in the NRCS Air Water Database
and update feature services running on a local SDE database.


Installation
------------

The script does not need to be installed. It can simply
be run by double-clicking or calling from the command
line as an argument of python. However, it does have three
dependencies outside the python standard library:

- arcpy: assumed to be available from the python installation
  with which the user executes the script

- [suds-jurko](https://bitbucket.org/jurko/suds):
  suds is a SOAP web service client for python, and
  suds-jurko is a maintained fork of the project. This script was
  developed with version 0.6.

- [arcpy-extensions](https://github.com/jkeifer/arcpy-extensions):
  arcpy-extensions is a collection of helper functions and classes
  to make using arcpy easier. It is not currently on pypi but can
  be installed directly from GitHub. This script was developed with
  version 0.0.1; the project is tagged v0.0.1 to maintain this state.

To install suds-jurko and arcpy-extensions with pip available, simply:

    pip install requirements.txt

If pip is unavailable, e.g., when using the ArcGIS-installed python,
download each of these packages and run the setup.py script using the
python to which installation of these packages is desired.


Support
-------

Please report all issues to the [issue tracker for this project](https://github.com/PSU-CSAR/awdb-retrieve/issues).
