# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CadHelp
                                 A QGIS plugin
 Store and restore layer visibilities
                             -------------------
        begin                : 2012-12-26
        copyright            : (C) 2012 by Olivier Dalang
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

# Basic dependencies
from os.path import join, dirname

# Import the PyQt and QGIS libraries
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QTextBrowser, QVBoxLayout, QPushButton
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.core import *


class VectorBenderHelp(QtWidgets.QDialog):
    def __init__(self):
        QtWidgets.QDialog.__init__(self)
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)
        self.helpFile = join(dirname(__file__), "README.html")
        self.setWindowTitle("VectorBender")
        txt = QTextBrowser()
        txt.setReadOnly(True)
        txt.setSearchPaths([dirname(__file__)])
        txt.setOpenExternalLinks(True)
        txt.setText(open(self.helpFile, "r").read())
        cls = QPushButton("Close")
        cls.pressed.connect(self.accept)
        lay = QVBoxLayout()
        lay.addWidget(txt)
        lay.addWidget(cls)
        self.setLayout(lay)
