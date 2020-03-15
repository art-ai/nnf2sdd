
def read_csv(filename):
    with open(filename,'r') as f:
        lines = f.readlines()
    dataset = []
    for line in lines:
        line = line.strip().split(",")
        line = [ int(x) for x in line ]
        dataset.append(line)
    return dataset
