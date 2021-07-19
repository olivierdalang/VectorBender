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

# Import the and QGIS graphical libraries
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtGui import *
from qgis.core import *
from qgis.gui import *

# standard library dependency
from os.path import join, dirname

# More tricky dependencies
from distutils.version import StrictVersion
dependenciesStatus = 2 # 2: ok, 1: too old, 0: missing
try:
    import matplotlib.tri
    minVersion = '1.3.0'
    if StrictVersion(matplotlib.__version__) < StrictVersion(minVersion):
        dependenciesStatus = 1
        QgsMessageLog.logMessage(
            f"Matplotlib version too old ({matplotlib.__version__} instead of {minVersion}). You won't be able to use the bending algorithm",
            "VectorBender")
except Exception: # <---- what type of exception??
    QgsMessageLog.logMessage(
        "Matplotlib is missing. You won't be able to use the bending algorithm", "VectorBender")
    dependenciesStatus = 0

# Other modules
from .vectorbendertransformers import *
from .vectorbenderdialog import VectorBenderDialog
from .vectorbenderhelp import VectorBenderHelp


class VectorBender:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = VectorBenderDialog(iface, self)
        self.ptsA = list()
        self.ptsB = list()
        self.transformer = None
        self.aboutWindow = None

    def initGui(self):
        self.action = QAction(
            QIcon(join(dirname(__file__), "resources", "icon.png")),
            "Vector Bender", self.iface.mainWindow())
        self.action.triggered.connect(self.showUi)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Vector Bender", self.action)
        self.helpAction = QAction(
            QIcon(join(dirname(__file__), "resources", "about.png")),
            "Vector Bender Help", self.iface.mainWindow())
        self.helpAction.triggered.connect(self.showHelp)
        self.iface.addPluginToMenu("&Vector Bender", self.helpAction)

    def showHelp(self):
        if self.aboutWindow is None:
            self.aboutWindow = VectorBenderHelp()
        self.aboutWindow.show()
        self.aboutWindow.raise_()

    def unload(self):
        # coudn't you use context syntax or is thsi a subclass from _io
        # so we can use `if self.dialog.closed:`
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None
        if self.aboutWindow is not None:
            self.aboutWindow.close()
            self.aboutWindow = None
        self.iface.removePluginMenu("&Vector Bender", self.action)
        self.iface.removePluginMenu("&Vector Bender", self.helpAction)
        self.iface.removeToolBarIcon(self.action)

    def showUi(self):
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.refreshStates()
    
    def featureCount(self, length):
        global dependenciesStatus
        if length <= 3: return length
        elif length >= 4:
            if dependenciesStatus != 2: return 5
            else: return 4
        return 0

    def determineTransformationType(self):
        """Returns :
            0 if no pairs Found
            1 if one pair found => translation
            2 if two pairs found => linear
            3 if three pairs found => affine
            4 if four or more pairs found => bending"""
        pairsLayer = self.dialog.pairsLayer()
        if pairsLayer is None:
            return 0
        elif self.dialog.restrictBox_pairsLayer.isChecked():
            self.featuresCount(len(pairsLayer.selectedFeatureIds()))
        else:
            self.featuresCount(len(pairsLayer.allFeatureIds())
    
    def delaunay(self, pairsLayer, transType):
        # Loading the delaunay
        restrictToSelection = self.dialog.restrictBox_pairsLayer.isChecked()
        if transType == 4:
            self.dialog.displayMsg(f"Loading delaunay mesh ({len(self.ptsA)} points) ...")
            QCoreApplication.processEvents()
            self.transformer = BendTransformer(pairsLayer, restrictToSelection, self.dialog.bufferValue())
        elif transType == 3:
            self.dialog.displayMsg("Loading affine transformation vectors...")
            self.transformer = AffineTransformer(pairsLayer, restrictToSelection)
        elif transType == 2:
            self.dialog.displayMsg("Loading linear transformation vectors...")
            self.transformer = LinearTransformer(pairsLayer, restrictToSelection)
        elif transType == 1:
            self.dialog.displayMsg("Loading translation vector...")
            self.transformer = TranslationTransformer(pairsLayer, restrictToSelection)
        else:
            self.dialog.displayMsg("INVALID TRANSFORMATION TYPE - YOU SHOULDN'T HAVE BEEN ABLE TO HIT RUN")
            return False
        return True
    
    def pairsToPinsTransformation(self, pairsLayer):
        if self.dialog.pairsToPinsCheckBox.isChecked():
            if not self.dialog.restrictBox_pairsLayer.isChecked():
                features = pairsLayer.getFeatures()
                total = pairsLayer.featureCount()
            else:
                features = pairsLayer.selectedFeatures()
                total = len(features)
            self.dialog.progressBar.setValue(0)
            self.dialog.displayMsg(
                f"Starting to transform {total} pairs to pins . . . ")
            QCoreApplication.processEvents()
            pairsLayer.beginEditCommand("Transforming pairs to pins")
            for count, feature in enumerate(features):
                self.dialog.progressBar.setValue((count / total) * 100)
                self.dialog.displayMsg(
                    f"Transforming pair to pin {count} out of {total} ... {count/total:%}")
                QCoreApplication.processEvents()
                geom = feature.geometry().asPolyline()
                pairsLayer.changeGeometry(
                    feature.id(), QgsGeometry.fromPolylineXY([geom[-1], geom[-1]]))
            pairsLayer.endEditCommand()
    
    def recursiveTransform(self, point_list):
        if not isinstance(point_list, list):
            return self.transformer.map(point_list)
        else:
            return [self.recursiveTransform(point) for point in point_list]

    def run(self):
        self.dialog.progressBar.setValue(0)
        toBendLayer = self.dialog.toBendLayer()
        pairsLayer = self.dialog.pairsLayer()
        if not self.delaunay(pairsLayer, self.determineTransformationType()):
            return
        # Starting to iterate
        if not self.dialog.restrictBox_toBendLayer.isChecked():
            features = toBendLayer.getFeatures()
            total = toBendLayer.featureCount()
        else:
            features = toBendLayer.selectedFeatures()
            total = len(features)
        self.dialog.displayMsg(f"Starting to iterate through {total} features...")
        QCoreApplication.processEvents()
        toBendLayer.beginEditCommand("Feature bending")
        for count, feature in enumerate(features):
            self.dialog.progressBar.setValue((count / total) * 100)
            self.dialog.displayMsg(
                f"Aligning features {count} out of {total} ... {count/total:%}")
            QCoreApplication.processEvents()
            geom = feature.geometry()
            # TODO : this code be much simple if we could iterate through to vertices
            # and use QgsGeometry.moveVertex(x,y,index), but QgsGeometry.vertexAt(index)
            # doesn't tell wether the index exists, so there's no clean way to iterate...
            if geom.type() == QgsWkbTypes.PointGeometry:
                if not geom.isMultipart(): # SINGLE PART POINT
                    geom = QgsGeometry.fromPointXY(
                        self.transformer.map(geom.asPoint()))
                else: # MULTI PART POINT
                    geom = QgsGeometry.fromMultiPointXY(
                        self.recursiveTransform(geom.asMultiPoint()))
            elif geom.type() == QgsWkbTypes.LineGeometry: # isinstance ?
                if not geom.isMultipart():  # SINGLE PART LINESTRING
                    geom = QgsGeometry.fromPolylineXY(
                        self.recursiveTransform(geom.asPolyline()))
                else: # MULTI PART LINESTRING
                    geom = QgsGeometry.fromMultiPolylineXY(
                        self.recursiveTransform(geom.asMultiPolyline()))
            elif geom.type() == QgsWkbTypes.PolygonGeometry: # isinstance ?
                if not geom.isMultipart(): # SINGLE PART POLYGON
                    geom = QgsGeometry.fromPolygonXY(
                        self.recursiveTransform(geom.asPolygon()))
                else: # MULTI PART POLYGON
                    geom = QgsGeometry.fromMultiPolygonXY(
                        self.recursiveTransform(geom.asMultiPolygon()))
            toBendLayer.changeGeometry(feature.id(), geom)
        toBendLayer.endEditCommand()
        toBendLayer.repaintRequested.emit()
        #Transforming pairs to pins
        self.pairsToPinsTransformation(pairsLayer)
        self.dialog.displayMsg("Finished !")
        self.dialog.progressBar.setValue(100)
        pairsLayer.repaintRequested.emit()
