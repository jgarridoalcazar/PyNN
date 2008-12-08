# encoding: utf-8
"""
PyNN-->NeuroML
$Id:$
"""

from pyNN import common
import math
#import numpy, types, sys, shutil
import xml.dom.minidom
import xml.dom.ext

neuroml_url = 'http://morphml.org'
namespace = {'xsi': "http://www.w3.org/2001/XMLSchema-instance",
             'mml':  neuroml_url+"/morphml/schema",
             'net':  neuroml_url+"/networkml/schema",
             'meta': neuroml_url+"/metadata/schema",
             'bio':  neuroml_url+"/biophysics/schema",  
             'cml':  neuroml_url+"/channelml/schema",}

# ==============================================================================
#   Utility classes
# ==============================================================================

class ID(common.IDMixin):
    """
    Instead of storing ids as integers, we store them as ID objects,
    which allows a syntax like:
        p[3,4].tau_m = 20.0
    where p is a Population object. The question is, how big a memory/performance
    hit is it to replace integers with ID objects?
    """
    
    def __init__(self, n):
        common.IDMixin.__init__(self, n)

# ==============================================================================
#   Module-specific functions and classes (not part of the common API)
# ==============================================================================

def build_node(name_, text=None, **attributes):
    # we call the node name 'name_' because 'name' is a common attribute name (confused? I am)
    ns, name_ = name_.split(':')
    if ns:
        node = xmldoc.createElementNS(namespace[ns], "%s:%s" % (ns, name_))
    else:
        node = xmldoc.createElement(name_)
    for attr, value in attributes.items():
        node.setAttribute(attr, str(value))
    if text:
        node.appendChild(xmldoc.createTextNode(text))
    return node

def build_parameter_node(name, value):
        param_node = build_node('bio:parameter', value=value)
        if name:
            param_node.setAttribute('name', name)
        group_node = build_node('bio:group', 'all')
        param_node.appendChild(group_node)
        return param_node

class IF_base(object):
    """Base class for integrate-and-fire neuron models."""        
    
    def define_morphology(self):
        segments_node = build_node('mml:segments')
        soma_node = build_node('mml:segment', id=0, name="Soma", cable=0)
        # L = 100  diam = 1000/PI: gives area = 10³ cm²
        soma_node.appendChild(build_node('mml:proximal', x=0, y=0, z=0, diameter=1000/math.pi))
        soma_node.appendChild(build_node('mml:distal', x=0, y=0, z=100, diameter=1000/math.pi))
        segments_node.appendChild(soma_node)
        
        cables_node   = build_node('mml:cables')
        soma_node = build_node('mml:cable', id=0, name="Soma")
        soma_node.appendChild(build_node('meta:group','all'))
        cables_node.appendChild(soma_node)
        return segments_node, cables_node
        
    def define_biophysics(self):
        # L = 100  diam = 1000/PI  // 
        biophys_node  = build_node(':biophysics', units="Physiological Units")
        ifnode        = build_node('bio:mechanism', name='IandF', type='Channel Mechanism')
        passive_node  = build_node('bio:mechanism', name='pas', type='Channel Mechanism')
        # g_max = 10⁻³cm/tau_m  // cm(nF)/tau_m(ms) = G(µS) = 10⁻⁶G(S). Divide by area (10³) to get factor of 10⁻³
        gmax = str(1e-3*self.parameters['cm']/self.parameters['tau_m'])
        passive_node.appendChild(build_parameter_node('gmax', gmax))
        cm_node       = build_node('bio:specificCapacitance')
        cm_node.appendChild(build_parameter_node('', str(self.parameters['cm'])))  # units?
        Ra_node       = build_node('bio:specificAxialResistance')
        Ra_node.appendChild(build_parameter_node('', "0.1")) # value doesn't matter for a single compartment
        esyn_node     = build_node('bio:mechanism', name="ExcitatorySynapse", type="Channel Mechanism")
        isyn_node     = build_node('bio:mechanism', name="InhibitorySynapse", type="Channel Mechanism")
        
        for node in ifnode, passive_node, esyn_node, isyn_node, cm_node, Ra_node: # the order is important here
            biophys_node.appendChild(node)
        return biophys_node
        
    def define_channel_types(self):
        ion_node     = build_node('cml:ion', name="non_specific",
                                  charge=1, default_erev=self.parameters['v_rest'])
        
        passive_node = build_node('cml:channel_type', name="pas", density="yes")
        passive_node.appendChild( build_node('meta:notes', "Simple example of a leak/passive conductance") )
        cvr_node = build_node('cml:current_voltage_relation')
        ohmic_node = build_node('cml:ohmic', ion="non_specific")
        gmax = str(1e-3*self.parameters['cm']/self.parameters['tau_m'])
        ohmic_node.appendChild( build_node('cml:conductance', default_gmax=gmax) )
        cvr_node.appendChild(ohmic_node)
        passive_node.appendChild(cvr_node)
        
        ifnode = build_node('cml:channel_type', name="IandF")
        ifnode.appendChild( build_node('meta:notes', "Spike and reset mechanism") )
        cvr_node = build_node('cml:current_voltage_relation')
        ifmech_node = build_node('cml:integrate_and_fire',
                                 threshold=self.parameters['v_thresh'],
                                 t_refrac=self.parameters['tau_refrac'],
                                 v_reset=self.parameters['v_reset'],
                                 g_refrac=0.1) # this value just needs to be 'large enough'
        cvr_node.appendChild(ifmech_node)
        ifnode.appendChild(cvr_node)
        
        return [ion_node, passive_node, ifnode]
            
    def define_synapse_types(self, synapse_type):
        esyn_node = build_node('cml:synapse_type', name="ExcitatorySynapse")
        esyn_node.appendChild( build_node('cml:%s' % synapse_type,
                                          max_conductance="1.0e-5",
                                          rise_time="1.0e-12",
                                          decay_time=self.parameters['tau_syn_E'],
                                          reversal_potential=self.parameters['e_rev_E'] ) )
        isyn_node = build_node('cml:synapse_type', name="InhibitorySynapse")
        isyn_node.appendChild( build_node('cml:%s' % synapse_type,
                                          max_conductance="1.0e-5",
                                          rise_time="1.0e-12",
                                          decay_time=self.parameters['tau_syn_I'],
                                          reversal_potential=self.parameters['e_rev_I'] ) )
        return [esyn_node, isyn_node]

    def build_nodes(self):
        cell_node = build_node(':cell', name=self.label)
        doc_node = build_node('meta:notes', "Instance of PyNN %s cell type" % self.__class__.__name__)
        segments_node, cables_node = self.define_morphology()
        biophys_node = self.define_biophysics()
        for node in doc_node, segments_node, cables_node, biophys_node:
            cell_node.appendChild(node)
        
        channel_nodes = self.define_channel_types()
        synapse_nodes = self.define_synapse_types(self.synapse_type)
        channel_nodes.extend(synapse_nodes)
        
        return cell_node, channel_nodes

