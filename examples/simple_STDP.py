"""
Very simple STDP test

Andrew Davison, UNIC, CNRS
January 2008

$Id$
"""

import numpy
from pyNN.utility import get_script_args
sim_name = get_script_args(1)[0]
exec("from pyNN.%s import *" % sim_name)

setup(timestep=0.001, min_delay=0.1, max_delay=1.0, debug=True, quit_on_end=False)

p1 = Population(1, SpikeSourceArray(spike_times=numpy.arange(1, 50, 1.0)))
p2 = Population(1, IF_cond_exp())

stdp_model = STDPMechanism(timing_dependence=SpikePairRule(tau_plus=20.0, tau_minus=20.0),
                           weight_dependence=AdditiveWeightDependence(w_min=0, w_max=0.04,
                                                                      A_plus=0.01, A_minus=0.012))

connection_method = AllToAllConnector(weights=0.024, delays=0.2)
prj = Projection(p1, p2, method=connection_method,
                 synapse_dynamics=ComposedSynapseType(slow=stdp_model))


p1.record('spikes')
p2.record(('spikes', 'v'))
try:
    p2.record(('gsyn_exc', 'gsyn_inh'))
except Exception:
    pass


t = []
w = []

for i in range(60):
    t.append(run(1.0))
    w.extend(prj.get('weights', format='list'))
p1.write_data("Results/simple_STDP_1_%s.pkl" % sim_name)
p2.write_data("Results/simple_STDP_2_%s.pkl" % sim_name)

print w
f = open("Results/simple_STDP_%s.w" % sim_name, 'w')
f.write("\n".join([str(ww) for ww in w]))
f.close()

end()
