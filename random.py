"""
Provides wrappers for several random number generators, giving them all a
common interface so that they can be used interchangeably in PyNN.

Note however that we have so far made no effort to implement parameter translation,
and parameter names/order may be different for the different RNGs.

$Id$
"""

import sys
import numpy.random
try:
    import pygsl.rng
except ImportError:
    print "Warning: GSL random number generators not available"
import time

# The following two functions taken from
# http://www.nedbatchelder.com/text/pythonic-interfaces.html
def _functionId(obj, nFramesUp):
    """ Create a string naming the function n frames up on the stack. """
    fr = sys._getframe(nFramesUp+1)
    co = fr.f_code
    return "%s.%s" % (obj.__class__, co.co_name)
 
def abstractMethod(obj=None):
    """ Use this instead of 'pass' for the body of abstract methods. """
    raise Exception("Unimplemented abstract method: %s" % _functionId(obj, 1))
 
 
class AbstractRNG:
    """Abstract class for wrapping random number generators. The idea is to be able
    to use either simulator-native rngs, which may be more efficient, or a
    standard python rng, e.g. a numpy.random.RandomState object, which would
    allow the same random numbers to be used across different simulators, or
    simply to read externally-generated numbers from files."""
    
    def __init__(self,seed=None):
        if seed:
            assert isinstance(seed,int)
        self.seed = seed
        # define some aliases
        self.random = self.next
        self.sample = self.next
    
    def next(self,n=1,distribution='uniform',parameters=[]):
        """Return n random numbers from the distribution.
        
        If n is 1, return a float, if n > 1, return a numpy array,
        if n <= 0, raise an Exception."""
        abstractMethod(self)

    
class NumpyRNG(AbstractRNG):
    """Wrapper for the numpy.random.RandomState class (Mersenne Twister PRNG)."""
    
    def __init__(self,seed=None):
        AbstractRNG.__init__(self,seed)
        self.rng = numpy.random.RandomState()
        if self.seed  :
            self.rng.seed(self.seed)
        else:
            self.rng.seed()
            
    def __getattr__(self, name):
        """This is to give NumpyRNG the same methods as numpy.random.RandomState."""
        return getattr(self.rng,name)
    
    def next(self,n=1,distribution='uniform',parameters=[]):
        """Return n random numbers from the distribution.
        
        If n is 1, return a float, if n > 1, return a numpy array,
        if n <= 0, raise an Exception."""
        if n > 1:
           return getattr(self.rng,distribution)(size=n,*parameters)
        elif n == 1:
            return getattr(self.rng,distribution)(size=1,*parameters)[0]
        else:
            raise ValueError, "The sample number must be positive"


class GSLRNG(AbstractRNG):
    """Wrapper for the GSL random number generators."""
       
    def __init__(self,seed=None,type='mt19937'):
        AbstractRNG.__init__(self,seed)
        self.rng = getattr(pygsl.rng,type)()
        if self.seed  :
            self.rng.set(self.seed)
        else:
            self.seed = int(time.time())
            self.rng.set(self.seed)
    
    def __getattr__(self, name):
        """This is to give GSLRNG the same methods as the GSL RNGs."""
        return getattr(self.rng,name)
    
    def next(self,n=1,distribution='uniform',parameters=[]):
        """Return n random numbers from the distribution.
        
        If n is 1, return a float, if n > 1, return a numpy array,
        if n <= 0, raise an Exception."""
        p = parameters + [n]
        return getattr(self.rng,distribution)(*p)

    
class NativeRNG(AbstractRNG):
    """Signals that the simulator's own native RNG should be used.
    Each simulator module should implement a class of the same name which
    inherits from this and which sets the seed appropriately."""
    pass


class RandomDistribution:
    """Class which defines a next(n) method which returns an array of n random
       numbers from a given distribution."""
       
    def __init__(self,rng=None,distribution='uniform',parameters=[]):
        self.name = distribution
        self.parameters = parameters
        if rng:
            assert isinstance(rng,AbstractRNG)
            self.rng = rng
        else: # use numpy.random.RandomState() by default
            self.rng = NumpyRNG()
        
    def next(self,n=1):
        """Return n random numbers from the distribution."""
        return self.rng.next(n=n,distribution=self.name,parameters=self.parameters)
        