# ==============================================================================
#   Standard cells
# ==============================================================================

class IF_curr_exp(common.IF_curr_exp):
    """Leaky integrate and fire model with fixed threshold and
    decaying-exponential post-synaptic current. (Separate synaptic currents for
    excitatory and inhibitory synapses"""
    
    def __init__(self, parameters):
        raise Exception('Cell type %s is not available in NeuroML' % self.__class__.__name__)

class IF_curr_alpha(common.IF_curr_alpha):
    """Leaky integrate and fire model with fixed threshold and alpha-function-
    shaped post-synaptic current."""
    
    def __init__(self, parameters):
        raise Exception('Cell type %s is not available in NeuroML' % self.__class__.__name__)

class IF_cond_exp(common.IF_cond_exp, IF_base):
    """Leaky integrate and fire model with fixed threshold and 
    decaying-exponential post-synaptic conductance."""
    
    n = 0
    translations = common.build_translations(*[(name, name)
                                               for name in common.IF_cond_exp.default_parameters])
    
    def __init__(self, parameters):
        common.IF_cond_exp.__init__(self, parameters)
        self.label = '%s%d' % (self.__class__.__name__, self.__class__.n)
        self.synapse_type = "doub_exp_syn"
        self.__class__.n += 1
        
class IF_cond_alpha(common.IF_cond_alpha, IF_base):
    """Leaky integrate and fire model with fixed threshold and alpha-function-
    shaped post-synaptic conductance."""
    
    n = 0
    translations = common.build_translations(*[(name, name)
                                               for name in common.IF_cond_alpha.default_parameters])
    
    def __init__(self, parameters):
        common.IF_cond_alpha.__init__(self, parameters)
        self.label = '%s%d' % (self.__class__.__name__, self.__class__.n)
        self.synapse_type = "alpha_syn"
        self.__class__.n += 1

class SpikeSourcePoisson(common.SpikeSourcePoisson):
    """Spike source, generating spikes according to a Poisson process."""

    def __init__(self, parameters):
        common.SpikeSourcePoisson.__init__(self, parameters)
        raise Exception('Cell type %s not yet implemented' % self.__class__.__name__)

