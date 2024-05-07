echo Opening up ArcGIS Pro
 
start /b C:\"Program Files"\ArcGIS\Pro\bin\ArcGISPro.exe
 
echo waiting 25 seconds
timeout 25
 
echo closing ArcGIS Pro
Taskkill /IM ArcGISPro.exe /T /F
 
echo Closing ArcGIS Pro and ending the batch file