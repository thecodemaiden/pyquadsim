import gc
import numpy as np
import threading
import Queue as queue
from multiprocessing.pool import ThreadPool
from collections import defaultdict
import itertools as it
from random import random
import ode

def fixPhase(a):
    return ( a + np.pi) % (2 * np.pi ) - np.pi

class FieldObject(object):
    def getPosition(self):
        pass
    def getRadiatedValues(self):
        # freq, power, t
        return [(None, None, None)]
    def getMaxRadiatedValue(self):
        return None # DUNNO
    def detectField(self, fieldValue):
        """Register any readings, if necessary. fieldvalue is a FieldSphere
           Return True if this wave was handled, False otherwise (and it may show up again) """
        return False

class FieldSphere(object):
    startR = 0.00001
    def __init__(self, center, speed, frequency, totalPower, startTime, data=None):
        # TODO: waves have wavelengths
        self.totalPower = totalPower
        self.center = tuple(center)
        self.radius = self.startR # TODO: make this an epsilon?
        self.lastRadius = 0
        self.intensity = None# LOL wut
        self.data = data
        self.t1 = startTime
        self.center_2 = sum([k*k for k in self.center])
        self.obj_distances = {}
        self.speed = speed
        self.isPlanar = False
        self.frequency = frequency
        self.intensity_factor = 1.0
        self.original = None
        self.destroyFlag = False
        self.phaseShift = 0
        self.onSurface = [0,0,0,0] # [a, b, c, d] for ax+by+cz = d
        self.reflect_limits = [[-np.inf, np.inf], [-np.inf, np.inf], [-np.inf, np.inf]] 


    def reflectOffSurface(self, surf_coord, surf_at, surf_depth):
        # first get the vector from our source to the surface
        # so we can reflect ourselves on the other side of that
        t = surf_depth


        test_limits = self.reflect_limits[surf_coord]

        if self.center[surf_coord] < surf_at:
            if t<0 or t>self.radius:
                return None
        else:
            if t>0 or -t>self.radius:
                return None

        if surf_at <= test_limits[0] or surf_at >= test_limits[1]:
            # we did
            return None

        # update the reflection limits
        if surf_at < self.center[surf_coord]:
            # we won't reflect anywhere < this
            test_limits[0] = surf_at
        elif surf_at > self.center[surf_coord]:
            test_limits[1] = surf_at
        else:
            return None # no edge reflections for now

        reflectPos = list(self.center)
        reflectPos[surf_coord] += 2*t

        dt = t/self.frequency

        reflected = FieldSphere(reflectPos, self.speed, self.frequency, self.totalPower, self.t1, self.data)
        reflected.radius = self.radius
        reflected.intensity = self.intensity
        reflected.intensity_factor = 0.5
        self.intensity_factor = 0.75
        reflected.original = self
        reflected.phaseShift = np.pi
        reflected.reflect_limits = self.reflect_limits

        return reflected

    def prepareToDiscard(self, t):
        self.lastRadius = self.radius
        self.radius = self.speed*(t-self.t1)
       
        if self.radius > 0:
            self.intensity = self.totalPower/(4*np.pi*self.radius*self.radius)
            self.intensity *= self.intensity_factor


    def calculate(self, obj, obj_pos, obj_pos_sq):
        x1, y1, z1 = self.center
        x,y,z = obj_pos

        order2 = 2*x*x1 + 2*y*y1 + 2*z*z1
       
        newDist = obj_pos_sq + self.center_2 - order2
        oldDist = self.obj_distances.get(obj, newDist)

        self.obj_distances[obj] = newDist

        if (self.radius*self.radius >= newDist) and (self.lastRadius*self.lastRadius < oldDist):
            return True
        return False

    @classmethod
    def copyAtT(cls, oldS, t, speed):
        newS =  cls(oldS.center, oldS.speed, oldS.frequency, oldS.totalPower, oldS.t1)
        newS.radius = speed*(t-oldS.t1)
        newS.phaseShift = oldS.phaseShift
        newS.data = oldS.data
        newS.original = oldS.original
        if newS.radius > 0:
            newS.intensity = newS.totalPower/(newS.radius*newS.radius)
            newS.intensity *= oldS.intensity_factor

        return newS

