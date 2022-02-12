#!/usr/bin/env python3

import sys
from collections import defaultdict
from .circuits import Literal, AndGate, OrGate, Nnf

class Verbose:
    """helper to print out update messages during compilation"""
    def __init__(self,nnf,verbose):
        self.nnf = nnf
        self.verbose = verbose
        self.count = 0
        self.node_count = self.nnf.root.count()

    def __enter__(self):
        print("count %d:\n" % self.node_count)
        return self

    def __exit__(self,type,value,traceback):
        pass

    def update(self):
        self.count += 1
        if not self.verbose: return
        if (self.count >= .999*self.node_count) or \
           (self.count >=  .99*self.node_count and self.count % 50 == 0)  or \
           (self.count >=   .9*self.node_count and self.count % 500 == 0) or \
            self.count % 5000 == 0:
            print(" %d" % self.count,flush=True)

def compile_nnf(nnf,mgr,verbose=False):
    with Verbose(nnf,verbose) as v:
        for node in nnf.root.__iter__(clear_data=True):
            if isinstance(node,Literal):
                alpha = mgr.literal(node.literal)
            elif isinstance(node,AndGate):
                alpha = mgr.true()
                for child in node.children:
                    alpha = alpha & child._data
            elif isinstance(node,OrGate):
                alpha = mgr.false()
                for child in node.children:
                    alpha = alpha | child._data
            else:
                raise Exception("compiling: unknown type")
            node._data = alpha
            v.update()
    return alpha

def compile_nnf_automatic(nnf,mgr,verbose=False):
    nnf._prime_ref_count()
    mgr.auto_gc_and_minimize_on()

    with Verbose(nnf,verbose) as v:
        for node in nnf.root.__iter__(clear_data=True):
            if isinstance(node,Literal):
                alpha = mgr.literal(node.literal)
            elif isinstance(node,AndGate):
                alpha = mgr.true()
                for child in node.children:
                    alpha = alpha & child._data
                    child._data.deref()
            elif isinstance(node,OrGate):
                alpha = mgr.false()
                for child in node.children:
                    alpha = alpha | child._data
                    child._data.deref()
            else:
                raise Exception("compiling: unknown type")
            for _ in range(node._ref_count): alpha.ref()
            node._data = alpha
            v.update()

    mgr.auto_gc_and_minimize_off()
    alpha.deref()
    return alpha

def compile_nnf_manual(nnf,mgr,verbose=False):
    nnf._prime_ref_count()
    #gc_last_size = 2**14
    #min_last_size = 2**14
    gc_last_size = 34000
    min_last_size = 34000

    with Verbose(nnf,verbose) as v:
        for node in nnf.root.__iter__(clear_data=True):
            if isinstance(node,Literal):
                alpha = mgr.literal(node.literal)
            elif isinstance(node,AndGate):
                alpha = mgr.true()
                for child in node.children:
                    alpha = alpha & child._data
                    child._data.deref()
            elif isinstance(node,OrGate):
                alpha = mgr.false()
                for child in node.children:
                    alpha = alpha | child._data
                    child._data.deref()
            else:
                raise Exception("compiling: unknown type")
            for _ in range(node._ref_count): alpha.ref()
            node._data = alpha

            if mgr.dead_count() >= 2*gc_last_size:
                print('+',end='',flush=True)
                gc_last_size = 2*gc_last_size
                mgr.garbage_collect()
            if mgr.live_count() >= 2*min_last_size:
                print('*',end='',flush=True)
                min_last_size = 2*min_last_size
                mgr.minimize_limited()
            v.update()

    alpha.deref()
    return alpha

def _compile_nnf_recursive(node,mgr,v):
    if node._data is not None:
        return node._data
    if isinstance(node,Literal):
        alpha = mgr.literal(node.literal)
    elif isinstance(node,AndGate):
        alpha = mgr.true()
        for child in node.children:
            alpha.ref()
            beta = _compile_nnf_recursive(child,mgr,v)
            alpha.deref()
            alpha = alpha & beta
            beta.deref()
    elif isinstance(node,OrGate):
        alpha = mgr.false()
        for child in node.children:
            alpha.ref()
            beta = _compile_nnf_recursive(child,mgr,v)
            alpha.deref()
            alpha = alpha | beta
            beta.deref()
    else:
        raise Exception("compiling: unknown type")
    v.update()
    for _ in range(node._ref_count): alpha.ref()
    node._data = alpha
    return alpha

