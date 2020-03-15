#!/usr/bin/env python3

import os
from .linear import Classifier

class Gate:
    def __init__(self,node_id):
        self.node_id = node_id
        self.node_vars = None
        self._bit = False # internal bit field
        self._data = None
        self._ref_count = None
        self._negated = None

    def is_input(self):
        """Returns true if node is a literal, and false otherwise"""
        return isinstance(self,Literal)

    def is_gate(self):
        """Returns true if node is internal, and false otherwise"""
        return not isinstance(self,Literal)

    def is_false(self):
        """Returns true if node is FALSE, and false otherwise"""
        return isinstance(self,OrGAte) and len(self.children) == 0

    def is_true(self):
        """Returns true if node is TRUE, and false otherwise"""
        return isinstance(self,AndGate) and len(self.children) == 0

    def count(self):
        node_count = 0
        for node in self:
            node_count += 1
        return node_count

    def size(self):
        edge_count = 0
        for node in self:
            if node.is_gate():
                edge_count += len(node.children)
        return edge_count

    def count_and_size(self):
        node_count,edge_count = 0,0
        for node in self:
            node_count += 1
            if node.is_gate():
                edge_count += len(node.children)
        return (node_count,edge_count)

    def negate(self,manager):
        pass

    def is_model(self,inst,clear_bits=True):
        # inst is a map: var_index -> {0,1}
        if self._bit is True: return self._data
        self._bit = True
        sat = self._is_model(inst)
        self._data = sat
        if clear_bits:
            self.clear_bits(clear_data=True)
        return sat


    ########################################
    # TRAVERSAL
    ########################################

    def __iter__(self,marker=True,clear_data=False,clear_bits=True):
        """post-order (children before parents) generator"""
        if self._bit is marker: return
        self._bit = marker

        if self.is_gate():
            for child in self.children:
                for node in child.__iter__(marker=marker,clear_bits=False):
                    yield node
        yield self

        if clear_bits:
            self.clear_bits(clear_data=clear_data)

    def clear_bits(self,clear_data=False):
        """clears bits set by recursive traversal"""
        for node in self.__iter__(marker=False,clear_bits=False):
            if clear_data: node._data = None


class Literal(Gate):
    def __init__(self,node_id,literal):
        Gate.__init__(self,node_id)
        self.literal = literal
        self.var = literal if literal > 0 else -literal
        self.val = 1 if literal > 0 else 0

    def __repr__(self):
        st = 'L %d' % self.literal
        return st

    def negate(self,manager):
        if self._negated is not None: return self._negated
        self._negated = manager.new_node(Literal,literal=-self.literal)
        self._negated._negated = self
        return self._negated

    def _is_model(self,inst):
        # inst is a map: var_index -> {0,1}
        sat = inst[self.var] == self.val
        return 1 if sat else 0


class AndGate(Gate):
    def __init__(self,node_id,children):
        Gate.__init__(self,node_id)
        self.children = children

    def __repr__(self):
        child_ids = [ str(child.node_id) for child in self.children ]
        st = 'A %d %s' % (len(self.children), " ".join(child_ids))
        return st

    def negate(self,mgr):
        if self._negated is not None: return self._negated
        negated_children = [ child.negate(mgr) for child in self.children ]
        self._negated = mgr.new_node(OrGate,children=negated_children)
        self._negated._negated = self
        return self._negated

    def _is_model(self,inst):
        # inst is a map: var_index -> {0,1}
        sat = 1
        for child in self.children:
            if not child.is_model(inst,clear_bits=False):
                sat = 0
                break
        return sat


class OrGate(Gate):
    def __init__(self,node_id,children,decision_var=0):
        Gate.__init__(self,node_id)
        self.children = children
        self.decision_var = decision_var

    def __repr__(self):
        child_ids = [ str(child.node_id) for child in self.children ]
        st = 'O %d %d %s' % (self.decision_var, \
                             len(self.children), " ".join(child_ids))
        return st

    def negate(self,mgr):
        if self._negated is not None: return self._negated
        negated_children = [ child.negate(mgr) for child in self.children ]
        self._negated = mgr.new_node(AndGate,children=negated_children)
        self._negated._negated = self
        return self._negated

    def _is_model(self,inst):
        # inst is a map: var_index -> {0,1}
        sat = 0
        for child in self.children:
            if child.is_model(inst,clear_bits=False):
                sat = 1
                break
        return sat


