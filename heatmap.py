import numpy as np
class Heatmap(object):
    """description of class"""
    heatMapValues = np.array( [[255,    0,    0],
                                [255,   36,    0],
                                [255,   73,    0],
                                [255,  109,    0],
                                [255,  146,    0],
                                [255,  182,    0],
                                [255,  219,    0],
                                [255,  255,    0],
                                [255,  255,   43],
                                [255,  255,   85],
                                [255,  255,  128],
                                [255,  255,  170],
                                [255,  255,  213],
                                [255,  255,  255]], dtype='float')/255.0
    @classmethod
    def getHeatmapValue(cls, v, minVal, maxVal):
        if v < minVal:
            v = minVal
        if v > maxVal:
            v = maxVal
        if (maxVal == minVal):
            m = -1
        else:
            m = float(v - minVal) / float(maxVal - minVal)
        idx = int(m*len(cls.heatMapValues))
        if idx == len(cls.heatMapValues):
            idx = -1
        return cls.heatMapValues[idx]





