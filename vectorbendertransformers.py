# -*- coding: utf-8 -*-
from qgis.core import *
import math

try:
    #we silently fail the import here since message is already taken car in vectorbender.py
    import matplotlib.tri
except Exception, e:
    pass

class Transformer():
    """
    Represents an abstract transfromation type
    """
    def __init__(self, pairsLayer, restrictToSelection):

        self.pointsA = []
        self.pointsB = []
        features = pairsLayer.getFeatures() if not restrictToSelection else pairsLayer.selectedFeatures()

        for feature in features:
            geom = feature.geometry().asPolyline()
            self.pointsA.append( QgsPoint(geom[0].x(),geom[0].y()) )
            self.pointsB.append( QgsPoint(geom[-1].x(),geom[-1].y()) )

    def map(self, p):
        return p

class BendTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection, buff):

        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA)>=3
        assert len(self.pointsA)==len(self.pointsB)

        self.hull = QgsGeometry.fromMultiPoint( self.pointsA ).convexHull()

        # If there is a buffer, we add a ring outside the hull so that the transformation smoothly stops
        if buff>0:
            self.expandedHull = self.hull.buffer(buff, 3)
            for p in self.expandedHull.asPolygon()[0]:
                self.pointsA.append( p )
                self.pointsB.append( p )
        else:
            self.expandedHull = None

        # We compute the delaunay        
        self.delaunay = matplotlib.tri.Triangulation([p.x() for p in self.pointsA],[p.y() for p in self.pointsA])
        self.trifinder = self.delaunay.get_trifinder()

    def map(self, p):

        triangle = self.trifinder( p[0], p[1] )

        if triangle==-1:
            # No triangle found : don't change the point
            return QgsPoint(p[0], p[1])
        else:
            # Triangle found : adapt it from the old mesh to the new mesh
            a1 = self.pointsA[self.delaunay.triangles[triangle][0]]
            a2 = self.pointsA[self.delaunay.triangles[triangle][1]]
            a3 = self.pointsA[self.delaunay.triangles[triangle][2]]

            b1 = self.pointsB[self.delaunay.triangles[triangle][0]]
            b2 = self.pointsB[self.delaunay.triangles[triangle][1]]
            b3 = self.pointsB[self.delaunay.triangles[triangle][2]]

            mappedP = self.mapPointFromTriangleAtoTriangleB(p, a1, a2, a3, b1, b2, b3)

            return mappedP

    def mapPointFromTriangleAtoTriangleB(self, p, a1,a2,a3, b1,b2,b3 ):
        cT = self.fromCartesianToTriangular( p, a1, a2, a3  )
        cC = self.fromTriangularToCartesian( cT, b1, b2, b3  )
        return cC

    def fromCartesianToTriangular(self, p, t1, t2, t3):
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

    def fromTriangularToCartesian(self, l,t1,t2,t3):
        """ l is a triplet for barycentric coordinates """
        x = l[0]*t1.x()+l[1]*t2.x()+l[2]*t3.x()
        y = l[0]*t1.y()+l[1]*t2.y()+l[2]*t3.y()
        return QgsPoint(x,y)


class LinearTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA)==2
        assert len(self.pointsA)==len(self.pointsB)

        self.a1 = self.pointsA[0]
        self.a2 = self.pointsA[1]
        self.b1 = self.pointsB[0]
        self.b2 = self.pointsB[1]

        #scale 
        self.ds = math.sqrt( (self.b2.x()-self.b1.x())**2.0+(self.b2.y()-self.b1.y())**2.0 ) / math.sqrt( (self.a2.x()-self.a1.x())**2.0+(self.a2.y()-self.a1.y())**2.0 )
        #rotation
        self.da =  math.atan2( self.b2.y()-self.b1.y(), self.b2.x()-self.b1.x() ) - math.atan2( self.a2.y()-self.a1.y(), self.a2.x()-self.a1.x() )
        #translation
        self.dx1 = self.pointsA[0].x()
        self.dy1 = self.pointsA[0].y() 
        self.dx2 = self.pointsB[0].x()
        self.dy2 = self.pointsB[0].y()


    def map(self, p):

        #move to origin (translation part 1)
        p = QgsPoint( p.x()-self.dx1, p.y()-self.dy1 )

        #scale 
        p = QgsPoint( self.ds*p.x(), self.ds*p.y() )

        #rotation
        p = QgsPoint( math.cos(self.da)*p.x() - math.sin(self.da)*p.y(), math.sin(self.da)*p.x() + math.cos(self.da)*p.y() )

        #remove to right spot (translation part 2)
        p = QgsPoint( p.x()+self.dx2, p.y()+self.dy2 )

        return p

class TranslationTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA)==1 
        assert len(self.pointsA)==len(self.pointsB)

        self.dx = self.pointsB[0].x()-self.pointsA[0].x()
        self.dy = self.pointsB[0].y()-self.pointsA[0].y()

    def map(self, p):
        return QgsPoint(p[0]+self.dx, p[1]+self.dy)

