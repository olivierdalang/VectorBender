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
try:
    import scipy.spatial
    if StrictVersion(scipy.__version__) < StrictVersion('0.14.0'):
        dependenciesStatus=1
        QgsMessageLog.logMessage("Scipy version too old (%s instead of %s). Some things may not work as expected." % (scipy.__version__,'0.14.0'))
except Exception, e:
    QgsMessageLog.logMessage("Scipy is missing !")
    dependenciesStatus = 0

# Other classes
from vectorbenderdialog import VectorBenderDialog
from vectorbenderhelp import VectorBenderHelp

class VectorBender:

    def __init__(self, iface):
        self.iface = iface
        self.dlg = VectorBenderDialog(iface,self)

        self.x_a = []
        self.y_a = []
        self.x_b = []
        self.y_b = []

        self.delaunay = []
        self.aboutWindow = None

        self.rubberBands = None

    def initGui(self):
        
        self.action = QAction( QIcon(os.path.join(os.path.dirname(__file__),'resources','icon.png')), "Vector Bender", self.iface.mainWindow())
        self.action.triggered.connect(self.showUi)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&Vector Bender", self.action)

        if dependenciesStatus == 0:
            self.action.setEnabled(False)
            self.action.setText("Vector Bender (unmet dependencies)")

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

    def loadDelaunay(self, pairsLayer, buff=0):

        self.x_a = []
        self.y_a = []
        self.x_b = []
        self.y_b = []
        ptsForHull = []
        for feature in pairsLayer.getFeatures():
            geom = feature.geometry().asPolyline()
            self.x_a.append(geom[0].x())
            self.y_a.append(geom[0].y())
            self.x_b.append(geom[-1].x())
            self.y_b.append(geom[-1].y())
            ptsForHull.append( (geom[0].x(), geom[0].y()) )


        #we add a ring outside the hull so that the transformation smoothly stops
        hullVrt = scipy.spatial.ConvexHull(ptsForHull).vertices
        self.hull = []
        for i in hullVrt:
            self.hull.append( ptsForHull[i] )

        if buff>0:
            self.expandedHull = expandPoly(self.hull,buff)
            for p in self.expandedHull:
                self.x_a.append(p[0])
                self.y_a.append(p[1])
                self.x_b.append(p[0])
                self.y_b.append(p[1])
        else:
            self.expandedHull = self.hull   

        self.delaunay = matplotlib.tri.Triangulation(self.x_a,self.y_a)

    def togglePreview(self):

        if self.rubberBands is not None:
            self.rubberBands[0].reset(QGis.Polygon)
            self.rubberBands[1].reset(QGis.Polygon)
            self.rubberBands[2].reset(QGis.Polygon)
            self.rubberBands = None
        else:        
            self.rubberBands = (QgsRubberBand(self.iface.mapCanvas(), QGis.Polygon),QgsRubberBand(self.iface.mapCanvas(), QGis.Polygon),QgsRubberBand(self.iface.mapCanvas(), QGis.Polygon))
            self.updatePreview()

    def updatePreview(self):
        if self.rubberBands is not None:
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
            for p in self.expandedHull:
                self.rubberBands[0].addPoint( QgsPoint(p[0],p[1]), True, 0  )
            for p in self.expandedHull[0:1]:
                #we readd the first point since it's not possible to make true rings with rubberbands
                self.rubberBands[0].addPoint( QgsPoint(p[0],p[1]), True, 0  )

            #draw the hull
            for p in self.hull:
                self.rubberBands[0].addPoint( QgsPoint(p[0],p[1]), True, 0  ) #inner ring of rubberband 1
                self.rubberBands[1].addPoint( QgsPoint(p[0],p[1]), True, 0  )
            for p in self.hull[0:1]:
                #we readd the first point since it's not possible to make true rings with rubberbands
                self.rubberBands[0].addPoint( QgsPoint(p[0],p[1]), True, 0  )

            #draw the triangles
            for i,tri in enumerate(self.delaunay.triangles):
                self.rubberBands[2].addPoint( QgsPoint(self.x_a[tri[0]],self.y_a[tri[0]]), False, i  )
                self.rubberBands[2].addPoint( QgsPoint(self.x_a[tri[1]],self.y_a[tri[1]]), False, i  )
                self.rubberBands[2].addPoint( QgsPoint(self.x_a[tri[2]],self.y_a[tri[2]]), True, i  ) #TODO : this refreshes the rubber band on each triangle, it should be updated only once after this loop
                

    def run(self):

        self.dlg.progressBar.setValue( 0 )

        toBendLayer = self.dlg.layerToBend()
        pairsLayer = self.dlg.pairsLayer()

        # Checkin requirements
        if toBendLayer is None:
            self.dlg.displayMsg( "You must select a vector layer to bend !", True )
            return
        if pairsLayer is None:
            self.dlg.displayMsg( "You must select a vector-line layer which defines the points pairs !", True )
            return
        if pairsLayer is toBendLayer:
            self.dlg.displayMsg( "The layer to bend must be different from the pairs layer !", True )
            return            
        if not toBendLayer.isEditable():
            self.dlg.displayMsg( "The layer to bend must be in edit mode !", True )
            return
        if not toBendLayer.isEditable():
            self.dlg.displayMsg( "The layer to bend must be in edit mode !", True )
            return


        # Loading the delaunay
        self.dlg.displayMsg( "Loading delaunay mesh (%i points) ..." % len(self.x_a) )
        QCoreApplication.processEvents()
        self.loadDelaunay(pairsLayer, self.dlg.bufferValue())
        self.trifinder = self.delaunay.get_trifinder()



        # Starting to iterate
        count = toBendLayer.featureCount()
        self.dlg.displayMsg( "Starting to iterate through %i features..." % count )
        QCoreApplication.processEvents()

        toBendLayer.beginEditCommand("Feature bending")

        for i,feature in enumerate(toBendLayer.getFeatures()):

            self.dlg.progressBar.setValue( int(100.0*float(i)/float(count)) )
            self.dlg.displayMsg( "Aligning features %i out of %i..."  % (i, count))
            QCoreApplication.processEvents()

            geom = feature.geometry()

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

        self.dlg.displayMsg( "Finished !" )
        self.dlg.progressBar.setValue( 100 )
        toBendLayer.repaintRequested.emit()

    def mapPoint(self, p):

        tri = self.trifinder( p[0], p[1] )

        if tri==-1:
            # No triangle found : don't change the point
            return QgsPoint(p[0], p[1])
        else:
            # Triangle found : adapt it from the old mesh to the new mesh
            a1 = (self.x_a[self.delaunay.triangles[tri][0]], self.y_a[self.delaunay.triangles[tri][0]])
            a2 = (self.x_a[self.delaunay.triangles[tri][1]], self.y_a[self.delaunay.triangles[tri][1]])
            a3 = (self.x_a[self.delaunay.triangles[tri][2]], self.y_a[self.delaunay.triangles[tri][2]])

            b1 = (self.x_b[self.delaunay.triangles[tri][0]], self.y_b[self.delaunay.triangles[tri][0]])
            b2 = (self.x_b[self.delaunay.triangles[tri][1]], self.y_b[self.delaunay.triangles[tri][1]])
            b3 = (self.x_b[self.delaunay.triangles[tri][2]], self.y_b[self.delaunay.triangles[tri][2]])

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
    x1,y1 = t1
    x2,y2 = t2
    x3,y3 = t3
    l1 = ((y2-y3)*(x-x3)+(x3-x2)*(y-y3))/((y2-y3)*(x1-x3)+(x3-x2)*(y1-y3))
    l2 = ((y3-y1)*(x-x3)+(x1-x3)*(y-y3))/((y2-y3)*(x1-x3)+(x3-x2)*(y1-y3))
    l3 = 1-l1-l2
    return (l1,l2,l3)