class RayField(object):
    def __init__(self, propSpeed, minIntensity=1e-10):
        self.objects = {}
        self.speed = float(propSpeed)
        self.minI = minIntensity
        self.dPhi = 5
        self.dTheta = 5
        self.environment = None
        # pick a default value for reception sphere; see if we can speed this up later
        self.receptionSize = 0.1
        self.objectLookup = {} # TODO: empty this at intervals?

    def addObject(self, o):
        self.objects[o] = []
        if self.environment is None:
            self.environment = o.environment
        elif self.environment != o.environment:
            raise RuntimeError('Objects in diferent environments')

    def removeObject(self, o):
        self.objects.pop(o, None)

    def prepareObjectSpace(self):
        # create a reception sphere for each receiving object
        # attach the sensor information to the reception sphere
        objectSpace = ode.HashSpace()
        for o in self.objects:
            recepSphere = ode.GeomSphere(objectSpace, self.receptionSize)
            recepShere.obj = o
            recepSphere.setPosition(o.getPosition())
        return objectSpace


    def createRaysForObject(self, o, emissionTimes, now, space):
        rayList = []
        origin = o.getPosition()
        # for now, just generate 8 rays:
        # radiating to cube corners
        directions = [(1,1,1), (-1,-1,-1), (1,1,-1), (-1,-1,1), (1,-1,1), (-1,1,-1), (-1, 1,1), (1, -1, -1)]
        for et in emissionTimes:
            for d in directions:
                (t,pw) = et
                radius = self.speed*(now-t)
                newRay = ode.GeomRay(space, radius)
                newRay.set(origin, d)
                newRay.intensity = pw
                newRay.source = o # attach source to ray so we can eliminate multiple hits on reception spheres
                #newRay = FieldRay(radius,  origin, d, pw, space)
                rayList.append(newRay)
        
        return rayList

    def handleReflectionForRays(self, rayContacts):
        # determine if we are making more reflections, and if there are intersections with objects
        newRayList = []
        newRaySpace = ode.HashSpace()
        intersectionList = defaultdict(list)
        for ray, contactList in rayContacts.items():
            for contact in contactList:
                pos, normal, depth, g1, g2 = contact.getContactGeomParams()
                # is it in our object list? then we need to record this intersection
                obj = self.environment.getObjectFromGeom(g2)
                sensor = self.findSensorForObject(obj)
                if sensor is not None:
                    # don't be intersected by rays coming from us...
                    if ray.getPosition() != sensor.getPosition():
                        intersectionList[sensor].append(ray)
                else:
                    try:
                        if obj.isObstacle:
                            # reflect
                            reflectDir = normal
                            reflectFrom = pos
                            newLength = ray.getLength() - depth
                            newRay = ode.GeomRay(newRaySpace, newLength)
                            newRay.set(reflectFrom, reflectDir)
                            newRay.intensity = ray.intensity
                            newRayList.append(newRay)
                    except AttributeError:
                        pass
                    # is it an obstacle?

        return newRayList, newRaySpace, intersectionList

    def update(self, now):
        allObjects = self.objects.iterkeys()
        raySpace = ode.HashSpace()
        allRays = []
        worldSpace = None
        self.currentRayContacts = defaultdict(list)
        for o in allObjects:
            emissionTimes = self.objects[o]
            keptTimes = []
 
            # remove emissions that fall below our minimum intensity
            for (t, power) in emissionTimes:
                distance = self.speed*(now-t)
                intensity = power / (4*np.pi*distance*distance)
                if intensity >= self.minI:
                    keptTimes.append(t,intensity)

            # add new emissions if any
            allNew = o.getRadiatedValues()
            for info in allNew:
                if info is None or info[0] <= 0 or info[1] <= 0:
                    continue
                freq, power, t = info
                keptTimes.append((t, power)) # we will deal with freq later when basic raycasting works

            # new list of emissions is complete
            emissionTimes = keptTimes

            # create the rays
            rayList = self.createRaysForObject(o, emissionTimes, now, raySpace)
            allRays += rayList

            # all objects should be in the same world, so grab the space
            if worldSpace is None:
                worldSpace = o.environment.space

        nReflections = 2
        allIntersections = defaultdict(list)
        for _ in range(nReflections):
            # perform the ray-object intersections
            ode.collide2(raySpace, worldSpace, None, self._rayCollideCallback)
            if len(self.currentRayContacts) > 0:
                newRayList, raySpace, newIntersections = self.handleReflectionForRays(self.currentRayContacts)
            else:
                break #no reflections or intersections means we are done
            # add in the newInterstections
            for k,v in newIntersections.items():
                allIntersections[k] += v
        # ok, we're done, now to handle interference and sensing
        for sensor, rays in allIntersections.items():
            chosen = rays[0]
            sensor.detectField(chosen)


    def _rayCollideCallback(self, args, geom1, geom2):
        contacts = ode.collide(geom1, geom2)
        if len(contacts) > 0:
            if isinstance(geom1, ode.GeomRay):
                theRay = geom1
            elif isinstance(geom2, ode.GeomRay):
                raise RuntimeError('I didn''t think ray==geom2 was possible')
            self.currentRayContacts[theRay]+=(contacts)

    def combineValues(self, rayList):
        return sphereList[0]
             
