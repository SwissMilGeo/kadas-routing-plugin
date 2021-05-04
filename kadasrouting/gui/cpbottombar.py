import os
import logging
import json

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor

from qgis.core import QgsWkbTypes, QgsProject, QgsVectorLayer
from qgis.utils import iface

from qgis.gui import QgsMapTool, QgsRubberBand
from kadasrouting.gui.valhallaroutebottombar import ValhallaRouteBottomBar
from kadasrouting.gui.drawpolygonmaptool import DrawPolygonMapTool
from kadasrouting.utilities import pushWarning, transformToWGS

# Royal Blue
PATROL_AREA_COLOR = QColor(65, 105, 225)

WIDGET, BASE = uic.loadUiType(os.path.join(os.path.dirname(__file__), "cpbottombar.ui"))

LOG = logging.getLogger(__name__)


class CPBottomBar(ValhallaRouteBottomBar, WIDGET):
    def __init__(self, canvas, action, plugin):
        self.default_layer_name = "Patrol"
        self.patrolArea = None
        self.patrolFootprint = self.createFootprintArea(color = PATROL_AREA_COLOR)
        super().__init__(canvas, action, plugin)
        
        self.btnPatrolAreaClear.clicked.connect(self.clearPatrol)
        self.btnPatrolAreaCanvas.toggled.connect(self.setPatrolPolygonDrawingMapTool) # todo: use new instance of drawing tool
        
        self.radioPatrolAreaPolygon.toggled.connect(self._radioButtonsPatrolChanged)
        self.radioPatrolAreaLayer.toggled.connect(self._radioButtonsPatrolChanged)
    
    def populatePatrolLayerSelector(self):
        self.comboPatrolAreaLayers.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.geometryType() == QgsWkbTypes.PolygonGeometry
            ):
                self.comboPatrolAreaLayers.addItem(layer.name(), layer)

    def setPatrolPolygonDrawingMapTool(self, checked):
        if checked:
            self.prevMapTool = iface.mapCanvas().mapTool()
            self.mapToolDrawPolygon = DrawPolygonMapTool(iface.mapCanvas())
            self.mapToolDrawPolygon.polygonSelected.connect(
                self.setPatrolAreaFromPolygon
            )
            iface.mapCanvas().setMapTool(self.mapToolDrawPolygon)
        else:
            try:
                iface.mapCanvas().setMapTool(self.prevMapTool)
            except Exception as e:
                LOG.error(e)
                iface.mapCanvas().setMapTool(QgsMapToolPan(iface.mapCanvas()))

    def clearPatrolArea(self):
        self.patrolArea = None
        self.patrolFootprint.reset(QgsWkbTypes.PolygonGeometry)

    def setPatrolAreaFromPolygon(self, polygon):
        self.patrolArea = polygon
        self.patrolFootprint.setToGeometry(polygon)

    def _radioButtonsPatrolChanged(self):
        self.populatePatrolLayerSelector()
        self.comboPatrolAreaLayers.setEnabled(self.radioPatrolAreaLayer.isChecked())
        self.btnPatrolAreaCanvas.setEnabled(
            self.radioPatrolAreaPolygon.isChecked()
        )
        self.btnPatrolAreaClear.setEnabled(self.radioPatrolAreaPolygon.isChecked())
        if self.radioPatrolAreaPolygon.isChecked():
            if self.patrolArea is not None:
                self.patrolFootprint.setToGeometry(self.patrolArea)
        else:
            self.patrolFootprint.reset(QgsWkbTypes.PolygonGeometry)

    def clearPatrol(self):
        self.patrol = None
        self.patrolFootprint.reset(QgsWkbTypes.PolygonGeometry)

    def prepareValhalla(self):
        layer, points, profile, allAreasToAvoidWGS, costingOptions = super().prepareValhalla()
        if self.radioPatrolAreaPolygon.isChecked():
            # Currently only single polygon is accepted
            patrolArea = self.patrolArea
            canvasCrs = self.canvas.mapSettings().destinationCrs()
            transformer = transformToWGS(canvasCrs)
            if patrolArea is None:
                # if the custom polygon button is checked, but no polygon has been drawn
                pushWarning(
                    self.tr("Custom polygon button is checked, but no polygon is drawn")
                )
                return
        elif self.radioPatrolAreaLayer.isChecked():
            avoidLayer = self.comboPatrolAreaLayers.currentData()
            if avoidLayer is not None:
                layerCrs = avoidLayer.crs()
                transformer = transformToWGS(layerCrs)
                patrolArea = [f.geometry() for f in avoidLayer.getFeatures()]
            else:
                # If polygon layer button is checked, but no layer polygon is selected
                pushWarning(
                    self.tr(
                        "Polygon layer button is checked, but no layer polygon is selected"
                    )
                )
                return
        else:
            # No areas to avoid
            patrolArea = None
            patrolAreaWGS = None
            allPatrolAreaWGS = None

        # transform to WGS84 (Valhalla's requirement)
        allPatrolAreaWGS = []
        if patrolArea:
            for patrolAreaGeom in patrolArea:
                patrolAreaJson = json.loads(patrolAreaGeom.asJson())
                patrolAreaWGS = []
                for i, polygon in enumerate(patrolAreaJson["coordinates"]):
                    patrolAreaWGS.append([])
                    for point in polygon:
                        pointWGS = transformer.transform(point[0], point[1])
                        patrolAreaWGS[i].append([pointWGS.x(), pointWGS.y()])
                allPatrolAreaWGS.extend(patrolAreaWGS)
        return layer, points, profile, allAreasToAvoidWGS, costingOptions, allPatrolAreaWGS

    def calculate(self):
        layer, points, profile, allAreasToAvoidWGS, costingOptions, allPatrolAreaWGS = self.prepareValhalla()
        try:
            layer.updateRoute(points, profile, allAreasToAvoidWGS, costingOptions, allPatrolAreaWGS)
            self.btnNavigate.setEnabled(True)
        except Exception as e:
            LOG.error(e, exc_info=True)
            # TODO more fine-grained error control
            pushWarning(self.tr("Could not compute route"))
            LOG.error("Could not compute route")
            raise (e)

