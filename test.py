#!/usr/bin/env python3

from circuits.timer import Timer
from circuits.linear import *

def print_model(model):
    model_vars = sorted(model.keys())
    print(" ".join("%d:%d" % (var,model[var]) for var in model_vars))

if __name__ == '__main__':
    precision = 1
    filename = 'examples/example.neuron'
    c = Classifier.read(filename)
    print("== input neuron:")
    print(c)
    d = c.with_precision(precision)
    print("== neuron with %d digit(s) precision:" % precision)
    print(d)
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

    print("model count: %d" % node.model_count(obdd_manager.var_count))
    print("models:")
    for model in node.models():
        print_model(model)
    print("non-models:")
    for model in node.non_models():
        print_model(model)