class Field(object):
    sharedThreadPool = ThreadPool(4) 
    def __init__(self, propSpeed, minI=1e-10, planeEquation=None):
        # TODO: replace with sphereList, mapping sphere to producing object
        self.objects = {}
        self.speed = float(propSpeed)
        self.minI = minI
        self.planeEq = planeEquation

    def addObject(self, o):
        self.objects[o] = []

    def removeObject(self, o):
        self.objects.pop(o, None)

    def _sphereGenerator(self):
        for sphereList in self.objects.itervalues():
            for s in sphereList:
                yield s

    def _intersectionThreaded(self, args):
        s = args[0]
        info = args[1]
        intersectInfo = {}
        if s.intensity is not None:
            for o in self.objects:
                objInfo = info[o]
                if s.calculate(o, objInfo[0], objInfo[1]):
                    dPos = np.subtract(objInfo[0], s.center)
                    dt = np.linalg.norm(dPos)/self.speed
                    properCopy = FieldSphere.copyAtT(s, s.t1+dt, self.speed)
                    properCopy.tArr = s.t1+dt
                    intersectInfo[o] = properCopy
        return intersectInfo

    def performIntersections(self, t):
        '''We need to go through all spheres and find intersections between objects and spheres with radius>0'''
        # assumes waaay more spheres than objects
        # TODO: octree or other representation to limit comparisons

        extraSpheres = self.intersectObstacles(self.environment.obstacleList)


        # precalculate obj. info
        objInfoTable = {}
        for o in self.objects:
            pos = o.getPosition()
            pos2 = sum([k*k for k in pos])
            objInfoTable[o] = (pos, pos2)

        repeatInfo = it.repeat(objInfoTable)
        origSpheresList = self._sphereGenerator()
        allSpheresList = it.chain(origSpheresList, extraSpheres)
        together = it.izip(allSpheresList, repeatInfo)
        allIntersections = it.imap(self._intersectionThreaded, together)
        #allIntersections = self.sharedThreadPool.imap_unordered(self._intersectionThreaded, together, 16)
        # now take the collisions and order them by object
        intersectionsByObject = defaultdict(list)
        for intersect in allIntersections:
            for o in intersect:
                intersectionsByObject[o].append(intersect[o])
        for o,sList in intersectionsByObject.items():
            # TODO: combine wavefronts that interfere
            newWave = self.combineValues(sList)
            o.detectField(newWave)
           

    def _obstacleThreaded(self, args):
        s = args[0]
        obs = args[1]
        bounceList = []
        # check for the closest surfaces
        # in future, more checks needed
        # TODO: make this prettier
        selected = {}
        for f in obs.faces:
            key = f[0]
            at = f[1]
            t = -s.center[key] + at
            if key not in selected:
                selected[key] = (f[0], f[1], t)
            else:
                otherT = selected[key][2]
                if abs(otherT) > t:
                    selected[key] = (f[0],f[1],t)

        for v in selected.values():
            bounceList.append(s.reflectOffSurface(*v))
        bouncy = [i for i in bounceList if i is not None]
        return bouncy       

    def intersectObstacles(self, obsList):
        allCombo = it.product(self._sphereGenerator(), obsList)
        reflections = it.imap(self._obstacleThreaded, allCombo)
        #reflections = self.sharedThreadPool.imap_unordered(self._obstacleThreaded, allCombo, 16)   
        return it.chain.from_iterable(reflections)
             
    def update(self, now):
        # TODO: modify in-place
        allObjects = self.objects.iterkeys()
        for o in allObjects:
            sphereList = self.objects[o]
            newSpheres = self.spawnSphereFromObject(o) # TODO: check frequency!
            for newSphere in newSpheres:
                newSphere.obj_distances[o] = 0
                sphereList.append(newSphere)
            for s in sphereList:
                s.prepareToDiscard(now)
        self.performIntersections(now)
        allObjects = self.objects.iterkeys()
        for o in allObjects:
            toRemove = []
            sphereList = self.objects[o]
            for s in sphereList:
                if s.intensity is not None and s.intensity < self.minI:
                    if s.destroyFlag:
                        toRemove.append(s)
                    else:
                        s.destroyFlag = True
            newList = [s for s in sphereList if s not in toRemove]
            self.objects[o] = newList

    def spawnSphereFromObject(self, o):
        sphereList = []
        allNew = o.getRadiatedValues()
        for info in allNew:
            if info is None or info[0] <= 0 or info[1] <= 0:
                continue
            freq, power, t = info
            newSphere = FieldSphere(o.getPosition(), self.speed, freq, power, t)
            sphereList.append(newSphere)
        return sphereList

    def combineValues(self, sphereList):
        return sphereList[0]