class SpikeSourceArray(common.SpikeSourceArray):
    """Spike source generating spikes at the times given in the spike_times array."""

    def __init__(self, parameters):
        common.SpikeSourceArray.__init__(self, parameters)
        raise Exception('Cell type %s not yet implemented' % self.__class__.__name__)


# ==============================================================================
#   Functions for simulation set-up and control
# ==============================================================================

def setup(timestep=0.1, min_delay=0.1, max_delay=0.1, debug=False,**extra_params):
    """
    Should be called at the very beginning of a script.
    extra_params contains any keyword arguments that are required by a given
    simulator but not by others.
    """
    global xmldoc, xmlfile, populations_node, projections_node, inputs_node, cells_node, channels_node, neuromlNode
    xmlfile = extra_params['file']
    if isinstance(xmlfile, basestring):
        xmlfile = open(xmlfile, 'w')
    dt = timestep
    xmldoc = xml.dom.minidom.Document()
    neuromlNode = xmldoc.createElementNS(neuroml_url+'/neuroml/schema','neuroml')
    neuromlNode.setAttributeNS(namespace['xsi'],'xsi:schemaLocation',"http://morphml.org/neuroml/schema ../../Schemata/v1.5/Level3/NeuroML_Level3_v1.5.xsd")
    neuromlNode.setAttribute('lengthUnits',"micron")
    xmldoc.appendChild(neuromlNode)
    
    populations_node = build_node('net:populations')
    projections_node = build_node('net:projections', units="Physiological Units")
    inputs_node = build_node('net:inputs', units="Physiological Units")
    cells_node = build_node(':cells')
    channels_node = build_node(':channels', units="Physiological Units")
    
    for node in cells_node, channels_node, populations_node, projections_node, inputs_node:
        neuromlNode.appendChild(node)
        
def end(compatible_output=True):
    """Do any necessary cleaning up before exiting."""
    global xmldoc, xmlfile, populations_node, projections_node, inputs_node, cells_node, channels_node, neuromlNode
    # Remove empty nodes, otherwise the validator will complain
    for node in cells_node, channels_node, populations_node, projections_node, inputs_node:
        if not node.hasChildNodes():
            neuromlNode.removeChild(node)
    # Write the file
    xml.dom.ext.PrettyPrint(xmldoc, xmlfile)
    xmlfile.close()

def run(simtime):
    """Run the simulation for simtime ms."""
    pass # comment in NeuroML file

def setRNGseeds(seedList):
    """Globally set rng seeds."""
    raise Exception('Not yet implemented')

# ==============================================================================
#   Low-level API for creating, connecting and recording from individual neurons
# ==============================================================================

def create(cellclass, param_dict=None, n=1):
    """Create n cells all of the same type.
    If n > 1, return a list of cell ids/references.
    If n==1, return just the single id.
    """
    raise Exception('Not yet implemented')

def connect(source, target, weight=None, delay=None, synapse_type=None, p=1, rng=None):
    """Connect a source of spikes to a synaptic target. source and target can
    both be individual cells or lists of cells, in which case all possible
    connections are made with probability p, using either the random number
    generator supplied, or the default rng otherwise.
    Weights should be in nA or uS."""
    raise Exception('Not yet implemented')

def set(cells, cellclass, param, val=None):
    """Set one or more parameters of an individual cell or list of cells.
    param can be a dict, in which case val should not be supplied, or a string
    giving the parameter name, in which case val is the parameter value.
    cellclass must be supplied for doing translation of parameter names."""
    raise Exception('Not yet implemented')

def record(source, filename):
    """Record spikes to a file. source can be an individual cell or a list of
    cells."""
    pass # put a comment in the NeuroML file?

def record_v(source, filename):
    """Record membrane potential to a file. source can be an individual cell or
    a list of cells."""
    pass # put a comment in the NeuroML file?

# ==============================================================================
#   High-level API for creating, connecting and recording from populations of
#   neurons.
# ==============================================================================
    
