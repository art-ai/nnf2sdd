class ObddManager:
    def __init__(self,var_count,use_cache=True): # ACACAC: use_cache
        self.var_count = var_count
        #self.ordering = ordering # ACAC
        self.zero = ObddNode(is_terminal=True,sign=0,nid=0)
        self.one = ObddNode(is_terminal=True,sign=1,nid=1)
        self.id_counter = 2
        # unique node cache (possibly external)
        self.use_cache = use_cache
        self.cache = [ {} for _ in range(var_count+1) ]
        self.cache_hits = 0
        self.cache_misses = 0
        # stats for oracle
        self.sat_calls = 0
        self.sat_time = 0.0

    def zero_sink(self):
        return self.zero

    def one_sink(self):
        return self.one

    def obdd_to_cnf(self,root,base_index):
        from .cnf import Cnf

        clauses = []
        self._reindex(root)
        for node in root:
            if node.is_terminal():
                me = base_index + node._index
                lit = -me if node.is_false() else me
                clauses.append([lit])
            else:
                # wire = base + index
                # wire <=> ( dvar & self.hi | -dvar & self.lo )
                dvar = node.dvar
                hi = base_index + node.hi._index
                lo = base_index + node.lo._index
                me = base_index + node._index
                clauses.append([ -me,lo,dvar ])
                clauses.append([ -me,hi,-dvar ])
                clauses.append([ -me,lo,hi ])
                clauses.append([ me,-lo,dvar ])
                clauses.append([ me,-hi,-dvar ])
        # me is output wire
        return Cnf(me,clauses),me

    def obdd_to_sdd(self,root,offset=0):
        from pysdd.sdd import Vtree, SddManager
        var_count = self.var_count + offset
        vtree = Vtree(var_count=var_count,vtree_type="right")
        mgr = SddManager.from_vtree(vtree)
        for node in root.__iter__(clear_data=True):
            if node.is_terminal():
                alpha = mgr.true() if node.is_true() else mgr.false()
            else:
                dvar = node.dvar + offset
                plit,nlit = mgr.literal(dvar),mgr.literal(-dvar)
                alpha = (plit & node.hi.data) | (nlit & node.lo.data)
            node.data = alpha
        return (mgr,alpha)

    def obdd_to_nnf(self,root):
        from .circuits import NnfManager, Nnf
        from .circuits import Literal, AndGate, OrGate
        mgr = NnfManager(self.var_count)
        for node in root.__iter__(clear_data=True):
            if node.is_terminal():
                alpha = mgr.true() if node.is_true() else mgr.false()
            else:
                dvar = node.dvar
                plit = mgr.new_node(Literal,literal=dvar)
                nlit = mgr.new_node(Literal,literal=-dvar)
                hi = mgr.new_node(AndGate,children=[plit,node.hi.data])
                lo = mgr.new_node(AndGate,children=[nlit,node.lo.data])
                alpha = mgr.new_node(OrGate,children=[hi,lo])
            node.data = alpha
        node_count,edge_count = alpha.count_and_size()
        nnf = Nnf(node_count,edge_count,mgr.var_count,alpha)
        return mgr,nnf

    def obdd_to_pyeda(self,root):
        """This converts our OBDD to an OBDD in the PyEDA module.
        You can use this to save the OBDD to a png file."""
        from pyeda.inter import bddvars
        dvars = bddvars('x',self.var_count+1) # extra var to 1-index
        x = dvars[0]
        true,false = (x|~x),(x&~x)
        for node in root.__iter__(clear_data=True):
            if node.is_terminal():
                f = false if node.is_false() else true
            else:
                dvar = dvars[node.dvar]
                f = (dvar & node.hi.data) | (~dvar & node.lo.data)
            node.data = f
        return f

    def obdd_to_png(self,root,filename):
        import pydot
        obdd = self.obdd_to_pyeda(root)
        obdd_dot_string = obdd.to_dot()
        graphs = pydot.graph_from_dot_data(obdd_dot_string)
        graphs[0].write_png(filename)

    def _reindex(self,root):
        for i,node in enumerate(root):
            node._index = i

    def new_node(self,dvar,hi,lo): # ACAC  unique-table-lookup?
        if self.use_cache:
            key = (hi.nid,lo.nid)
            if key in self.cache[dvar]:
                return self.cache[dvar][key]
        node = ObddNode(dvar=dvar,hi=hi,lo=lo,nid=self.id_counter)
        self.id_counter += 1
        if self.use_cache:
            self.cache[dvar][key] = node
        """
        if self.id_counter % 1000 == 0:
            print(self.id_counter)
            #print(self.id_counter, end=' ')
        """
        return node

    def save_vtree(self,filename):
        with open(filename,'w') as f:
            n = 2*self.var_count - 1
            f.write("vtree %d\n" % n)
            for i in range(self.var_count):
                var = i + 1
                vtree_id = 2*i
                f.write("L %d %d\n" % (vtree_id,var))
            last_vtree_id = 2*(self.var_count-1)-1
            left_id,right_id = last_vtree_id-1,last_vtree_id+1
            f.write("I %d %d %d\n" % (last_vtree_id,left_id,right_id))
            for vtree_id in range(last_vtree_id-2,0,-2):
                left_id = vtree_id - 1
                right_id = vtree_id + 2
                f.write("I %d %d %d\n" % (vtree_id,left_id,right_id))

    def save_sdd(self,filename,root):
        last_var = self.var_count
        count,last_count = root.count(dvar=last_var)
        terminal_count = root.count_terminals()
        # decision-nodes + terminals + literals - last-decision-nodes
        node_count = (count + terminal_count + 2*self.var_count) - last_count
        cache = {}
        with open(filename,'w') as f:
            f.write("sdd %d\n" % node_count)
            node_id = 0
            # literal-ids range from 0 to 2*n-1
            for var in range(1,self.var_count+1):
                vtree_id = 2*(var-1)
                f.write("L %d %d %d\n" % (node_id,vtree_id,-var))
                node_id += 1
                f.write("L %d %d %d\n" % (node_id,vtree_id,var))
                node_id += 1
            for node in root:
                if node.is_terminal():
                    if node.is_false():
                        label = "F"
                        false_id = node_id
                    else:
                        label = "T"
                        true_id = node_id
                    f.write("%s %d\n" % (label,node_id))
                    new_node_id = node_id
                    node_id += 1
                else:
                    var = node.dvar
                    neg_id,pos_id = 2*(var-1),2*(var-1)+1
                    if var == last_var:
                        if node.hi.is_true() and node.lo.is_true():
                            new_node_id = true_id
                        elif node.hi.is_false() and node.lo.is_false():
                            new_node_id = false_id
                        elif node.hi.is_true() and node.lo.is_false():
                            new_node_id = pos_id
                        elif node.hi.is_false() and node.lo.is_true():
                            new_node_id = neg_id
                    else:
                        vtree_id = 2*(var-1) + 1
                        hi_id = cache[node.hi.nid]
                        lo_id = cache[node.lo.nid]
                        f.write("D %d %d 2 %d %d %d %d\n" % \
                                (node_id,vtree_id,pos_id,hi_id,neg_id,lo_id))
                        new_node_id = node_id
                        node_id += 1
                cache[node.nid] = new_node_id