class NnfGate(Gate):
    def __init__(self,node_id,children,nnf=None,filename="missing-filename"):
        Gate.__init__(self,node_id)
        self.children = children
        self.nnf = nnf
        self.nnf_manager = None # AC
        self.filename = filename
        self.precision = 2 # AC

    def __repr__(self):
        child_ids = [ str(child) for child in self.children ]
        st = 'N %d %s %s' % (len(self.children), " ".join(child_ids), 
                             self.filename)
        return st

    def _make_nnf(self,precision=None):
        if self.nnf is not None: return
        if precision is None: precision = self.precision
        extension = os.path.splitext(self.filename)[-1]
        if extension == ".neuron" or extension == "":
            c = Classifier.read(self.filename)
            d = c.with_precision(precision)
            manager,obdd = d.compile()
            self.nnf_manager,self.nnf = manager.obdd_to_nnf(obdd)
        else:
            msg = "unknown extension %s" % extension
            raise Exception("NnfGate._make_nnf: %s" % msg)

    def negate(self,mgr):
        raise Exception("NnfGate.negate: unsupported")

    def _is_model(self,inst):
        # inst is a map: var_index -> {0,1}
        self._make_nnf()
        var_count = self.nnf_manager.var_count
        nnf_inst = [None] * (var_count+1)
        for var,child in enumerate(self.children,1):
            nnf_inst[var] = child.is_model(inst,clear_bits=False)
        return self.nnf.is_model(nnf_inst)


class Nnf:
    """NNF circuits"""

    def __init__(self,node_count,edge_count,var_count,root):
        self.node_count = node_count
        self.edge_count = edge_count
        self.var_count = var_count
        self.root = root

    def __repr__(self):
        st = 'nnf %d %d %d' % (self.node_count,self.edge_count,self.var_count)
        return st

    ########################################
    # QUERIES & TRANSFORMATIONS
    ########################################

    def model_count(self):
        self._used_variables()
        for node in self.root.__iter__(clear_data=True):
            if isinstance(node,Literal):
                count = 1
            elif isinstance(node,AndGate):
                count = 1
                for child in node.children:
                    count *= child._data
            elif isinstance(node,OrGate):
                count = 0
                node_var_count = len(node.node_vars)
                for child in node.children:
                    gap_size = node_var_count - len(child.node_vars)
                    count += child._data << gap_size
            else:
                raise Exception("model_count: unknown type")
            node._data = count
        gap_size = self.var_count - len(self.root.node_vars)
        return count << gap_size

    def _used_variables(self):
        if self.root.node_vars is not None: return
        for node in self.root:
            node.node_vars = set()
            if isinstance(node,Literal):
                var = abs(node.literal)
                node.node_vars.add(var)
            elif isinstance(node,(AndGate,OrGate)):
                for child in node.children:
                    node.node_vars.update(child.node_vars)
            else:
                raise Exception("used_variables: unknown type")

    def _prime_ref_count(self):
        for node in self.root.__iter__(clear_data=True):
            node._ref_count = 0
            if isinstance(node,Literal):
                pass
            elif isinstance(node,(AndGate,OrGate)):
                for child in node.children:
                    child._ref_count += 1
            else:
                raise Exception("ref_count: unknown type")
        self.root._ref_count += 1

    def flatten(self,mgr,precision=None):
        for node in self.root.__iter__(clear_data=True):
            if isinstance(node,NnfGate):
                node._make_nnf(precision)
                inputs = [None] + node.children
                for alpha in node.nnf.root.__iter__(clear_data=True):
                    if isinstance(alpha,Literal):
                        lit,var = alpha.literal,alpha.var
                        beta = inputs[var]._data
                        if lit < 0: beta = beta.negate(mgr)
                    else: # is_gate
                        cls = type(alpha)
                        new_children = [ c._data for c in alpha.children ]
                        beta = mgr.new_node(cls,children=new_children)
                    alpha._data = beta
                alpha = beta
            else:
                alpha = node
            node._data = alpha
        node_count,edge_count = alpha.count_and_size()
        nnf = Nnf(node_count,edge_count,mgr.var_count,alpha)
        return nnf

    def is_model(self,inst):
        # inst is a map: var_index -> {0,1}
        return self.root.is_model(inst)

    ########################################
    # I/O
    ########################################

    @staticmethod
    def read(filename):
        with open(filename,'r') as f:
            lines = f.readlines()
        my_node_count = len(lines) - 1 
        nodes = [None]*my_node_count
        for node_id,line in enumerate(lines):
            line = line.strip().split()
            node_id = node_id-1
            if line[0] == 'nnf':
                node_count = int(line[1])
                edge_count = int(line[2])
                var_count = int(line[3])
                manager = NnfManager(var_count)
                assert node_count == len(nodes)
                continue
            elif line[0] == 'L':
                literal = int(line[1])
                node = manager.new_node(Literal,literal=literal)
            elif line[0] == 'A':
                child_count = int(line[1])
                children = [ int(x) for x in line[2:] ]
                assert len(children) == child_count
                children = [ nodes[child_id] for child_id in children ]
                node = manager.new_node(AndGate,children=children)
            elif line[0] == 'O':
                decision_var = int(line[1]) # ignore
                child_count = int(line[2])
                children = [ int(x) for x in line[3:] ]
                assert len(children) == child_count
                children = [ nodes[child_id] for child_id in children ]
                node = manager.new_node(OrGate,children=children)
            elif line[0] == 'S':
                child_count = int(line[1])
                children = [ int(x) for x in line[2:-2] ] # skip offset ## ACAC
                offset = int(line[-2])
                assert len(children) == child_count
                children = [ nodes[child_id] for child_id in children ]
                filename = line[-1]
                node = manager.new_node(NnfGate,children=children,
                                        filename=filename)
            else:
                raise Exception("Nnf.save: unknown type")
            nodes[node_id] = node
        alpha = Nnf(node_count,edge_count,var_count,node)
        return manager,alpha

    def save(self,filename):
        idmap = {}
        with open(filename,'w') as f:
            f.write("nnf %d %d %d\n" % 
                    (self.node_count,self.edge_count,self.var_count))
            for node_id,node in enumerate(self.root):
                idmap[node.node_id] = node_id # id in file
                if isinstance(node,Literal):
                    f.write("L %d\n" % node.literal)
                elif isinstance(node,AndGate):
                    child_ids = [ idmap[c.node_id] for c in node.children ]
                    child_st = " ".join(map(str,child_ids))
                    f.write("A %d %s\n" % (len(child_ids),child_st))
                elif isinstance(node,OrGate):
                    child_ids = [ idmap[c.node_id] for c in node.children ]
                    child_st = " ".join(map(str,child_ids))
                    f.write("O %d %d %s\n" % (node.decision_var,
                                              len(child_ids),child_st))
                else:
                    raise Exception("Nnf.save: unknown type")


