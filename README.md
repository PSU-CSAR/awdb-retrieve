awdb-retrieve
=============

Script to download stations in the NRCS Air Water Database
and update feature services running on a local SDE database.


Dependencies
------------

This project has three dependencies outside the python standard library:

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

    pip install -r requirements.txt

If pip is unavailable, e.g., when using the ArcGIS-installed python,
download each of these packages and run the setup.py script using the
python to which installation of these packages is desired.

If not using the the ArcGIS python install (as is recommended), you
will need to create a .pth file to link your python with the arcpy libs.

Updates for Python 3/ArcGIS Pro
------------------------
[wiki article](https://github.com/PSU-CSAR/awdb-retrieve/wiki/Publishing-AWDB-data-to-ArcGIS-Online-with-ArcGIS-Pro-API)

Brief Installation Guide
------------------------

Much of the installtion process has not been automated in any way.
Sorry for the inconvenince. Due to the number of steps, the following
instructions have been kept rather concise. You can find additional
notes in the sections below.

1. Clone the git repo to your desired location

2. Setup the DB in ArcCatalog/PGAdmin.
    
    - Create the DB in Catalog using the "Create Enterprise Geodatabase" tool
        - Authorization file: C:\Program Files (x86)\ESRI\License10.3\sysgen\keycodes
        - Database name awdb_prod
        - Tablespace is `gis_data`, assuming PG is setup right
        - I got error "You must copy the latest ST_GEOMETRY and
          dependent libraries to the PostgreSQL software location."
            - Fix by copying `C:\Program Files (x86)\ArcGIS\Desktop10.3\DatabaseSupport\PostgreSQL\9.3\Windows64\<both files>`
              to `C:\Prorgram Files\PostgreSQL\9.3\lib`
    - Need to add awdb and awdb_readonly users in PGAdmin
      - See https://sites.google.com/site/nwccspatialservices/developers-blog/creatingusersforansdedatabaseinpostgresql
        for some tips. Note that a data owner role is required for the retrieve script,
        which is a user that will have read/write/create privileges.
        For the maps, a read-only role is required.
    - Need to create the awdb schema in the awdb-prod DB
      so the awdb user can create data in that DB

3. Create the awdb owner DB connection in arc and set the path
   in the settings.py file (default is simply the repo directory).

4. Set any other settings that are missing or that deviate from the defaults.

5. Use the following command to setup a new virtual env:

    ```
    > conda create -n awdb_retrieve python
    ```
    
6. Install the dependencies:

    ```
    > activate awdb_retrieve
    > conda install numpy
    > pip install https://github.com/jkeifer/arcpy-extensions/tarball/master
    > pip install suds-jurko==0.6
    ```

7. Copy the Desktop10.`<X>`.pth file to the env site-packages:

    - The file is at `C:\Python27\ArcGIS10.<X>\Lib\site-packages\Desktop10.<X>.pth`
      where `<X>` is the minor ArcGIS version.
    - Copy the file to `C:\Anaconda_x86\envs\awdb_retrieve\Lib\site-packages`.

8. Run the script the first time (from the repo directory):

    ```
    > python get_AWDB_stations.py
    ```

9. Run the mxd generator (yes, the name is misleading and should be changed):

    ```
    > python create_AWDB_wfs.py
    ```

10. Publish all the webservices. The changes required to publish
    a service with the correct settings are detailed as follows:

    - Parameters
        - Maximum number of records returned by the server: 5000
    - Capabilities
        - Disable KML
        - Enable Feature Access and WFS
    -  Feature Access
        - Operations allowed: only Query
        - Do not allow geometry updates
        - Apply default Z-value: 0
    - WFS
        - Uncheck "Enable maximum number of features returned by service"
    - Item Descritption
        - Summary: 
          - ACTIVE: `<network_code>` sites from the NRCS AWDB with ACTIVE status.
          - ALL: `<network_code>` sites from the NRCS AWDB.
          - INACTIVE: `<network_code>` sites from the NRCS AWDB with INACTIVE status.
        - Tags: `<network_code>`, NRCS, AWDB
        - Descritption: same as summary

11. Run the script again just to make sure it can update the data without issue.

12. Setup a reoccurring task in the Task Scheduler to run the script on a weekly basis.

Support
-------

Please report all issues to the [issue tracker for this project](https://github.com/PSU-CSAR/awdb-retrieve/issues).


Some notes
----------

Reviewing the script, it seems only necessary to setup the SDE DB,
the users, and the database connection files before running the retrieve.
The script should create a FDS if specified, and should create the FCs as well.
The lack of any existing WFSs shouldn't be an issue--
the script will stop all of them, which is none, then copy the FCs to SDE.
(Note that this wasn't true, and I had to fix the script so this was the behavior).

Once the script runs the first time, the maps need to be created
and shared as WFSs. For each AWDB network, three maps should be created:
one with all stations, one with only active stations,
and one with only inactive stations.
Filtering the stations is simply a matter of a definition query, as follows:

    active: enddate == timestamp '2100-01-01 00:00:00'
    inactive: enddate <> timestamp '2100-01-01 00:00:00'
    
A script, create_AWDB_wfs.py has been created to automate these tasks.
Just run it once after the initial AWDB retrieve creates the FCs.

NOTE: automating the publishing of the maps to WFSs turned
out to be too difficult vs not. I decided to manually publish all
the services from each of the generated mxds. I also ran into an
issue with the first service published where the data source was
not registered with the server. I had to register the AWDB database
via the readonly connection file to make Arc happy.


And more notes (openssl problems)
---------------------------------

I ran into a terribly confusing and difficult problem,
wherein I would get the following error when running the script:

    urllib2.URLError: <urlopen error: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:661)>

It would error out when going to
http://www.wcc.nrcs.usda.gov/awdbWebService/services?WSDL
to get the SOAP definition for AWDB.

I tried upgrading python, running older versions of python,
changing the _ssl lib, installing updates to OpenSSL...you name it.
I tried using cURL to the url and that had the same problem,
at least on the Basins and Atlas servers.
But web browsers were fine, and I was able to get to the url.

Notably, the url is not https. So at first I couldn't figure out
why SSL was even coming into play. However, I realize that this
url had a redirect to https, and then that https url had a redirect
to a completely different url: https://wcc.sc.egov.usda.gov/awdbWebService/services?WSDL.
I have updated the settings template with this new url to avoid the
redirects.

So this is the reason for SSL. But everything worked a week ago. What happened?
I am still not certain, but my guess is these redirects happened this week.
Due to the newness of the CA they used to sign the TLS certs, Basins didn't
have a copy of them to sign the site's certs against. I think.

I still don't know what the "right" way to resolve this is, as I was able to
get Atlas to work, seemingly with the same libs in place. But cURL didn't work
there, on Basins, or my Windows VM (it did work on MacOS). So I followed the
instructions to install cURL hoping that I could update it, get it to work,
and get some insight into the problem. Through this process I realized that
the cURL installed on the machines was from the OSGeo4W install. And I saw that
the C:\OSGeo4W\bin folder had curl.exe but no curl-ca-bundle.crt, which is what
curl looks for to get its CAs. So I downloaded the most recent one from the curl
website: https://curl.haxx.se/docs/caextract.html. Then I copied this file into
the bin directory, renaming it curl-ca-bundle.crt. Voila! cURL began working.

Interestingly, this also fixed the python problem. I guess having this CA bundle
on the path is enough to allow the python SSL install to use it. Thank goodness.
