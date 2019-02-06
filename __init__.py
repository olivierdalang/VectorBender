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
 This script initializes the plugin, making it known to QGIS.
"""
def classFactory(iface):
    # load VectorBender class from file VectorBender
    from .vectorbender import VectorBender
    return VectorBender(iface)
