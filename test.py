#!/usr/bin/env python3

from circuits.timer import Timer
from circuits.linear import *

def print_model(model):
    model_vars = sorted(model.keys())
    print(" ".join("%d:%d" % (var,model[var]) for var in model_vars))

if __name__ == '__main__':
    filename = 'examples/example.neuron'
    c = Classifier.read(filename)
    print("=== INPUT NEURON:")
    print(c)
    assert c.is_integer
    #c = c.with_precision(3)
    #print("== quantized neuron:")
    #print(c)
    print("=== NEURON TO OBDD:")
    with Timer("compiling"):
        obdd_manager,node = c.compile()
    with Timer("size"):
        count_before = len(list(node))
    with Timer("reducing"):
        node = node.reduce()
    with Timer("size"):
        count_after = len(list(node))
    print("node count before reduce: %d" % count_before)
    print(" node count after reduce: %d" % count_after)

    print("=== OBDD:")
    print("model count: %d" % node.model_count(obdd_manager.var_count))
    print("models:")
    for model in node.models():
        print_model(model)
    print("non-models:")
    for model in node.non_models():
        print_model(model)

    # save the obdd to a png, using pyeda and pydot (install these)
    png_filename = filename + ".png"
    obdd_manager.obdd_to_png(node,png_filename)
    print("saved obdd image to %s" % png_filename)

    #obdd_manager.save_vtree("tmp.vtree")
    #obdd_manager.save_sdd("tmp.sdd",node)