class VectorField(Field):
    # TODO: real vector shit
    def __init__(self, propSpeed, minIntensity):
        super(VectorField, self).__init__(propSpeed)
        self.minI = float(minIntensity)

class SemanticField(Field):
    def __init__(self, propSpeed, minIntensity):
        super(SemanticField, self).__init__(propSpeed)
        self.minI = float(minIntensity)

    def combineValues(self, sphereList):
        amplitudes, phases = zip(*[(np.sqrt(s.intensity), (2*np.pi*s.radius*s.frequency + s.phaseShift)) for s in sphereList])
        polard = np.multiply(amplitudes, np.exp(1j*np.array(phases)))

        probs = np.abs(np.real(polard))
        probs = probs/np.sum(probs)
        selector = 0

        p = random()
        for i in range(len(probs)):
            selector += probs[i]
            if p < selector:
                break

        chosen = sphereList[i]

        strongest = sphereList[amplitudes.index(max(amplitudes))]
        polar_sum = np.sum(polard)
        newAmplitude = np.abs(np.real(polar_sum))
        newIntensity = newAmplitude*newAmplitude

        newSphere = FieldSphere((0,0,0), 0, 0, 0, 0, chosen.data)
        newSphere.intensity = newIntensity

        return newSphere

    def spawnSphereFromObject(self, o):
        sphereList = []
        allNew = o.getRadiatedValues()
        for info in allNew:
            if info is None or info[0] is None:
                continue
            freq, val, t = info[0]
            data = info[1]
            newSphere = FieldSphere(o.getPosition(), self.speed, freq, val, t, data)
            sphereList.append(newSphere)
        return sphereList