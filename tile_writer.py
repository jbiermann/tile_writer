# tile_writer.py
# Version 0.3
# original script copyright 2015 Alexander Hajnal
# modified to run qwith QGIS 3 (tested with 3.8) and Python 3 by JB

# Generates slippy map tiles from within QGIS
# http://alephnull.net/software/gis/tile_writer.shtml

# See the README.md file for usage instructions

# ==============================================================================

# Start user-editable settings

# Minimum zoom level
start_z = 10

# Maximum zoom level
end_z = 15

# How many map tiles to place in each regional tile
# (the actual number of map tiles per regional tile is step * step)
# Higher number speed up rendering (assuming enough RAM is available).
# Lower numbers decrease memory usage but increase rendering time.
step = 16

# Number of extra map tiles to render along each edge of a regional tile
# By rendering extra, unused border tiles we can avoid shifting labels, 
# truncated images, and line-drawing inconsistancies at tile boundaries.
# If this value is set to 0 you will encounter rendering issues at tile 
# boundaries.
border = 2

# Directory to write the regional images and level subdirectories to
output_path = '/tmp'

# Path of shapefile defining the area of interest
# The extent of the shapefile is used to limit rendering to a particular area.
# Note that no clipping is done so at lower zoom levels tiles from outside the 
# area of interest will be generated.
area_of_interest = '/path/to/area_of_interest.shp'

# Filename convention to follow
#tile_format = 'google'
tile_format = 'tms'

# if tile writer fails to load globalmercator, uncomment the next line and 
# put in the full path to the directory where you have extracted tile writer
# directory (containing tile_writer.py and globalmercator.py)
#sys.path.append("/path/to/tilewriterdir")

# End user-editable settings

# ==============================================================================

from PyQt5.QtCore import *
from PyQt5.QtGui import *

from qgis.core import *
import qgis.utils
from qgis.utils import iface
from qgis.gui import *

import sys
import os
import os.path
import shutil
import math

sys.path.append("/path/to/tilewriterdir ")
from globalmercator import GlobalMercator

def delay( millisecondsToWait ):
    dieTime = QTime().currentTime().addMSecs( millisecondsToWait )
    while ( QTime.currentTime() < dieTime ):
        QCoreApplication.processEvents( QEventLoop().AllEvents, 100 )

borderLayer = QgsVectorLayer(area_of_interest, 'border', 'ogr')
borderRect = borderLayer.extent()
borderCRS = borderLayer.crs()

#mapRenderer = iface.mapCanvas().mapRenderer()
activeLayers = set()

mapRect = QgsCoordinateTransform(borderCRS, QgsCoordinateReferenceSystem('EPSG:4326'), QgsProject.instance()).transform(borderRect) # WGS84

xStart = mapRect.xMinimum()
xEnd = mapRect.xMaximum()

yStart = mapRect.yMinimum()
yEnd = mapRect.yMaximum()

width = mapRect.width()
height = mapRect.height()

print ("xStart:", xStart)
print ("xEnd:  ", xEnd)
print
print ("yStart:", yStart)
print ("yEnd:  ", yEnd)
print
print ("width: ", width)
print ("height:", height)

print

