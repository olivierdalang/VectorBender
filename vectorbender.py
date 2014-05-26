# -*- coding: utf-8 -*-
"""
/***************************************************************************
 VectorBender
                                 A QGIS plugin
 Deforms vector to adapt them despite heavy and irregular deformations
                              -------------------
        begin                : 2014-05-21
        copyright            : (C) 2014 by Olivier Dalang
        email                : olivier.dalang@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

# Basic dependencies
import os.path
import sys
import math
from distutils.version import StrictVersion

# More tricky dependencies
dependenciesStatus = 2 # 2: ok, 1: too old, 0: missing
try:
    import matplotlib.tri
    if StrictVersion(matplotlib.__version__) < StrictVersion('1.3.0'):
        dependenciesStatus=1
        QgsMessageLog.logMessage("Matplotlib version too old (%s instead of %s). Some things may not work as expected." % (matplotlib.__version__,'1.3.0'))
except Exception, e:
    QgsMessageLog.logMessage("Matplotlib is missing !")
    dependenciesStatus = 0

# Other classes
from vectorbenderdialog import VectorBenderDialog
from vectorbenderhelp import VectorBenderHelp

class VectorBender:

    def __init__(self, iface):
        self.iface = iface
        self.dlg = VectorBenderDialog(iface,self)

        self.ptsA = []
        self.ptsB = []

        self.delaunay = []
        self.aboutWindow = None

        self.rubberBands = None

    def initGui(self):
        
        self.action = QAction( QIcon(os.path.join(os.path.dirname(__file__),'resources','icon.png')), "Vector Bender", self.iface.mainWindow())
        self.action.triggered.connect(self.showUi)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&Vector Bender", self.action)

        self.helpAction = QAction( QIcon(os.path.join(os.path.dirname(__file__),'resources','about.png')), "Vector Bender Help", self.iface.mainWindow())
        self.helpAction.triggered.connect(self.showHelp)
        self.iface.addPluginToMenu(u"&Vector Bender", self.helpAction)

    def showHelp(self):
        if self.aboutWindow is None:
            self.aboutWindow = VectorBenderHelp()
        self.aboutWindow.show()
        self.aboutWindow.raise_() 

    def unload(self):
        if self.dlg is not None:
            self.dlg.close()
            self.dlg = None

        if self.rubberBands is not None:
            self.rubberBands[0].reset()
            self.rubberBands[1].reset()
            self.rubberBands[2].reset()

        if self.aboutWindow is not None:
            self.aboutWindow.close()
            self.aboutWindow = None

        self.iface.removePluginMenu(u"&Vector Bender", self.action)
        self.iface.removePluginMenu(u"&Vector Bender", self.helpAction)
        self.iface.removeToolBarIcon(self.action)

    def showUi(self):
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.refreshStates()

    def loadDelaunay(self, pairsLayer, buff=0):

        self.ptsA = []
        self.ptsB = []
        ptsForHull = []

        features = pairsLayer.getFeatures() if not self.dlg.restrictBox_pairsLayer.isChecked() else pairsLayer.selectedFeatures()

        for feature in features:
            geom = feature.geometry().asPolyline()
            self.ptsA.append( QgsPoint(geom[0].x(),geom[0].y()) )
            self.ptsB.append( QgsPoint(geom[-1].x(),geom[-1].y()) )

        #we add a ring outside the hull so that the transformation smoothly stops
        self.hull = QgsGeometry.fromMultiPoint( self.ptsA ).convexHull()

        if buff>0:
            self.expandedHull = self.hull.buffer(buff, 3)
            for p in self.expandedHull.asPolygon()[0]:
                self.ptsA.append( p )
                self.ptsB.append( p )
        else:
            self.expandedHull = self.hull

        self.delaunay = matplotlib.tri.Triangulation([p.x() for p in self.ptsA],[p.y() for p in self.ptsA])

    def determineTransformationType(self):

        pairsLayer = self.dlg.pairsLayer()

        if pairsLayer is None:
            return 0

        featuresCount = len(pairsLayer.selectedFeaturesIds()) if self.dlg.restrictBox_pairsLayer.isChecked() else len(pairsLayer.allFeatureIds())
        
        if featuresCount == 1:
            return 1
        elif featuresCount == 2:
            return 2
        elif featuresCount >= 3:
            return 3

        return 0

    

    def hidePreview(self):
        if self.rubberBands is not None:
            self.rubberBands[0].reset(QGis.Polygon)
            self.rubberBands[1].reset(QGis.Polygon)
            self.rubberBands[2].reset(QGis.Polygon)
            self.rubberBands = None

    def showPreview(self):

        self.rubberBands = (QgsRubberBand(self.iface.mapCanvas(), QGis.Polygon),QgsRubberBand(self.iface.mapCanvas(), QGis.Polygon),QgsRubberBand(self.iface.mapCanvas(), QGis.Polygon))

        self.rubberBands[0].reset(QGis.Polygon)
        self.rubberBands[1].reset(QGis.Polygon)
        self.rubberBands[2].reset(QGis.Polygon)

        pairsLayer = self.dlg.pairsLayer()
        if pairsLayer is None:
            self.dlg.statusLabel.setText( "You must select a vector-line layer which defines the points pairs !" )
            return

        self.loadDelaunay(pairsLayer, self.dlg.bufferValue())

        self.rubberBands[0].setColor(QColor(0,125,255))
        self.rubberBands[1].setColor(QColor(255,125,0))
        self.rubberBands[2].setColor(QColor(0,125,0,50))

        self.rubberBands[0].setBrushStyle(Qt.Dense6Pattern)
        self.rubberBands[1].setBrushStyle(Qt.Dense6Pattern)
        self.rubberBands[2].setBrushStyle(Qt.NoBrush)

        self.rubberBands[0].setWidth(3)
        self.rubberBands[1].setWidth(3)
        self.rubberBands[2].setWidth(1)
      
        #draw the expanded hull
        for p in self.expandedHull.asPolygon()[0]:
            self.rubberBands[0].addPoint( p, True, 0  )
        for p in self.expandedHull.asPolygon()[0][0:1]:
            #we readd the first point since it's not possible to make true rings with rubberbands
            self.rubberBands[0].addPoint( p, True, 0  )

        #draw the hull
        for p in self.hull.asPolygon()[0]:
            self.rubberBands[0].addPoint( p, True, 0  ) #inner ring of rubberband 1
            self.rubberBands[1].addPoint( p, True, 0  )
        for p in self.hull.asPolygon()[0][0:1]:
            #we readd the first point since it's not possible to make true rings with rubberbands
            self.rubberBands[0].addPoint( p, True, 0  )

        #draw the triangles
        for i,tri in enumerate(self.delaunay.triangles):
            self.rubberBands[2].addPoint( self.ptsA[tri[0]], False, i  )
            self.rubberBands[2].addPoint( self.ptsA[tri[1]], False, i  )
            self.rubberBands[2].addPoint( self.ptsA[tri[2]], True, i  ) #TODO : this refreshes the rubber band on each triangle, it should be updated only once after this loop       

    def run(self):

        self.dlg.progressBar.setValue( 0 )

        toBendLayer = self.dlg.toBendLayer()
        pairsLayer = self.dlg.pairsLayer()



        # Loading the delaunay
        self.dlg.displayMsg( "Loading delaunay mesh (%i points) ..." % len(self.ptsA) )
        QCoreApplication.processEvents()
        self.loadDelaunay(pairsLayer, self.dlg.bufferValue())
        self.trifinder = self.delaunay.get_trifinder()



        # Starting to iterate
        features = toBendLayer.getFeatures() if not self.dlg.restrictBox_toBendLayer.isChecked() else toBendLayer.selectedFeatures()

        count = toBendLayer.featureCount() if not self.dlg.restrictBox_toBendLayer.isChecked() else len(features)
        self.dlg.displayMsg( "Starting to iterate through %i features..." % count )
        QCoreApplication.processEvents()

        toBendLayer.beginEditCommand("Feature bending")
        for i,feature in enumerate(features):

            self.dlg.progressBar.setValue( int(100.0*float(i)/float(count)) )
            self.dlg.displayMsg( "Aligning features %i out of %i..."  % (i, count))
            QCoreApplication.processEvents()

            geom = feature.geometry()

            #TODO : this cood be much simpler if we could iterate through to vertices and use QgsGeometry.moveVertex(x,y,index), but QgsGeometry.vertexAt(index) doesn't tell wether the index exists, so there's no clean way to iterate...

            if geom.type() == QGis.Point:

                if not geom.isMultipart():
                    # SINGLE PART POINT
                    p = goem.asPoint()
                    newGeom = QgsGeometry.fromPoint( self.mapPoint( p ) )

                else:
                    # MULTI PART POINT
                    listA = geom.asMultiPoint()
                    newListA = []
                    for p in listA:
                        newListA.append( self.mapPoint(p) )
                    newGeom = QgsGeometry.fromMultiPoint( newListA )

            elif geom.type() == QGis.Line:

                if not geom.isMultipart():
                    # SINGLE PART LINESTRING
                    listA = geom.asPolyline()
                    newListA = []
                    for p in listA:
                        newListA.append( self.mapPoint(p) )
                    newGeom = QgsGeometry.fromPolyline( newListA )

                else:
                    # MULTI PART LINESTRING
                    listA = geom.asMultiPolyline()
                    newListA = []
                    for listB in listA:
                        newListB = []
                        for p in listB:
                            newListB.append( self.mapPoint(p) )
                        newListA.append( newListB )
                    newGeom = QgsGeometry.fromMultiPolyline( newListA )

            elif geom.type() == QGis.Polygon:

                if not geom.isMultipart():
                    # SINGLE PART POLYGON
                    listA = geom.asPolygon()
                    newListA = []
                    for listB in listA:
                        newListB = []
                        for p in listB:
                            newListB.append( self.mapPoint(p) )
                        newListA.append( newListB )
                    newGeom = QgsGeometry.fromPolygon( newListA )

                else:
                    # MULTI PART POLYGON
                    listA = geom.asMultiPolygon()
                    newListA = []
                    for listB in listA:
                        newListB = []
                        for listC in listB:
                            newListC = []
                            for p in listC:
                                newListC.append( self.mapPoint(p) )
                            newListB.append( newListC )
                        newListA.append( newListB )
                    newGeom = QgsGeometry.fromMultiPolygon( newListA )

            else:
                # FALLBACK, JUST IN CASE ;)
                newGeom = geom

            toBendLayer.changeGeometry( feature.id(), newGeom )

        toBendLayer.endEditCommand()


        #Transforming pairs to pins
        features = pairsLayer.getFeatures() if not self.dlg.restrictBox_pairsLayer.isChecked() else pairsLayer.selectedFeatures()

        count = pairsLayer.featureCount() if not self.dlg.restrictBox_pairsLayer.isChecked() else len(features)
        self.dlg.progressBar.setValue( 0 )
        self.dlg.displayMsg( "Starting to transform %i pairs to pins..." % count )
        QCoreApplication.processEvents()

        pairsLayer.beginEditCommand("Transforming pairs to pins")
        for i,feature in enumerate(features):

            self.dlg.progressBar.setValue( int(100.0*float(i)/float(count)) )
            self.dlg.displayMsg( "Transforming pair to pin %i out of %i..."  % (i, count))
            QCoreApplication.processEvents()

            geom = feature.geometry().asPolyline()

            newGeom = QgsGeometry.fromPolyline( [geom[-1],geom[-1]] )
            pairsLayer.changeGeometry( feature.id(), newGeom )

        pairsLayer.endEditCommand()

        self.dlg.displayMsg( "Finished !" )
        self.dlg.progressBar.setValue( 100 )
        pairsLayer.repaintRequested.emit()

    def mapPoint(self, p):

        tri = self.trifinder( p[0], p[1] )

        if tri==-1:
            # No triangle found : don't change the point
            return QgsPoint(p[0], p[1])
        else:
            # Triangle found : adapt it from the old mesh to the new mesh
            a1 = self.ptsA[self.delaunay.triangles[tri][0]]
            a2 = self.ptsA[self.delaunay.triangles[tri][1]]
            a3 = self.ptsA[self.delaunay.triangles[tri][2]]

            b1 = self.ptsB[self.delaunay.triangles[tri][0]]
            b2 = self.ptsB[self.delaunay.triangles[tri][1]]
            b3 = self.ptsB[self.delaunay.triangles[tri][2]]

            mappedP = mapPointFromTriangleAtoTriangleB(p, a1, a2, a3, b1, b2, b3)

            return QgsPoint(mappedP[0], mappedP[1])



def mapPointFromTriangleAtoTriangleB(p, a1,a2,a3, b1,b2,b3 ):
    cT = fromCartesianToTriangular( p, a1, a2, a3  )
    cC = fromTriangularToCartesian( cT, b1, b2, b3  )
    return cC

def fromCartesianToTriangular(p, t1, t2, t3):
    """ Returns triangular coordinates (l1, l2, l3) for a given point in a given triangle """
    """ p is a duplet for cartesian coordinates coordinates """
    x,y = p
    x1,y1 = t1.x(),t1.y()
    x2,y2 = t2.x(),t2.y()
    x3,y3 = t3.x(),t3.y()
    l1 = ((y2-y3)*(x-x3)+(x3-x2)*(y-y3))/((y2-y3)*(x1-x3)+(x3-x2)*(y1-y3))
    l2 = ((y3-y1)*(x-x3)+(x1-x3)*(y-y3))/((y2-y3)*(x1-x3)+(x3-x2)*(y1-y3))
    l3 = 1-l1-l2
    return (l1,l2,l3)

def fromTriangularToCartesian(l,t1,t2,t3):
    """ l is a triplet for barycentric coordinates """
    x = l[0]*t1.x()+l[1]*t2.x()+l[2]*t3.x()
    y = l[0]*t1.y()+l[1]*t2.y()+l[2]*t3.y()
    return (x,y)