class Population(common.Population):
    """
    An array of neurons all of the same type. `Population' is used as a generic
    term intended to include layers, columns, nuclei, etc., of cells.
    """
    
    n = 0
    
    def __init__(self, dims, cellclass, cellparams=None, label=None):
        """
        dims should be a tuple containing the population dimensions, or a single
          integer, for a one-dimensional population.
          e.g., (10,10) will create a two-dimensional population of size 10x10.
        cellclass should either be a standardized cell class (a class inheriting
        from common.StandardCellType) or a string giving the name of the
        simulator-specific model that makes up the population.
        cellparams should be a dict which is passed to the neuron model
          constructor
        label is an optional name for the population.
        """
        global populations_node, cells_node, channels_node
        common.Population.__init__(self, dims, cellclass, cellparams, label)
        self.label = self.label or 'Population%d' % Population.n
        self.celltype = cellclass(cellparams)
        Population.n += 1
        
        population_node = build_node('net:population', name=self.label)
        self.celltype.label = '%s_%s' % (self.celltype.__class__.__name__, self.label)
        celltype_node = build_node('net:cell_type', self.celltype.label)
        instances_node = build_node('net:instances')
        for i in range(self.size):
            x, y, z = self.positions[:, i]
            instance_node = build_node('net:instance', id=i)
            instance_node.appendChild( build_node('net:location', x=x, y=y, z=z) )
            instances_node.appendChild(instance_node)
            
        for node in celltype_node, instances_node:
            population_node.appendChild(node)
        
        populations_node.appendChild(population_node)

        cell_node, channel_list = self.celltype.build_nodes()
        cells_node.appendChild(cell_node)
        for channel_node in channel_list:
            channels_node.appendChild(channel_node)
            