for z in range(start_z, end_z+1, 1):
    print
    print ("zoom:%i  step:%i  border_size:%i" % (z, step, border))

    gm = GlobalMercator()

    lon = xStart
    lat = yStart
    mx_min, my_min = gm.LatLonToMeters(lat, lon)
    tx_min, ty_min = gm.MetersToTile(mx_min, my_min, z)
    print ("Min: %i, %i @ %i" % ( tx_min, ty_min, z ))

    lon = xEnd
    lat = yEnd
    mx_max, my_max = gm.LatLonToMeters(lat, lon)
    tx_max, ty_max = gm.MetersToTile(mx_max, my_max, z)
    print ("Max: %i, %i @ %i" % ( tx_max, ty_max, z ))

    dirPath = "%s/%i" % (output_path,z)
    QDir().mkpath(dirPath)

    width = 256 * ( step + border + border )
    height = 256 * ( step + border + border )
    
    print
    print ("While generating the regional tiles, QGIS may appear to have locked up.")
    print ("This is not the case.  Please be patient.")
    print
    print ("Generating regional tiles... (%i x %i tiles -> %i x %i regional tiles)" % (tx_max-tx_min+1, ty_max-ty_min+1, math.ceil((tx_max-tx_min+1.0)/step), math.ceil((ty_max-ty_min+1.0)/step)))
    total_regional_tiles = 0
    for x in range(tx_min, tx_max+1, step):
        for y in range(ty_min, ty_max+1, step):
            total_regional_tiles += 1
            imagePath = "%s/%i_%i_%i_s%i_b%i.png" % (output_path,z,x,y,step,border)
            lat_min, lon_min, ignore, ignore = gm.TileLatLonBounds(x-border,y-border,z)
            ignore, ignore, lat_max, lon_max = gm.TileLatLonBounds(x+step+border-1,y+step+border-1,z)
            lat_min, lon_min = gm.LatLonToMeters(lat_min, lon_min)
            lat_max, lon_max = gm.LatLonToMeters(lat_max, lon_max)
            if os.path.isfile(imagePath):
                # Regional tile exists, so skip it
                sys.stdout.write("o")
            else:
                image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
                
                settings = QgsMapSettings()
                settings.setOutputDpi(95.0)
                settings.setOutputImageFormat(QImage.Format_ARGB32_Premultiplied)
                settings.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
                settings.setOutputSize(QSize(width, height))

                print ("Setting active layers")
                layers = QgsProject.instance().mapLayers()
                root = QgsProject.instance().layerTreeRoot()
                
                for l in layers.values():
                    node = root.findLayer(l.id())
                    if (node.isItemVisibilityCheckedRecursive()):
                        print (l.id())
                        activeLayers.add(l)
                print ("List of active layers")
                settings.setLayers(activeLayers)
              
                settings.setFlag(QgsMapSettings.DrawLabeling, True)
                settings.setBackgroundColor(QColor(127, 127, 127, 0))
                
                tileRect = QgsRectangle(lat_min, lon_min, lat_max, lon_max)
                settings.setExtent(tileRect)
                
                job = QgsMapRendererSequentialJob(settings)
                job.start()
                job.waitForFinished()
                delay(10)
                image = job.renderedImage()
                image.save(imagePath, "PNG")
                sys.stdout.write("*")
        sys.stdout.write("\n")
    
    print
    
    print ("Splitting regional tiles into TMS tiles...")
    h = 256 * (border + border + step)
    current_regional_tile = 1
    for x in range(tx_min, tx_max+1, step):
        for y in range(ty_min, ty_max+1, step):
            srcPath = "%s/%i_%i_%i_s%i_b%i.png" % (output_path,z,x,y,step,border)
            if os.path.isfile(srcPath):
                print
                print ("Processing regional tile %i of %i: %s" % (current_regional_tile, total_regional_tiles, srcPath ))
                current_regional_tile += 1
                srcImage = QImage()
                srcImage.load(srcPath)
                px = 256 * border
                for tile_x in range(x, x+step, 1):
                    iDirPath = "%s/%i/%i" % (output_path,z,tile_x)
                    QDir().mkpath(iDirPath)
                    py = 256 * ( border + 1 )
                    for tile_y in range(y, y+step, 1):
                        if tile_format == 'tms':
                            tile_y_tms = (1<<z) - tile_y - 1
                            dstPath = "%s/%i/%i/%i.png" % (output_path,z,tile_x,tile_y_tms)
                        else:
                            dstPath = "%s/%i/%i/%i.png" % (output_path,z,tile_x,tile_y)
                        if os.path.isfile(dstPath):
                            # Tile exists, so skip it
                            sys.stdout.write("o")
                        else:
                            dstImage = srcImage.copy(px,h-py,256,256)
                            dstImage.save(dstPath, "PNG")
                            sys.stdout.write("*")
                        py += 256
                    sys.stdout.write("\n")
                    px += 256

print
print ("All done!")



# Warranty
# ------------------------------------------------------------------------------
# I make no warranty or representation, either express or implied, with respect 
# the behavior of this script, its quality, performance, accuracy, merchantability, 
# or fitness for a particular purpose. This script is provided 'as is', and 
# you, by making use thereof, are assuming the entire risk.  That said, 
# I hope you this script useful.  Have fun!
