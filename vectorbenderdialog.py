# -*- coding: utf-8 -*-

from PyQt4 import uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import *
import os.path


class VectorBenderDialog(QWidget):
    def __init__(self, iface, vb):
        QWidget.__init__(self)
        uic.loadUi(os.path.join(os.path.dirname(__file__),'ui_main.ui'), self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint) #TODO : is there a way to have the window not on top of other applications ?

        self.iface = iface
        self.vb = vb

        self.updateLayersComboboxes()
        self.updateEditState()

        QgsMapLayerRegistry.instance().layersAdded.connect( self.updateLayersComboboxes )
        QgsMapLayerRegistry.instance().layersRemoved.connect( self.updateLayersComboboxes )

        self.createMemoryLayerButton.clicked.connect(self.createMemoryLayer)

        self.previewButton.clicked.connect(self.vb.togglePreview)
        self.toggleEditModeButton.clicked.connect(self.toggleEditMode)
        self.runButton.clicked.connect(self.vb.run)

        self.bufferSpinBox.valueChanged.connect( self.vb.updatePreview )

        self.layerToBendComboBox.currentIndexChanged.connect( self.updateEditState )

    def layerToBend(self):
        layerId = self.layerToBendComboBox.itemData(self.layerToBendComboBox.currentIndex())
        return QgsMapLayerRegistry.instance().mapLayer(layerId)
    def pairsLayer(self):
        layerId = self.pairsLayerComboBox.itemData(self.pairsLayerComboBox.currentIndex())
        return QgsMapLayerRegistry.instance().mapLayer(layerId)
    def bufferValue(self):
        return self.bufferSpinBox.value()

    def updateEditState(self):
        if self.layerToBend() is not None:
            self.toggleEditModeButton.setChecked( self.layerToBend().isEditable() )

    def show(self):
        self.updateEditState()
        self.updateLayersComboboxes()
        QWidget.show(self)


    def updateLayersComboboxes(self):
        oldBendLayer = self.layerToBend()
        oldPairsLayer = self.pairsLayer()

        self.layerToBendComboBox.clear()
        self.pairsLayerComboBox.clear()
        for layer in self.iface.legendInterface().layers():
            if layer.type() == QgsMapLayer.VectorLayer:
                self.layerToBendComboBox.addItem( layer.name(), layer.id() )
                if layer.geometryType() == QGis.Line :
                    self.pairsLayerComboBox.addItem( layer.name(), layer.id() )

        if oldBendLayer is not None:
            index = self.layerToBendComboBox.findData(oldBendLayer.id())
            self.layerToBendComboBox.setCurrentIndex( index )
        if oldPairsLayer is not None:
            index = self.pairsLayerComboBox.findData(oldPairsLayer.id())
            self.pairsLayerComboBox.setCurrentIndex( index )



    def createMemoryLayer(self):
        suffix = ""
        name = "Vector Bender"
        while len( QgsMapLayerRegistry.instance().mapLayersByName( name+suffix ) ) > 0:
            if suffix == "": suffix = " 1"
            else: suffix = " "+str(int(suffix)+1)

        newMemoryLayer = QgsVectorLayer("Linestring", name+suffix, "memory")
        newMemoryLayer.loadNamedStyle(os.path.join(os.path.dirname(__file__),'PairStyle.qml'), False)
        QgsMapLayerRegistry.instance().addMapLayer(newMemoryLayer)

        self.updateLayersComboboxes()

        index = self.pairsLayerComboBox.findData(newMemoryLayer.id())
        self.pairsLayerComboBox.setCurrentIndex( index )
        
        newMemoryLayer.startEditing()

    def toggleEditMode(self, checked):
        l = self.layerToBend()
        if l is None:
            return 

        if checked:
            l.startEditing()
        else:
            if not l.isModified():
                l.rollBack()
            else:
                retval = QMessageBox.warning(self, "Stop editting", "Do you want to save the changes to layer %s ?" % l.name(), QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)

                if retval == QMessageBox.Save:
                    l.commitChanges()
                elif retval == QMessageBox.Discard:
                    l.rollBack()

    def displayMsg(self, msg, error=False):
        if error:
            QApplication.beep()
            msg = "<font color='red'>"+msg+"</font>"
        self.statusLabel.setText( msg )




