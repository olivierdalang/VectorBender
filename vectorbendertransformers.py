# -*- coding: utf-8 -*-
from qgis.core import *
from math import sqrt, pow, atan2, sin, cos

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

        self.pointsA = list()
        self.pointsB = list()
        if not restrictToSelection:
            features = pairsLayer.getFeatures()
        else:
            features = pairsLayer.selectedFeatures()

        for feature in features:
            geom = feature.geometry().asPolyline()
            self.pointsA.append(QgsPointXY(geom[0].x(), geom[0].y()))
            self.pointsB.append(QgsPointXY(geom[-1].x(), geom[-1].y()))

    def map(self, point):
        return point
    
    def pythag(self, x, y):
        return sqrt(pow(x) + pow(y))
    
    def diff_x(self, point_0, point_1):
        return point_0.x() - point_1.x()
    
    def diff_y(self, point_0, point_1):
        return point_0.y() - point_1.y()
    

class BendTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection, buff):

        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA) >= 3
        assert len(self.pointsA) == len(self.pointsB)

        self.hull = QgsGeometry.fromMultiPointXY(self.pointsA).convexHull()

        # If there is a buffer, we add a ring outside the hull so that the transformation smoothly stops
        if buff > 0:
            self.expandedHull = self.hull.buffer(buff, 3)
            for point in self.expandedHull.asPolygon()[0]:
                self.pointsA.append(point)
                self.pointsB.append(point)
        else:
            self.expandedHull = None

        # We compute the delaunay        
        self.delaunay = matplotlib.tri.Triangulation(
            [point.x() for point in self.pointsA],
            [point.y() for point in self.pointsA])
        self.trifinder = self.delaunay.get_trifinder()

    def map(self, point):
        triangle = self.trifinder(point[0], point[1])
        if triangle == -1:
            # No triangle found : don't change the point
            return QgsPointXY(point[0], point[1])
        else:
            # Triangle found : adapt it from the old mesh to the new mesh
            a_points = list()
            b_points = list()
            for i in range(3):
                a_points.append(
                    self.pointsA[self.delaunay.triangles[triangle][i]])
            for i in range(3):
                b_points.append(
                    self.pointsB[self.delaunay.triangles[triangle][i]])
            return self.mapPointFromTriangleAtoTriangleB(
                point, *a_points, *b_points)

    def mapPointFromTriangleAtoTriangleB(self, point, a1, a2, a3, b1, b2, b3):
        return self.fromTriangularToCartesian(
            self.fromCartesianToTriangular(point, a1, a2, a3), b1, b2, b3)

    def fromCartesianToTriangular(self, poiunt, t1, t2, t3):
        """ Returns triangular coordinates (l1, l2, l3) for a given point in a given triangle
            p is a duplet for cartesian coordinates coordinates """
        x, y = point
        x1, y1 = t1.x(), t1.y()
        x2, y2 = t2.x(), t2.y()
        x3, y3 = t3.x(), t3.y()
        line_1 = (y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)
        line_1 /= (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        line_2 = (y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)
        line_2 /= (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        return (line_1, line_2, 1 - line_1 - line_2)

    def fromTriangularToCartesian(self, lines, t1, t2, t3):
        """ lines is a triplet for barycentric coordinates """
        line_1, line_2, line_3 = lines
        x = line_1 * t1.x() + line_2 * t2.x() + line_3 * t3.x()
        y = line_1 * t1.y() + line_2 * t2.y() + line_3 * t3.y()
        return QgsPointXY(x, y)

class AffineTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA) == 3
        assert len(self.pointsA) == len(self.pointsB)

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

        self.a = x12 * (y31 - y21) - x22 * y31 + x32 * y21 + (x22 - x32) * y11
        self.a /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31)  *y11
        
        self.b = x11 * (x32 - x22) - x21 * x32 + x22 * x31 + x12 * (x21  -x31)
        self.b /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31) * y11
        
        self.c = -(x11 * (x32 * y21 - x22 * y31) + x12 * (x21 * y31 - x31 * y21) + (x22 * x31 - x21 * x32) * y11)
        self.c /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21-x31) * y11
        
        self.d = y21 * y32 + y11 * (y22 - y32) + y12 * (y31 - y21) - y22 * y31
        self.d /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31) * y11
        
        self.e = -(x21 * y32 + x11 * (y22 - y32) - x31 * y22 + (x31 - x21) * y12)
        self.e /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31) * y11
        self.f = x11 * (y22 * y31 - y21 * y32) + y11 * (x21 * y32 - x31 * y22)
        self.f += y12 * (x31 * y21 - x21 * y31)
        self.f /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31) * y11


    def map(self, p):
        return QgsPointXY(
            self.a * p.x() + self.b * p.y() + self.c,
            self.d * p.x() + self.e * p.y() + self.f)
        
class LinearTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA) == 2
        assert len(self.pointsA) == len(self.pointsB)

        self.a1 = self.pointsA[0]
        self.a2 = self.pointsA[1]
        self.b1 = self.pointsB[0]
        self.b2 = self.pointsB[1]

        # scale
        self._scale()
        # rotation
        self._rotation()
        # translation
        self.dx1 = self.pointsA[0].x()
        self.dy1 = self.pointsA[0].y()
        self.dx2 = self.pointsB[0].x()
        self.dy2 = self.pointsB[0].y()
    
    def _scale(self):
        a1, a2, b1, b2 = self.a1, self.a2, self.b1, self.b2
        self.delta_scale = self.pythag(self.diff_x(b2, b1), self.diff_y(b2, b1))
        self.delta_scale /= self.pythag(self.diff_x(a2, a1), self.diff_y(a2, a1))
    
    def _rotation(self):
        a1, a2, b1, b2 = self.a1, self.a2, self.b1, self.b2
        self.delta_angle = atan2(self.diff_y(b2, b1), self.diff_x(b2, b1))
        self.delta_angle -= atan2(self.diff_y(a2, a1), self.diff_x(a2, a1))

    def map(self, point):
        #move to origin (translation part 1)
        point = QgsPointXY(point.x() - self.dx1, point.y() - self.dy1)
        #scale 
        point = QgsPointXY(
            self.delta_scale * point.x(), self.delta_scale * point.y())
        #rotation
        point = QgsPointXY(
            cos(self.delta_angle) * point.x() - sin(self.delta_angle) * point.y(),
            sin(self.delta_angle) * point.x() + cos(self.delta_angle) * point.y())
        #remove to right spot (translation part 2)
        return QgsPointXY(point.x() + self.dx2, point.y() + self.dy2)

class TranslationTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA) == 1
        assert len(self.pointsA) == len(self.pointsB)

        self.dx = self.diff_x(self.pointsB[0], self.pointsA[0])
        self.dy = self.diff_y(self.pointsB[0], self.pointsA[0])

    def map(self, point):
        return QgsPointXY(point[0] + self.dx, point[1] + self.dy)

# -*- coding: utf-8 -*-
from qgis.core import *
from math import sqrt, pow, atan2, sin, cos

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

        self.pointsA = list()
        self.pointsB = list()
        if not restrictToSelection:
            features = pairsLayer.getFeatures()
        else:
            features = pairsLayer.selectedFeatures()

        for feature in features:
            geom = feature.geometry().asPolyline()
            self.pointsA.append(QgsPointXY(geom[0].x(), geom[0].y()))
            self.pointsB.append(QgsPointXY(geom[-1].x(), geom[-1].y()))

    def map(self, point):
        return point
    
    def pythag(self, x, y):
        return sqrt(pow(x) + pow(y))
    
    def diff_x(self, point_0, point_1):
        return point_0.x() - point_1.x()
    
    def diff_y(self, point_0, point_1):
        return point_0.y() - point_1.y()
    

class BendTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection, buff):

        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA) >= 3
        assert len(self.pointsA) == len(self.pointsB)

        self.hull = QgsGeometry.fromMultiPointXY(self.pointsA).convexHull()

        # If there is a buffer, we add a ring outside the hull so that the transformation smoothly stops
        if buff > 0:
            self.expandedHull = self.hull.buffer(buff, 3)
            for point in self.expandedHull.asPolygon()[0]:
                self.pointsA.append(point)
                self.pointsB.append(point)
        else:
            self.expandedHull = None

        # We compute the delaunay        
        self.delaunay = matplotlib.tri.Triangulation(
            [point.x() for point in self.pointsA],
            [point.y() for point in self.pointsA])
        self.trifinder = self.delaunay.get_trifinder()

    def map(self, point):
        triangle = self.trifinder(point[0], point[1])
        if triangle == -1:
            # No triangle found : don't change the point
            return QgsPointXY(point[0], point[1])
        else:
            # Triangle found : adapt it from the old mesh to the new mesh
            a_points = list()
            b_points = list()
            for i in range(3):
                a_points.append(
                    self.pointsA[self.delaunay.triangles[triangle][i]])
            for i in range(3):
                b_points.append(
                    self.pointsB[self.delaunay.triangles[triangle][i]])
            return self.mapPointFromTriangleAtoTriangleB(
                point, *a_points, *b_points)

    def mapPointFromTriangleAtoTriangleB(self, point, a1, a2, a3, b1, b2, b3):
        return self.fromTriangularToCartesian(
            self.fromCartesianToTriangular(point, a1, a2, a3), b1, b2, b3)

    def fromCartesianToTriangular(self, poiunt, t1, t2, t3):
        """ Returns triangular coordinates (l1, l2, l3) for a given point in a given triangle
            p is a duplet for cartesian coordinates coordinates """
        x, y = point
        x1, y1 = t1.x(), t1.y()
        x2, y2 = t2.x(), t2.y()
        x3, y3 = t3.x(), t3.y()
        line_1 = (y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)
        line_1 /= (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        line_2 = (y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)
        line_2 /= (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        return (line_1, line_2, 1 - line_1 - line_2)

    def fromTriangularToCartesian(self, lines, t1, t2, t3):
        """ lines is a triplet for barycentric coordinates """
        line_1, line_2, line_3 = lines
        x = line_1 * t1.x() + line_2 * t2.x() + line_3 * t3.x()
        y = line_1 * t1.y() + line_2 * t2.y() + line_3 * t3.y()
        return QgsPointXY(x, y)

class AffineTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA) == 3
        assert len(self.pointsA) == len(self.pointsB)

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

        self.a = x12 * (y31 - y21) - x22 * y31 + x32 * y21 + (x22 - x32) * y11
        self.a /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31)  *y11
        
        self.b = x11 * (x32 - x22) - x21 * x32 + x22 * x31 + x12 * (x21  -x31)
        self.b /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31) * y11
        
        self.c = -(x11 * (x32 * y21 - x22 * y31) + x12 * (x21 * y31 - x31 * y21) + (x22 * x31 - x21 * x32) * y11)
        self.c /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21-x31) * y11
        
        self.d = y21 * y32 + y11 * (y22 - y32) + y12 * (y31 - y21) - y22 * y31
        self.d /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31) * y11
        
        self.e = -(x21 * y32 + x11 * (y22 - y32) - x31 * y22 + (x31 - x21) * y12)
        self.e /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31) * y11
        self.f = x11 * (y22 * y31 - y21 * y32) + y11 * (x21 * y32 - x31 * y22)
        self.f += y12 * (x31 * y21 - x21 * y31)
        self.f /= x11 * (y31 - y21) - x21 * y31 + x31 * y21 + (x21 - x31) * y11


    def map(self, p):
        return QgsPointXY(
            self.a * p.x() + self.b * p.y() + self.c,
            self.d * p.x() + self.e * p.y() + self.f)
        
class LinearTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA) == 2
        assert len(self.pointsA) == len(self.pointsB)

        self.a1 = self.pointsA[0]
        self.a2 = self.pointsA[1]
        self.b1 = self.pointsB[0]
        self.b2 = self.pointsB[1]

        # scale
        self._scale()
        # rotation
        self._rotation()
        # translation
        self.dx1 = self.pointsA[0].x()
        self.dy1 = self.pointsA[0].y()
        self.dx2 = self.pointsB[0].x()
        self.dy2 = self.pointsB[0].y()
    
    def _scale(self):
        a1, a2, b1, b2 = self.a1, self.a2, self.b1, self.b2
        self.delta_scale = self.pythag(self.diff_x(b2, b1), self.diff_y(b2, b1))
        self.delta_scale /= self.pythag(self.diff_x(a2, a1), self.diff_y(a2, a1))
    
    def _rotation(self):
        a1, a2, b1, b2 = self.a1, self.a2, self.b1, self.b2
        self.delta_angle = atan2(self.diff_y(b2, b1), self.diff_x(b2, b1))
        self.delta_angle -= atan2(self.diff_y(a2, a1), self.diff_x(a2, a1))

    def map(self, point):
        #move to origin (translation part 1)
        point = QgsPointXY(point.x() - self.dx1, point.y() - self.dy1)
        #scale 
        point = QgsPointXY(
            self.delta_scale * point.x(), self.delta_scale * point.y())
        #rotation
        point = QgsPointXY(
            cos(self.delta_angle) * point.x() - sin(self.delta_angle) * point.y(),
            sin(self.delta_angle) * point.x() + cos(self.delta_angle) * point.y())
        #remove to right spot (translation part 2)
        return QgsPointXY(point.x() + self.dx2, point.y() + self.dy2)

class TranslationTransformer(Transformer):
    def __init__(self, pairsLayer, restrictToSelection):
        Transformer.__init__(self, pairsLayer, restrictToSelection)

        # Make sure data is valid
        assert len(self.pointsA) == 1
        assert len(self.pointsA) == len(self.pointsB)

        self.dx = self.diff_x(self.pointsB[0], self.pointsA[0])
        self.dy = self.diff_y(self.pointsB[0], self.pointsA[0])

    def map(self, point):
        return QgsPointXY(point[0] + self.dx, point[1] + self.dy)

