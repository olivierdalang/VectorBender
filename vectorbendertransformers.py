# -*- coding: utf-8 -*-
from qgis.core import *
import math

try:
    #we silently fail the import here since message is already taken car in vectorbender.py
    import matplotlib.tri
except Exception:
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
            self.pointsA.append( QgsPointXY(geom[0].x(),geom[0].y()) ) #Almerio: era QgsPoint
            self.pointsB.append( QgsPointXY(geom[-1].x(),geom[-1].y()) ) #Almerio: era QgsPoint

    def map(self, p):
        return p

class BendTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection, buff):

        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA)>=3
        assert len(self.pointsA)==len(self.pointsB)

        self.hull = QgsGeometry.fromMultiPointXY( self.pointsA ).convexHull() #Almerio: fromMultiPoint

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
            return QgsPointXY(p[0], p[1]) #Almerio: era QgsPoint
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
        return QgsPointXY(x,y) ##Almerio: era QgsPoint

class AffineTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA)==3
        assert len(self.pointsA)==len(self.pointsB)

        self.a1 = self.pointsA[0]
        self.a2 = self.pointsA[1]
        self.a3 = self.pointsA[2]
        self.b1 = self.pointsB[0]
        self.b2 = self.pointsB[1]
        self.b3 = self.pointsB[2]


        """
        MATRIX
            [a,b,c] 
        M = [d,e,f] 
            [0,0,1] 
               [x11]   [x12]
        1] M * [y11] = [y12]
               [ 1 ]   [ 1 ]
               [x21]   [x22]
        2] M * [y21] = [y22]
               [ 1 ]   [ 1 ]
               [x31]   [x32]
        3] M * [y31] = [y32]
               [ 1 ]   [ 1 ]
        Equations to solve
        [ 
            a*x11+b*y11+c = x12,
            d*x11+e*y11+f = y12,
            a*x21+b*y21+c = x22,
            d*x21+e*y21+f = y22,
            a*x31+b*y31+c = x32,
            d*x31+e*y31+f = y32]
        For variables
        [a,b,c,d,e,f]
        Result using http://www.numberempire.com/equationsolver.php
        a = (x12*(y31-y21)-x22*y31+x32*y21+(x22-x32)*y11)/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        b = (x11*(x32-x22)-x21*x32+x22*x31+x12*(x21-x31))/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        c = -(x11*(x32*y21-x22*y31)+x12*(x21*y31-x31*y21)+(x22*x31-x21*x32)*y11)/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        d = (y21*y32+y11*(y22-y32)+y12*(y31-y21)-y22*y31)/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        e = -(x21*y32+x11*(y22-y32)-x31*y22+(x31-x21)*y12)/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        f = (x11*(y22*y31-y21*y32)+y11*(x21*y32-x31*y22)+y12*(x31*y21-x21*y31))/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        """

        x11 = self.a1.x()
        y11 = self.a1.y()
        x21 = self.a2.x()
        y21 = self.a2.y()
        x31 = self.a3.x()
        y31 = self.a3.y()
        x12 = self.b1.x()
        y12 = self.b1.y()
        x22 = self.b2.x()
        y22 = self.b2.y()
        x32 = self.b3.x()
        y32 = self.b3.y()

        self.a = (x12*(y31-y21)-x22*y31+x32*y21+(x22-x32)*y11)/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        self.b = (x11*(x32-x22)-x21*x32+x22*x31+x12*(x21-x31))/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        self.c = -(x11*(x32*y21-x22*y31)+x12*(x21*y31-x31*y21)+(x22*x31-x21*x32)*y11)/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        self.d = (y21*y32+y11*(y22-y32)+y12*(y31-y21)-y22*y31)/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        self.e = -(x21*y32+x11*(y22-y32)-x31*y22+(x31-x21)*y12)/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)
        self.f = (x11*(y22*y31-y21*y32)+y11*(x21*y32-x31*y22)+y12*(x31*y21-x21*y31))/(x11*(y31-y21)-x21*y31+x31*y21+(x21-x31)*y11)


    def map(self, p):

        return QgsPointXY( self.a*p.x()+self.b*p.y()+self.c, self.d*p.x()+self.e*p.y()+self.f ) #Almerio: era QgsPoint
        
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
        p = QgsPointXY( p.x()-self.dx1, p.y()-self.dy1 )#Almerio: era QgsPoint

        #scale 
        p = QgsPointXY( self.ds*p.x(), self.ds*p.y() )#Almerio: era QgsPoint

        #rotation
        p = QgsPointXY( math.cos(self.da)*p.x() - math.sin(self.da)*p.y(), math.sin(self.da)*p.x() + math.cos(self.da)*p.y() )#Almerio: era QgsPoint

        #remove to right spot (translation part 2)
        p = QgsPointXY( p.x()+self.dx2, p.y()+self.dy2 )#Almerio: era QgsPoint

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
        return QgsPointXY(p[0]+self.dx, p[1]+self.dy) #Almerio: era QgsPoint

