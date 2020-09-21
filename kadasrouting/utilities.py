# -*- coding: utf-8 -*-
import os

from io import StringIO
from html.parser import HTMLParser

from PyQt5.QtCore import QLocale, QCoreApplication, QSettings, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMessageBox, QApplication

from qgis.utils import iface
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    Qgis,
)

tr = lambda x: QCoreApplication.translate("", x)

def localeName():
    override_flag = QSettings().value(
        'locale/overrideFlag', True, type=bool)

    if override_flag:
        locale_name = QSettings().value('locale/userLocale', 'en_US', type=str)
    else:
        locale_name = QLocale.system().name()
        locale_name = str(locale_name).split('_')[0]

    return locale_name

def iconPath(name):
    return os.path.join(os.path.dirname(__file__), "icons", name)


def icon(name):
    return QIcon(iconPath(name))


def showMessageBox(text):
    QMessageBox.information(iface.mainWindow(), "Log", text)


def pushMessage(text):
    iface.messageBar().pushMessage(tr("Info"), text, level=Qgis.Info)


def pushWarning(text):
    iface.messageBar().pushMessage(tr("Warning"), text, level=Qgis.Warning)


def waitcursor(method):
    def func(*args, **kw):
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            return method(*args, **kw)
        except Exception as ex:
            raise ex
        finally:
            QApplication.restoreOverrideCursor()

    return func


def transformToWGS(crs):
    """
    Returns a transformer to WGS84

    :param old_crs: CRS to transform from
    :type old_crs: QgsCoordinateReferenceSystem

    :returns: transformer to use in various modules.
    :rtype: QgsCoordinateTransform
    """
    outCrs = QgsCoordinateReferenceSystem(4326)
    xformer = QgsCoordinateTransform(crs, outCrs, QgsProject.instance())

    return xformer


def _trans(value, index):
    """
    Copyright (c) 2014 Bruno M. Custódio
    Copyright (c) 2016 Frederick Jansen
    https://github.com/hicsail/polyline/commit/ddd12e85c53d394404952754e39c91f63a808656
    """
    byte, result, shift = None, 0, 0

    while byte is None or byte >= 0x20:
        byte = ord(value[index]) - 63
        index += 1
        result |= (byte & 0x1F) << shift
        shift += 5
        comp = result & 1

    return ~(result >> 1) if comp else (result >> 1), index


def decodePolyline6(expression, precision=6, is3d=False):
    """
    Copyright (c) 2014 Bruno M. Custódio
    Copyright (c) 2016 Frederick Jansen
    https://github.com/hicsail/polyline/commit/ddd12e85c53d394404952754e39c91f63a808656
    """
    coordinates, index, lat, lng, z, length, factor = [], 0, 0, 0, 0, len(
        expression), float(10 ** precision)

    while index < length:
        lat_change, index = _trans(expression, index)
        lng_change, index = _trans(expression, index)
        lat += lat_change
        lng += lng_change
        if not is3d:
            coordinates.append((lat / factor, lng / factor))
        else:
            z_change, index = _trans(expression, index)
            z += z_change
            coordinates.append((lat / factor, lng / factor, z / 100))

    return coordinates

def formatdist(d):
    if d is None:
        return ""
    return "{d:.1f} km".format(d=d/1000) if d > 1000 else "{d:.0f} m".format(d=d)


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.text = StringIO()
    def handle_data(self, d):
        self.text.write(d)
    def get_data(self):
        return self.text.getvalue()

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()
