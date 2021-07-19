# -*- coding: utf-8 -*-
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *

from qgis.core import *
from qgis.gui import *

from os.path import join, dirname

from .vectorbendertransformers import *

class VectorBenderDialog(QtWidgets.QDialog):
    def __init__(self, iface, vb):
        QtWidgets.QDialog.__init__(self)
        uic.loadUi(join(dirname(__file__), "ui_main.ui"), self)
        self.setFocusPolicy(Qt.ClickFocus)
        #self.setWindowModality( Qt.ApplicationModal )

        self.iface = iface
        self.vb = vb

        # Keeps three rubberbands for delaunay's peview
        self.rubberBands = None

        # Connect the UI buttons
        self.createMemoryLayerButton.clicked.connect(self.createMemoryLayer)

        self.previewButton.pressed.connect(self.showPreview)
        self.previewButton.released.connect(self.hidePreview)

        self.editModeButton_toBendLayer.clicked.connect(self.toggleEditMode_toBendLayer)
        self.editModeButton_pairsLayer.clicked.connect(self.toggleEditMode_pairsLayer)

        self.runButton.clicked.connect(self.vb.run)

        # When those are changed, we recheck the requirements
        self.editModeButton_pairsLayer.clicked.connect(self.checkRequirements)
        self.editModeButton_toBendLayer.clicked.connect(self.checkRequirements)
        self.comboBox_toBendLayer.activated.connect(self.checkRequirements)
        self.pairsToPinsCheckBox.clicked.connect(self.checkRequirements)

        # When those are changed, we change the transformation type (which also checks the requirements)
        self.comboBox_toBendLayer.activated.connect(self.updateEditState_toBendLayer)
        self.comboBox_pairsLayer.activated.connect(self.updateEditState_pairsLayer)
        self.comboBox_pairsLayer.activated.connect(self.updateTransformationType)
        self.restrictBox_pairsLayer.stateChanged.connect(self.updateTransformationType)

        # Create an event filter to update on focus
        self.installEventFilter(self)


    # UI Getters
    def toBendLayer(self):
        """
        Returns the current toBend layer depending on what is choosen in the comboBox_pairsLayer
        """
        return QgsProject.instance().mapLayer(
            self.comboBox_toBendLayer.itemData(self.comboBox_toBendLayer.currentIndex()))
    
    def pairsLayer(self):
        """
        Returns the current pairsLayer layer depending on what is choosen in the comboBox_pairsLayer
        """
        return QgsProject.instance().mapLayer(
            self.comboBox_pairsLayer.itemData(self.comboBox_pairsLayer.currentIndex()))
    
    def bufferValue(self):
        """
        Returns the current buffer value depending on the input in the spinbox
        """
        return self.bufferSpinBox.value()

    # Updaters
    def refreshStates(self):
        """
        Updates the UI values, to be used upon opening / activating the window
        """
        # Update the comboboxes
        self.updateLayersComboboxes()
        # Update the edit mode buttons
        self.updateEditState_pairsLayer()
        self.updateEditState_toBendLayer()
        # Update the transformation type
        self.updateTransformationType()
    
    def checkRequirements(self):
        """
        To be run after changes have been made to the UI. It enables/disables the run button and display some messages.
        """
        # Checkin requirements
        self.runButton.setEnabled(False)

        to_bend_layer = self.toBendLayer()
        pairs_layer = self.pairsLayer()

        if to_bend_layer is None:
            self.displayMsg("You must select a vector layer to bend !", True )
        elif pairs_layer is None:
            self.displayMsg("You must select a vector (line) layer which defines the points pairs !", True )
        elif pairs_layer is to_bend_layer:
            self.displayMsg("The layer to bend must be different from the pairs layer !", True )
        elif not to_bend_layer.isEditable():
            self.displayMsg("The layer to bend must be in edit mode !", True )
        elif not pairs_layer.isEditable() and self.pairsToPinsCheckBox.isChecked():
            self.displayMsg("The pairs layer must be in edit mode if you want to change pairs to pins !", True )
        elif self.stackedWidget.currentIndex() == 0:
            self.displayMsg("Impossible to run with an invalid transformation type.", True)
        else:
            self.displayMsg("Ready to go...")
            self.runButton.setEnabled(True)

    def updateLayersComboboxes(self):
        """ Recreate the comboboxes to display existing layers. """
        oldBendLayer = self.toBendLayer()
        oldPairsLayer = self.pairsLayer()

        self.comboBox_toBendLayer.clear()
        self.comboBox_pairsLayer.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayer.VectorLayer:
                self.comboBox_toBendLayer.addItem( layer.name(), layer.id() )
                if layer.geometryType() == QgsWkbTypes.LineGeometry :
                    self.comboBox_pairsLayer.addItem( layer.name(), layer.id() )

        if oldBendLayer is not None:
            index = self.comboBox_toBendLayer.findData(oldBendLayer.id())
            self.comboBox_toBendLayer.setCurrentIndex(index)
        if oldPairsLayer is not None:
            index = self.comboBox_pairsLayer.findData(oldPairsLayer.id())
            self.comboBox_pairsLayer.setCurrentIndex(index)
    
    def updateEditState_pairsLayer(self):
        """ Update the edit state button for pairsLayer """
        layer = self.pairsLayer()
        self.editModeButton_pairsLayer.setChecked(
            False if (layer is None or not layer.isEditable()) else True)
        
    def updateEditState_toBendLayer(self):
        """ Update the edit state button for toBendLayer """
        layer = self.toBendLayer()
        self.editModeButton_toBendLayer.setChecked(
            False if (layer is None or not layer.isEditable()) else True)
        
    def updateTransformationType(self):
        """
        Update the stacked widget to display the proper transformation type. Also runs checkRequirements() 
        """
        self.stackedWidget.setCurrentIndex(self.vb.determineTransformationType())

        self.checkRequirements()

    # Togglers
    def toggleEditMode(self, checked, toBendLayer_True_pairsLayer_False):
        layer = self.toBendLayer() if toBendLayer_True_pairsLayer_False else self.pairsLayer()
        if layer is None:
            return 

        if checked:
            layer.startEditing()
        else:
            if not layer.isModified():
                layer.rollBack()
            else:
                return_value = QMessageBox.warning(
                    self, "Stop editting", f"Do you want to save the changes to layer {layer.name()} ?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)

                if return_value == QMessageBox.Save:
                    layer.commitChanges()
                elif return_value == QMessageBox.Discard:
                    layer.rollBack()
    
    def toggleEditMode_toBendLayer(self, checked):
        self.toggleEditMode(checked, True)
    
    def toggleEditMode_pairsLayer(self, checked):
        self.toggleEditMode(checked, False)

    # Misc
    def createMemoryLayer(self):
        """
        Creates a new memory layer to be used as pairLayer, and selects it in the ComboBox.
        """

        suffix = 0
        name = "Vector Bender"
        while len(QgsProject.instance().mapLayersByName(f"{name} {suffix}")) > 0:
            suffix += 1

        newMemoryLayer = QgsVectorLayer("Linestring", f"{name} {suffix}", "memory")
        newMemoryLayer.loadNamedStyle(join(dirname(__file__), "PairStyle.qml"), False)
        QgsProject.instance().addMapLayer(newMemoryLayer)

        self.updateLayersComboboxes()

        index = self.comboBox_pairsLayer.findData(newMemoryLayer.id())
        self.comboBox_pairsLayer.setCurrentIndex( index )
        
        newMemoryLayer.startEditing()
        
    def displayMsg(self, msg, error = False):
        self.statusLabel.setText(
            f"<font color='red'>{msg}</font>" if error else msg)
    
    def hidePreview(self):
        if self.rubberBands is not None:
            for i in range(3):
                self.rubberBands[i].reset(QgsWkbTypes.PolygonGeometry)
            self.rubberBands = None
    
    def showPreview(self):
        for _ in range(3):
            rubberBands = QgsRubberBand(
                self.iface.mapCanvas(), QgsWkbTypes.PolygonGeometry)
            rubberBands.reset(QgsWkbTypes.PolygonGeometry)
            self.rubberBands.append(rubberBands)

        pairsLayer = self.pairsLayer()

        transformer = BendTransformer(
            pairsLayer, self.restrictBox_pairsLayer.isChecked(), self.bufferValue())
        
        values = [
            ((0, 125, 255), Qt.Dense6Pattern, 3),
            ((255, 125, 0), Qt.Dense6Pattern, 3),
            ((0, 125, 0, 50), Qt.NoBrush, 1)]
        for n, value in enumerate(values):
            self.rubberBands[n].setColor(QColor(*value[0]))
            self.rubberBands[n].setBrushStyle(value[1])
            self.rubberBands[n].setWidth(value[2])
      
        # draw the expanded hull
        if transformer.expandedHull is not None:
            for point in transformer.expandedHull.asPolygon()[0]:
                self.rubberBands[0].addPoint(point, True, 0)
            for point in transformer.expandedHull.asPolygon()[0][0:1]:
                #we readd the first point since it's not possible to make true rings with rubberbands
                self.rubberBands[0].addPoint(point, True, 0)
        
        # draw the hull
        for point in transformer.hull.asPolygon()[0]:
            self.rubberBands[0].addPoint(point, True, 0) # inner ring of rubberband 1
            self.rubberBands[1].addPoint(point, True, 0)
        for point in transformer.hull.asPolygon()[0][0:1]:
            # we readd the first point since it's not possible to make true rings with rubberbands
            self.rubberBands[0].addPoint(point, True, 0)
        
        # draw the triangles
        for i, tri in enumerate(transformer.delaunay.triangles):
            for j, boolean in enumerate([False, False, True]):
                self.rubberBands[2].addPoint(transformer.pointsA[tri[j]], boolean, i)
            #TODO : this refreshes the rubber band on each triangle, it should be updated only once after this loop

    # Events
    def eventFilter(self, obj, event):
        if event.type() == QEvent.WindowActivate:
            self.refreshStates()