class Projection(common.Projection):
    """
    A container for all the connections of a given type (same synapse type and
    plasticity mechanisms) between two populations, together with methods to set
    parameters of those connections, including of plasticity mechanisms.
    """
    
    n = 0
    
    def __init__(self, presynaptic_population, postsynaptic_population,
                 method='allToAll', method_parameters=None,
                 source=None, target=None, label=None, rng=None):
        """
        presynaptic_population and postsynaptic_population - Population objects.
        
        source - string specifying which attribute of the presynaptic cell signals action potentials
        
        target - string specifying which synapse on the postsynaptic cell to connect to
        If source and/or target are not given, default values are used.
        
        method - string indicating which algorithm to use in determining connections.
        Allowed methods are 'allToAll', 'oneToOne', 'fixedProbability',
        'distanceDependentProbability', 'fixedNumberPre', 'fixedNumberPost',
        'fromFile', 'fromList'
        
        method_parameters - dict containing parameters needed by the connection method,
        although we should allow this to be a number or string if there is only
        one parameter.
        
        rng - since most of the connection methods need uniform random numbers,
        it is probably more convenient to specify a RNG object here rather
        than within method_parameters, particularly since some methods also use
        random numbers to give variability in the number of connections per cell.
        """
        global projections_node
        common.Projection.__init__(self, presynaptic_population, postsynaptic_population, method, method_parameters, source, target, label, rng)
        self.label = self.label or 'Projection%d' % Projection.n
        connection_method = getattr(self,'_%s' % method)
        if target:
            self.synapse_type = target
        else:
            self.synapse_type = "ExcitatorySynapse"
        
        projection_node = build_node('net:projection', name=self.label)
        projection_node.appendChild( build_node('net:source', self.pre.label) )
        projection_node.appendChild( build_node('net:target', self.post.label) )
        
        synapse_node = build_node('net:synapse_props')
        synapse_node.appendChild( build_node('net:synapse_type', self.synapse_type) )
        synapse_node.appendChild( build_node('net:default_values', internal_delay=5, weight=1, threshold=-20) )
        projection_node.appendChild(synapse_node)
        
        projection_node.appendChild( connection_method(method_parameters) )
        
        projections_node.appendChild(projection_node)
        Projection.n += 1
        
        
    def _allToAll(self, parameters=None):
        """
        Connect all cells in the presynaptic population to all cells in the
        postsynaptic population.
        """
        allow_self_connections = True # when pre- and post- are the same population,
                                      # is a cell allowed to connect to itself?
        if parameters and parameters.has_key('allow_self_connections'):
            allow_self_connections = parameters['allow_self_connections']
        connectivity_node = build_node('net:connectivity_pattern')
        connectivity_node.appendChild( build_node('net:all_to_all', allow_self_connections=int(allow_self_connections)) )
        return connectivity_node
    
    def _oneToOne(self, parameters=None):
        """
        Where the pre- and postsynaptic populations have the same size, connect
        cell i in the presynaptic population to cell i in the postsynaptic
        population for all i.
        In fact, despite the name, this should probably be generalised to the
        case where the pre and post populations have different dimensions, e.g.,
        cell i in a 1D pre population of size n should connect to all cells
        in row i of a 2D post population of size (n, m).
        """
        connectivity_node = build_node('net:connectivity_pattern')
        connectivity_node.appendChild( build_node('net:one_to_one') )
        return connectivity_node
    
    def _fixedProbability(self, parameters, synapse_type=None):
        """
        For each pair of pre-post cells, the connection probability is constant.
        """
        allow_self_connections = True
        try:
            p_connect = float(parameters)
        except TypeError:
            p_connect = parameters['p_connect']
            if parameters.has_key('allow_self_connections'):
                allow_self_connections = parameters['allow_self_connections']
        connectivity_node = build_node('net:connectivity_pattern')
        connectivity_node.appendChild( build_node('net:fixed_probability',
                                                  probability=p_connect,
                                                  allow_self_conections=int(allow_self_connections)) )
        return connectivity_node
    
    def _distanceDependentProbability(self, parameters, synapse_type=None):
        """
        For each pair of pre-post cells, the connection probability depends on distance.
        d_expression should be the right-hand side of a valid python expression
        for probability, involving 'd', e.g. "exp(-abs(d))", or "float(d<3)"
        """
        raise Exception("Method not yet implemented")
    
    def __fixedNumber(self, parameters, direction):
        allow_self_connections = True
        if type(parameters) == types.IntType:
            n = parameters
            assert n > 0
            fixed = True
        elif type(parameters) == types.DictType:
            if parameters.has_key('n'): # all cells have same number of connections
                n = int(parameters['n'])
                assert n > 0
                fixed = True
            elif parameters.has_key('rand_distr'): # number of connections per cell follows a distribution
                rand_distr = parameters['rand_distr']
                assert isinstance(rand_distr, RandomDistribution)
                fixed = False
            if parameters.has_key('allow_self_connections'):
                allow_self_connections = parameters['allow_self_connections']
        elif isinstance(parameters, RandomDistribution):
            rand_distr = parameters
            fixed = False
        else:
            raise Exception("Invalid argument type: should be an integer, dictionary or RandomDistribution object.")
        if fixed:
            connectivity_node = build_node('net:connectivity_pattern')
            connectivity_node.appendChild( build_node('net:per_cell_connection',
                                                      num_per_source=n,
                                                      direction=direction,
                                                      allow_self_connections = int(allow_self_connections)) )
        else:
            raise Exception('Connection with variable connection number not implemented.')
    
    def _fixedNumberPre(self, parameters):
        """Each presynaptic cell makes a fixed number of connections."""
        return self.__fixedNumber(parameters,"PreToPost")

    def _fixedNumberPost(self, parameters):
        """Each postsynaptic cell receives a fixed number of connections."""
        return self.__fixedNumber(parameters,"PostToPre")
    
    def _fromFile(self, parameters):
        """
        Load connections from a file.
        """
        lines =[]
        if type(parameters) == types.FileType:
            fileobj = parameters
            # should check here that fileobj is already open for reading
            lines = fileobj.readlines()
        elif type(parameters) == types.StringType:
            filename = parameters
            # now open the file...
            f = open(filename,'r',1000)
            lines = f.readlines()
        elif type(parameters) == types.DictType:
            # dict could have 'filename' key or 'file' key
            # implement this...
            raise "Argument type not yet implemented"
        
        # We read the file and gather all the data in a list of tuples (one per line)
        input_tuples = []
        for line in lines:
            single_line = line.rstrip()
            src, tgt, w, d = single_line.split("\t", 4)
            src = "[%s" % src.split("[",1)[1]
            tgt = "[%s" % tgt.split("[",1)[1]
            input_tuples.append((eval(src), eval(tgt), float(w), float(d)))
        f.close()
        return self._fromList(input_tuples)
    
    def _fromList(self, conn_list):
        """
        Read connections from a list of tuples,
        containing [pre_addr, post_addr, weight, delay]
        where pre_addr and post_addr are both neuron addresses, i.e. tuples or
        lists containing the neuron array coordinates.
        """
        connections_node = build_node('net:connections')
        for i in xrange(len(conn_list)):
            src, tgt, weight, delay = conn_list[i][:]
            src = self.pre[tuple(src)]
            tgt = self.post[tuple(tgt)]
            connection_node = build_node('net:connection', id=i)
            connection_node.appendChild( build_node('net:pre', cell_id=src) )
            connection_node.appendChild( build_node('net:post', cell_id=tgt) )
            connection_node.appendChild( build_node('net:properties', internal_delay=delay, weight=weight) )
            connections_node.appendChild(connection_node)
        return connections_node
    
# ==============================================================================
#   Utility classes
# ==============================================================================
   
Timer = common.Timer  # not really relevant here except for timing how long it takes
                      # to write the XML file. Needed for API consistency.

# ==============================================================================