class NnfManager:
    def __init__(self,var_count):
        self.var_count = var_count
        # unique node cache (possibly external)
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        # make terminals
        self.id_counter = 0
        self.zero = self.new_node(OrGate,children=[])
        self.one = self.new_node(AndGate,children=[])
        self.literals = [None] * (2*var_count+1)
        for var in range(1,var_count+1):
            lit = -var
            self.literals[lit] = Literal(self.id_counter,lit)
            self.id_counter += 1
            lit = var
            self.literals[lit] = Literal(self.id_counter,lit)
            self.id_counter += 1

    def false(self): return self.zero
    def true(self): return self.one

    def new_id(self):
        node_id = self.id_counter
        self.id_counter += 1
        return node_id

    def new_node(self,cls,**kwargs):
        if cls is Literal:
            literal = kwargs["literal"]
            return self.literals[literal]
        else:
            if cls is NnfGate:
                children = tuple(kwargs["children"])
                filename = kwargs["filename"]
                key = (cls,children,filename)
            else:
                keyf = lambda x : x.node_id
                children = sorted(kwargs["children"],key=keyf)
                children = tuple(children)
                kwargs["children"] = children
                key = (cls,children)
            if key in self.cache:
                return self.cache[key]
            node = cls(node_id=self.new_id(),**kwargs)
            self.cache[key] = node
            return node

    def _reindex(self,nnf):
        index = self.var_count + 1
        for node in nnf.root:
            if node.is_input():
                node._index = node.literal
            else:
                node._index = index
                index += 1

    def nnf_to_cnf(self,nnf):
        from .cnf import Cnf

        clauses = []
        self._reindex(nnf)
        for node in nnf.root:
            if isinstance(node,Literal):
                me = node.literal # ACACAC
            elif isinstance(node,AndGate):
                me = node._index
                clause = [me]
                for child in node.children:
                    clauses.append([-me,child._index])
                    clause.append(-child._index)
                clauses.append(clause)
            elif isinstance(node,OrGate):
                me = node._index
                clause = [-me]
                for child in node.children:
                    clauses.append([me,-child._index])
                    clause.append(child._index)
                clauses.append(clause)
            else:
                msg = "Nnf.nnt_to_cnf: unexpected type % s" % type(node)
                raise Exception(msg)
        # me is output wire (last variable)
        return Cnf(me,clauses)

if __name__ == '__main__':
    from timer import Timer

    #filename = 'examples/simple.cnf.nnf'
    filename = 'examples/count.cnf.nnf'
    #filename = 'examples/c8.cnf.nnf'
    #filename = 'examples/c432.isc.cnf.nnf'
    with Timer("reading"):
        manager,nnf = Nnf.read(filename)
    #node.print_me()
    with Timer("counting"):
        node_count = nnf.root.count()
    with Timer("model counting"):
        model_count = nnf.model_count()
    print(" node count:", node_count)
    print("model count:", model_count)
    with Timer("negating"):
        negated = nnf.root.negate(manager)
        edge_count = negated.size()
        negated_nnf = Nnf(node_count,edge_count,manager.var_count,negated)
