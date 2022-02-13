#!/usr/bin/env python3

import math
from decimal import Decimal
from .obdd import ObddManager, ObddNode
from .timer import Timer

class Classifier:
    """For representing Andy's linear classifier (neuron) format."""

    def __init__(self,name="none",size="0",weights=[],threshold="0"):
                 #num_values="2",prior="0",offset="0"):
        self.name = name
        self.size = size
        self.weights = weights
        self.threshold = threshold
        self.is_integer = self.check_integrality()
        # extra stuff from Andy's format
        #self.num_values = num_values
        #self.prior = prior
        #self.offset  = offset

    def __repr__(self):
        st = []
        st.append("name: %s" % self.name)
        st.append("size: %s" % self.size)
        st.append("weights: %s" % " ".join(self.weights))
        st.append("threshold: %s" % self.threshold)
        return "\n".join(st)

    def dict(self):
        return {
            "name": self.name,
            "size": self.size,
            "weights": list(self.weights),
            "threshold": self.threshold
        }

    def format_andy(self):
        st = []
        st.append( "%s\n" % self.name )
        st.append( "%s %s %s %s %s\n" % ( self.size,self.num_values,
                                          self.prior,self.threshold,
                                          self.offset ) )
        st.append( "%s\n" % " ".join(self.weights) )
        return "".join(st)

    @staticmethod
    def read_andy(filename):
        """Read Andy's neuron format (deprecated)"""
        with open(filename,'r') as f:
            lines = f.readlines()
        lines = [ line.strip() for line in lines ]
        name = lines[0]
        size,num_values,prior,threshold,offset = lines[1].split()
        weights = lines[2].split()
        neuron = { "name": name, "size": size,
                   "weights": weights,"threshold": threshold }
        return Classifier(**neuron)

    @staticmethod
    def parse(st):
        """Parse a neuron string format"""
        neuron = {}
        for line in st.split('\n'):
            if not line: continue
            field,value = line.split(':')
            field = field.strip()
            value = value.strip()
            neuron[field] = value
        assert "size" in neuron
        assert "threshold" in neuron # or "bias" in neuron
        assert "weights" in neuron
        neuron["weights"] = neuron["weights"].split()
        return Classifier(**neuron)

    @staticmethod
    def read(filename):
        """Read a neuron from file"""
        with open(filename,'r') as f:
            st = f.read()
        return Classifier.parse(st)

    def save(self,filename=None):
        if filename is None: filename = self.filename
        with open(filename,'w') as f:
            f.write(str(self))

    def _biggest_weight(self):
        biggest = 0
        for weight in self.weights:
            w = abs(float(weight))
            if w > biggest:
                biggest = w
        return biggest

    def check_integrality(self):
        weights = self.weights + [self.threshold]
        check = [ float(w).is_integer() for w in weights ]
        return sum(check) == len(check)

    def with_precision(self,digits):
        biggest = self._biggest_weight()
        scale = Decimal(biggest).adjusted()
        scale = -scale + digits-1
        scale = 10**scale
        new_weights = [ scale*float(weight) for weight in self.weights ]
        new_weights = [ str(int(weight)) for weight in new_weights ]
        new_threshold = str(int(scale*float(self.threshold)))
        neuron = self.dict()
        neuron["weights"] = new_weights
        neuron["threshold"] = new_threshold
        c = Classifier(**neuron)
        assert c.is_integer
        return c

    def _get_bounds(self):
        assert self.is_integer
        lower,upper = 0,0
        for weight in self.weights:
            weight = int(weight)
            if weight < 0:
                lower += weight
            else:
                upper += weight
        return (lower,upper)

    def _to_obdd(self,matrix):
        var_count = int(self.size)
        manager = ObddManager(var_count)
        one,zero = manager.one_sink(),manager.zero_sink()
        last_level = matrix[var_count+1]
        for node in last_level:
            last_level[node] = one if last_level[node] else zero
        for dvar in range(var_count,0,-1):
            level,next_level = matrix[dvar],matrix[dvar+1]
            for node in level:
                hi,lo = level[node] # get indices
                hi,lo = next_level[hi],next_level[lo] # get nodes
                level[node] = manager.new_node(dvar,hi,lo)
        return (manager,matrix[1][0])

    def compile(self):
        assert self.is_integer
        var_count = int(self.size)
        matrix = [ dict() for _ in range(var_count+2) ]
        matrix[1][0] = None # root node
        for i in range(1,var_count+1):
            level,next_level = matrix[i],matrix[i+1]
            weight = int(self.weights[i-1])
            for node in level:
                hi,lo = (node+weight,node)
                level[node] = (hi,lo) # (hi,lo)
                next_level[hi] = None
                next_level[lo] = None
        last_level = matrix[var_count+1]
        threshold = int(self.threshold)
        for node in last_level:
            last_level[node] = node >= threshold
        return self._to_obdd(matrix)

if __name__ == '__main__':
    precision = 2
    #filename = 'examples/169_wd2_0'
    #output_filename = 'examples/169_wd2_0-quantized'
    filename = 'examples/9_wd2_0'
    output_filename = 'examples/9_wd2_0-quantized'
    #filename = 'examples/test.nn'
    #output_filename = 'examples/test-quantized.nn'
    c = Classifier.read(filename)
    print(c)
    d = c.with_precision(precision)
    print(d)
    d.save(output_filename)
    with Timer("compiling"):
        obdd_manager,node = d.compile()
    with Timer("size"):
        count_before = len(list(node))
    with Timer("reducing"):
        node = node.reduce()
    with Timer("size"):
        count_after = len(list(node))
    print("node count before reduce: %d" % count_before)
    print(" node count after reduce: %d" % count_after)

    obdd_manager.save_vtree("tmp.vtree")
    obdd_manager.save_sdd("tmp.sdd",node)

    with Timer("to sdd"):
        offset = int(c.offset)
        sdd_manager,sdd_node = obdd_manager.obdd_to_sdd(node,offset=offset)
    with Timer("read sdd"):
        sdd_filename = b'tmp.sdd'
        alpha = sdd_manager.read_sdd_file(sdd_filename)

    print("sdd nodes/size: %d/%d" % (sdd_node.count(),sdd_node.size()))
    print("sdd nodes/size: %d/%d" % (alpha.count(),alpha.size()))
