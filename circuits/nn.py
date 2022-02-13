#!/usr/bin/env python3

import sys
from random import randint
from circuits import *
from circuits.data import read_csv

def compile_nn(nnf_filename,precision,dataset_filename,\
               sdd_filename="tmp.sdd",vtree_filename="tmp.vtree",\
               var_order=None,verbose=False):
    from circuits import Timer # ACAC???
    from pysdd.sdd import Vtree, SddManager, SddNode

    with Timer("reading"):
        manager,nnf = Nnf.read(nnf_filename)
    with Timer("flattening"):
        flat = nnf.flatten(manager,precision=precision)
    # flat is an NNF (and/or circuit)
    var_count = manager.var_count
    node_count,edge_count = flat.root.count_and_size()
    print("%d node count" % node_count)
    print("%d edge count" % edge_count)

    # the following block can be skipped
    count = 0
    true_count = 0
    total = 100
    with Timer("sanity checking"):
        for _ in range(total):
            inst = [ randint(0,1) for _ in range(var_count+1) ]
            one = nnf.is_model(inst)
            two = flat.is_model(inst)
            count += int(one == two)
            if one: true_count += 1
    print("%d/%d correct" % (count,total))
    print("%d/%d positive" % (true_count,total))

    with Timer("compiling"):
        if var_order is None:
            vtree = Vtree(var_count=manager.var_count,vtree_type="right")
            sdd_manager = SddManager(vtree=vtree)
        else:
            vtree = Vtree.new_with_var_order(manager.var_count,\
                                             var_order,"right")
            sdd_manager = SddManager(vtree=vtree)
        # ACACAC
        #alpha = compile_nnf_manual(flat,sdd_manager,verbose=verbose)
        #alpha = compile_nnf_recursive(flat,sdd_manager,verbose=verbose)
        alpha = compile_nnf_recursive_by_depth(flat,sdd_manager,verbose=verbose)
    print("%d node count" % alpha.count())
    print("%d edge count" % alpha.size())

    # the following block can be enabled to do post-process minimization
    with Timer("minimizing"):
        alpha.ref()
        sdd_manager.minimize_limited()
        alpha.deref()
    print("%d node count" % alpha.count())
    print("%d edge count" % alpha.size())


    if dataset_filename:
        dataset = read_csv(dataset_filename)
        correct = 0
        N = len(dataset)
        with Timer("evaluating test set accuracy"):
            for example in dataset:
                inst = [0]+example[:-1]
                label = example[-1]
                prediction = flat.is_model(inst)
                correct += int(label == prediction)
        print("test accuracy: %d/%d = %.4f" % (correct,N,correct/N))

    with Timer("saving"):
        alpha.save(sdd_filename)
        sdd_manager.vtree().save(vtree_filename)

    print("== cleaning up ====================")
    print("before garbage collecting...")
    print("live size:", sdd_manager.live_count())
    print("dead size:", sdd_manager.dead_count())
    print("garbage collecting...")
    sdd_manager.garbage_collect()
    print("live size:", sdd_manager.live_count())
    print("dead size:", sdd_manager.dead_count())

if __name__ == '__main__':
    if not ( 2 <= len(sys.argv) <= 4 ):
        opts = "[NNF-FILENAME] DIGITS-OF-PRECISION DATASET-FILENAME"
        print( "usage: %s %s" % (sys.argv[0],opts) )
        exit(1)

    nnf_filename = sys.argv[1]
    precision = 4 if len(sys.argv) == 2 else int(sys.argv[2])
    dataset_filename = None if len(sys.argv) <= 3 else sys.argv[3]
    print("== compiling %s with precision %d" % (nnf_filename,precision))
    main(nnf_filename,precision,dataset_filename)