def compile_nnf_recursive(nnf,mgr,verbose=False):
    v = Verbose(nnf,verbose)
    nnf._prime_ref_count()
    mgr.auto_gc_and_minimize_on()
    root = _compile_nnf_recursive(nnf.root,mgr,v)
    mgr.auto_gc_and_minimize_off()
    root.deref()
    # ACACAC: clear data
    return root

############################################################
# experimental
############################################################

def label_nodes_by_depth(node,depth=0):
    if hasattr(node,'_depth'):
        node._depth = max(node._depth,depth)
        return
    else:
        node._depth = depth
    depth = node._depth # the deepest depth of this node found
    if isinstance(node,Literal):
        pass
    elif isinstance(node,AndGate):
        for child in node.children:
            label_nodes_by_depth(child,depth=depth+1)
    elif isinstance(node,OrGate):
        for child in node.children:
            label_nodes_by_depth(child,depth=depth+1)
    else:
        raise Exception("compiling: unknown type")

def bucket_nodes_by_depth(nnf):
    label_nodes_by_depth(nnf.root)
    buckets = defaultdict(set)
    for node in nnf.root:
        depth = node._depth
        buckets[depth].add(node)
    return buckets

def compile_nnf_recursive_by_depth(nnf,mgr,verbose=False):
    #mgr.auto_gc_and_minimize_on()
    nnf._prime_ref_count()
    gc_limit = 2**15
    min_limit = 2**15

    buckets = bucket_nodes_by_depth(nnf)
    depths = reversed(sorted(buckets.keys()))
    with Verbose(nnf,verbose) as v:
        for depth in depths:
            bucket = buckets[depth]
            print("depth: %d (%d nodes)" % (depth,len(bucket)))
            for node in bucket:
                if isinstance(node,Literal):
                    alpha = mgr.literal(node.literal)
                elif isinstance(node,AndGate):
                    alpha = mgr.true()
                    for child in node.children:
                        alpha = alpha & child._data
                        child._data.deref()
                elif isinstance(node,OrGate):
                    alpha = mgr.false()
                    for child in node.children:
                        alpha = alpha | child._data
                        child._data.deref()
                else:
                    raise Exception("compiling: unknown type")
                for _ in range(node._ref_count): alpha.ref()
                node._data = alpha

                v.update()
                if mgr.dead_count() >= 2*gc_limit:
                    print('+',end='',flush=True)
                    print("live count:", mgr.live_count())
                    print("dead count:", mgr.dead_count())
                    #gc_limit = 2*gc_limit
                    mgr.garbage_collect()
                if mgr.live_count() >= 2*min_limit:
                    print('*',end='',flush=True)
                    print("live count:", mgr.live_count())
                    print("dead count:", mgr.dead_count())
                    #min_limit = 2*min_limit
                    mgr.minimize_limited()
            print("live count:", mgr.live_count())
            print("dead count:", mgr.dead_count())

    for node in nnf.root.__iter__(clear_data=True):
        del node._depth
    #mgr.auto_gc_and_minimize_off()
    return alpha

############################################################
# experimental
############################################################

if __name__ == '__main__':
    from timer import Timer
    import pysdd
    from pysdd.sdd import Vtree, SddManager

    basename = 'c432.isc'
    nnf_filename = 'examples/%s.cnf.nnf' % basename
    vtree_filename = 'examples/%s.cnf.vtree' % basename

    with Timer("reading"):
        nnf_manager,nnf = Nnf.read(nnf_filename)

    vtree = Vtree(filename=vtree_filename)
    mgr = SddManager(vtree=vtree)
    with Timer("compiling"):
        node = compile_nnf_automatic(nnf,mgr)
    print("model count:", node.global_model_count())
    print(" node size: %d" % node.size())
    print("node count: %d" % node.count())

    print("live size: %d" % mgr.live_size())
    print("dead size: %d" % mgr.dead_size())
