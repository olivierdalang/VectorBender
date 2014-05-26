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
        self.setFocusPolicy(Qt.ClickFocus)
        #self.setWindowModality( Qt.ApplicationModal )

        self.iface = iface
        self.vb = vb

        # Connect the UI buttons
        self.createMemoryLayerButton.clicked.connect(self.createMemoryLayer)

        self.previewButton.pressed.connect(self.vb.showPreview)
        self.previewButton.released.connect(self.vb.hidePreview)
        self.editModeButton_toBendLayer.clicked.connect(self.toggleEditMode_toBendLayer)
        self.editModeButton_pairsLayer.clicked.connect(self.toggleEditMode_pairsLayer)
        self.runButton.clicked.connect(self.vb.run)

        # When those are changed, we recheck the requirements
        self.editModeButton_pairsLayer.clicked.connect(self.checkRequirements)
        self.editModeButton_toBendLayer.clicked.connect(self.checkRequirements)
        self.comboBox_toBendLayer.activated.connect( self.checkRequirements )
        self.pairsToPinsCheckBox.clicked.connect( self.checkRequirements )

        # When those are changed, we change the transformation type (which also checks the requirements)

        self.comboBox_toBendLayer.activated.connect( self.updateEditState_toBendLayer )
        self.comboBox_pairsLayer.activated.connect( self.updateEditState_pairsLayer )
        self.comboBox_pairsLayer.activated.connect( self.updateTransformationType )
        self.restrictBox_pairsLayer.stateChanged.connect( self.updateTransformationType )

        # Create an event filter to update when focus
        self.installEventFilter(self)

    def toBendLayer(self):
        layerId = self.comboBox_toBendLayer.itemData(self.comboBox_toBendLayer.currentIndex())
        return QgsMapLayerRegistry.instance().mapLayer(layerId)
    def pairsLayer(self):
        layerId = self.comboBox_pairsLayer.itemData(self.comboBox_pairsLayer.currentIndex())
        return QgsMapLayerRegistry.instance().mapLayer(layerId)
    def bufferValue(self):
        return self.bufferSpinBox.value()

    def updateEditState(self):
        if self.toBendLayer() is not None:
            self.toggleEditModeButton.setChecked( self.toBendLayer().isEditable() )

    def refreshStates(self):

        # Update the comboboxes
        self.updateLayersComboboxes()

        # Update the edit mode buttons
        self.updateEditState_pairsLayer()
        self.updateEditState_toBendLayer()

        # Update the transformation type
        self.updateTransformationType()



    def checkRequirements(self):
        # Checkin requirements
        self.runButton.setEnabled(False)

        tbl = self.toBendLayer()
        pl = self.pairsLayer()

        if tbl is None:
            self.displayMsg( "You must select a vector layer to bend !", True )
            return
        if pl is None:
            self.displayMsg( "You must select a vector (line) layer which defines the points pairs !", True )
            return
        if pl is tbl:
            self.displayMsg( "The layer to bend must be different from the pairs layer !", True )
            return            
        if not tbl.isEditable():
            self.displayMsg( "The layer to bend must be in edit mode !", True )
            return
        if not pl.isEditable() and self.pairsToPinsCheckBox.isChecked():
            self.displayMsg( "The pairs layer must be in edit mode if you want to change pairs to pins !", True )
            return
        if self.stackedWidget.currentIndex() == 0:
            self.displayMsg("Impossible to run with an invalid transformation type.", True)
            return
        self.displayMsg("Ready to go...")
        self.runButton.setEnabled(True)





    def updateLayersComboboxes(self):
        oldBendLayer = self.toBendLayer()
        oldPairsLayer = self.pairsLayer()

        self.comboBox_toBendLayer.clear()
        self.comboBox_pairsLayer.clear()
        for layer in self.iface.legendInterface().layers():
            if layer.type() == QgsMapLayer.VectorLayer:
                self.comboBox_toBendLayer.addItem( layer.name(), layer.id() )
                if layer.geometryType() == QGis.Line :
                    self.comboBox_pairsLayer.addItem( layer.name(), layer.id() )

        if oldBendLayer is not None:
            index = self.comboBox_toBendLayer.findData(oldBendLayer.id())
            self.comboBox_toBendLayer.setCurrentIndex( index )
        if oldPairsLayer is not None:
            index = self.comboBox_pairsLayer.findData(oldPairsLayer.id())
            self.comboBox_pairsLayer.setCurrentIndex( index )

    def updateEditState_pairsLayer(self):
        l = self.pairsLayer()
        self.editModeButton_pairsLayer.setChecked( False if (l is None or not l.isEditable()) else True )

    def updateEditState_toBendLayer(self):
        l = self.toBendLayer()
        self.editModeButton_toBendLayer.setChecked( False if (l is None or not l.isEditable()) else True )

    def updateTransformationType(self):
        tt = self.vb.determineTransformationType()
        self.stackedWidget.setCurrentIndex( tt )

        self.checkRequirements()




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

        index = self.comboBox_pairsLayer.findData(newMemoryLayer.id())
        self.comboBox_pairsLayer.setCurrentIndex( index )
        
        newMemoryLayer.startEditing()

    def toggleEditMode(self, checked, toBendLayer_True_pairsLayer_False):
        l = self.toBendLayer() if toBendLayer_True_pairsLayer_False else self.pairsLayer()
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
    def toggleEditMode_toBendLayer(self, checked):
        self.toggleEditMode(checked, True)
    def toggleEditMode_pairsLayer(self, checked):
        self.toggleEditMode(checked, False)

    def displayMsg(self, msg, error=False):
        if error:
            #QApplication.beep()
            msg = "<font color='red'>"+msg+"</font>"
        self.statusLabel.setText( msg )

    def eventFilter(self,object,event):
        if event.type() == QEvent.FocusIn:
            self.refreshStates()
        return False