def fromTriangularToCartesian(l,t1,t2,t3):
    """ l is a triplet for barycentric coordinates """
    x = l[0]*t1[0]+l[1]*t2[0]+l[2]*t3[0]
    y = l[0]*t1[1]+l[1]*t2[1]+l[2]*t3[1]
    return (x,y)

def vecUnit(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1])
    return ( v[0] / l, v[1] / l )

def vecMul(v, s):
    return ( v[0] * s, v[1] * s )

def vecDot(v1, v2):
    return v1[0] * v2[0] + v1[1] * v2[1]

def vecRot90CW(v):
    return ( v[1], -v[0] )

def vecRot90CCW(v):
    return ( -v[1], v[0] )

def intersect(line1, line2):
    a1 = line1[1][0] - line1[0][0]
    b1 = line2[0][0] - line2[1][0]
    c1 = line2[0][0] - line1[0][0]

    a2 = line1[1][1] - line1[0][1]
    b2 = line2[0][1] - line2[1][1]
    c2 = line2[0][1] - line1[0][1]

    t = (b1*c2 - b2*c1) / (a2*b1 - a1*b2)

    return (
        line1[0][0] + t * (line1[1][0] - line1[0][0]),
        line1[0][1] + t * (line1[1][1] - line1[0][1])
    )

def expandPoly(p, distance):
    expanded = [];

    for i in range(0,len(p)):

        # get this point (pt1), the point before it
        # (pt0) and the point that follows it (pt2)
        pt0 = p[ (i-1) if (i>0) else (len(p)-1) ]
        pt1 = p[i]
        pt2 = p[ (i+1) if (i<len(p)-1) else  0]

        # find the line vectors of the lines going
        # into the current point
        v01 = ( pt1[0] - pt0[0], pt1[1] - pt0[1] )
        v12 = ( pt2[0] - pt1[0], pt2[1] - pt1[1] )

        # find the normals of the two lines, multiplied
        # to the distance that polygon should inflate
        d01 = vecMul(vecUnit(vecRot90CW(v01)), distance)
        d12 = vecMul(vecUnit(vecRot90CW(v12)), distance)

        # use the normals to find two points on the
        # lines parallel to the polygon lines
        ptx0  = ( pt0[0] + d01[0], pt0[1] + d01[1] )
        ptx10 = ( pt1[0] + d01[0], pt1[1] + d01[1] )
        ptx12 = ( pt1[0] + d12[0], pt1[1] + d12[1] )
        ptx2  = ( pt2[0] + d12[0], pt2[1] + d12[1] )

        # find the intersection of the two lines, and
        # add it to the expanded polygon
        expanded.append(intersect([ptx0, ptx10], [ptx12, ptx2]))
    
    return expanded
