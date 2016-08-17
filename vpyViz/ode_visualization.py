from ode_objects import *
import ode
import visual as v
import visual.controls as vc
from operator import eq
import logging
import time

class Vpy_Visualization():
    def __init__(self, physicalEnvironment):
        self.logger = logging.getLogger(name='Quadsim.Visualizer')
        self.physEnv = physicalEnvironment
        self.obj = set()
        self.simFrames = 0
        self.objUpdates = 0
        self.canvas = v.display(title='Simulation', width=640, height=480)
        self.canvas.select()
        self.controls = vc.controls(x=640, y=0, range=20)
        self.infoLabel = v.label(display=self.controls.display,pos=(-10,-10), text='Click simulation to start', line=False)
        self.lastFPSCheckTime = None
        self.lastFPS = 0.0
        self.simTime = 0.0

    def updateLabel(self):
        now = time.time()
        elapsed = now - self.startTime
        labelFormat = 'Real time: {:4.2f}\nSim time: {:4.2f}\nFPS: {:4.2f}'
        if self.lastFPSCheckTime is None:
            self.lastFPSCheckTime = self.startTime
        elif self.simFrames % 60 == 0:
            self.lastFPS = 60.0/(now - self.lastFPSCheckTime)
            self.lastFPSCheckTime = now
        self.infoLabel.text = labelFormat.format(elapsed, self.simTime, self.lastFPS)

    def create(self):
        space = self.physEnv.space
        for i in range(space.getNumGeoms()):
            geom = space.getGeom(i)
            self.addGeom(geom)

    def update(self, dt):
        for obj in self.obj:
            obj.update()
            #self.objUpdates +=1
        self.simFrames +=1 
        self.simTime += dt
        self.updateLabel()
        v.rate(200)

    def getGraphics(self, geom):
        for o in self.obj:
            if eq(o.geom, geom):
                return o.src

    def extractObj(self, geom, ident):
        obj = None
        # Box
        if type(geom) == ode.GeomBox:
            obj = Vpy_Box(geom, ident, self.canvas)
        # Sphere
        elif type(geom) == ode.GeomSphere:
            obj = Vpy_Sphere(geom, ident, self.canvas)
        # Plane
        elif type(geom) == ode.GeomPlane:
            obj = Vpy_Plane(geom, ident, self.canvas)
        # Ray
        elif type(geom) == ode.GeomRay:
            obj = Vpy_Ray(geom, ident, self.canvas)
        # TriMesh
        elif type(geom) == ode.GeomTriMesh:
            obj = Vpy_TriMesh(geom, ident, self.canvas)
        # Cylinder
        elif type(geom) == ode.GeomCylinder:
            obj = Vpy_Cylinder(geom, ident, self.canvas)
        # Capsule
        elif type(geom) == ode.GeomCapsule:
            obj = Vpy_Capsule(geom, ident, self.canvas)
        # CappedCylinder
        elif type(geom) == GeomCCylinder:
            obj = Vpy_Capsule(geom, ident, self.canvas)
        elif type(geom) == ode.GeomTransform:
            obj = self.extractObj(geom.getGeom(), ident)
            obj = Vpy_Transform(geom, obj, ident, self.canvas)

        return obj

    def addGeom(self, geom, ident=None):
        obj = self.extractObj(geom, ident)
        if obj:
            obj.update()
            self.obj.add(obj)

            