class ObddNode:
    def __init__(self,dvar=None,hi=None,lo=None,
                 is_terminal=False,sign=False,nid=-1):
        self.nid = nid
        self.context = None
        if is_terminal:
            self.sign = sign
            self.dvar = 0 # None
            self.hi = None
            self.lo = sign # None
            self.is_decision_node = False
        else:
            #assert dvar == hi.dvar+1 and dvar == lo.dvar+1 # ACAC: ordering
            self.sign = None
            self.dvar = dvar
            self.hi = hi
            self.lo = lo
            self.is_decision_node = True
        self._bit = False
        self.data = None

    def __iter__(self,marker=True,clear_data=False,clear_bits=True):
        cur,last = self,None
        self._parent = None
        while cur is not None:
            if cur._bit is marker: # goto parent
                cur,last = cur._parent,cur
                del last._parent
            elif cur.is_terminal() or last == cur.lo: # goto parent
                cur._bit = marker
                yield cur
                cur,last = cur._parent,cur
                del last._parent
            elif last == cur.hi: # goto lo (check after lo)
                cur.lo._parent = cur
                cur,last = cur.lo,cur
            else: # goto hi
                cur.hi._parent = cur
                cur,last = cur.hi,cur
        if clear_bits:
            self.clear_bits(clear_data=clear_data)

    def clear_bits(self,clear_data=False):
        for node in self.__iter__(marker=False,clear_bits=False):
            if clear_data: node.data = None

    def reduce(self):
        # TODO: do unique table lookup here? needed?
        for node in self.__iter__(clear_data=True):
            if node.is_terminal(): continue
            if node.hi.data is not None:
                node.hi = node.hi.data
            if node.lo.data is not None:
                node.lo = node.lo.data
            if node.hi is node.lo:
                node.data = node.hi
            last = node.data
        return self if last is None else last

    def model_count(self,var_count):
        for node in self.__iter__(clear_data=True):
            if node.is_terminal():
                node.data = 0 if node.is_false() else 2**var_count
            else:
                count = (node.hi.data + node.lo.data)//2
                node.data = count
        return count

    def models(self):
        """generator that yields all models of the obdd."""
        if self.is_terminal():
            if self.is_true():
                yield dict()
        else:
            for model in self.hi.models():
                model[self.dvar] = 1
                yield model
            for model in self.lo.models():
                model[self.dvar] = 0
                yield model

    def non_models(self):
        """generator that yields all non-models of the obdd."""
        if self.is_terminal():
            if self.is_false():
                yield dict()
        else:
            for model in self.hi.non_models():
                model[self.dvar] = 1
                yield model
            for model in self.lo.non_models():
                model[self.dvar] = 0
                yield model

    def is_model(self,inst):
        if self.is_terminal():
            return self.sign
        val = inst[self.dvar]
        if val:
            return self.hi.is_model(inst)
        else:
            return self.lo.is_model(inst)

    def count(self,dvar=None):
        """returns number of decision nodes"""
        count,dvar_count = 0,0
        for node in self:
            if not node.is_terminal():
                count += 1
            if node.dvar == dvar:
                dvar_count += 1
        if dvar is not None:
            return (count,dvar_count)
        else:
            return count

    def count_terminals(self):
        """returns number of reachable terminals"""
        count = 0
        for node in self:
            if node.is_terminal():
                count += 1
        return count

    def __repr__(self):
        if self.is_decision_node:
            st = "%d %d %d %d" % (self.nid,self.dvar,self.hi.nid,self.lo.nid)
        else:
            st = "%d" % self.nid
        return st

    def is_decision(self): return self.is_decision_node
    def is_terminal(self): return not self.is_decision_node
    def get_context(self): return self.context
    def set_context(self,context): self.context = context
    def is_true(self): return not self.is_decision_node and self.sign != 0
    def is_false(self): return not self.is_decision_node and self.sign == 0
