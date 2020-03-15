class Cnf:
    def __init__(self,var_count,clauses):
        self.var_count = var_count
        self.clauses = clauses

    def condition(self,lit):
        new_clauses = []
        for clause in self.clauses:
            if lit in clause: continue
            if -lit in clause:
                clause = list(clause)
                clause.remove(-lit)
            new_clauses.append(clause)
        return Cnf(self.var_count,new_clauses)

    def is_model(self,model):
        is_cnf_sat = True
        model = set(model)
        for clause in self.clauses:
            is_clause_sat = False
            for lit in clause:
                if lit in model:
                    is_clause_sat = True
                    break
            if not is_clause_sat:
                is_cnf_sat = False
                break
        return is_cnf_sat

    def __repr__(self):
        st = "Cnf(var_count=%d,clauses=%s)" % \
            (self.var_count,str(self.clauses))
        return st

    def as_string(self):
        st = []
        st.append( "p cnf %d %d" % (self.var_count,len(self.clauses)) )
        for clause in self.clauses:
            clause_st = " ".join(map(str,clause))
            st.append( "%s 0" % clause_st )
        return "\n".join(st)

    def write(self,filename):
        with open(filename,'w') as f:
            f.write( "p cnf %d %d\n" % (self.var_count,len(self.clauses)) )
            for clause in self.clauses:
                clause_st = " ".join(map(str,clause))
                f.write("%s 0\n" % clause_st)

    @staticmethod
    def read(filename):
        with open(filename,'r') as f:
            lines = f.readlines()
        clauses = []
        for line in lines:
            line = line.strip()
            if line.startswith("c") or not line:
                continue
            elif line.startswith("p"):
                line = line.split(" ")
                var_count = int(line[2])
                clause_count = int(line[3])
            else:
                line = [ int(lit) for lit in line.split(" ") ]
                clause = line[:-1]
                clauses.append(clause)
        if len(clauses) != clause_count:
            print("warning: inconsistent clause count")
        return Cnf(var_count,clauses)
