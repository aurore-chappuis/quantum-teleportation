from typing import *
import math

from qiskit import *
from qiskit.compiler.transpiler import _parse_backend_properties 
from qiskit.providers.ibmq import *
from qiskit.tools.visualization import plot_histogram
from qiskit.tools.monitor import job_monitor

proco = ["ibmq_manila","ibmq_santiago","ibmq_athens","ibmq_belem","ibmq_quito","ibmq_lima","ibmqx2"]

class circuitBuilder(object):
    def __init__(self,minCiruitsize:Tuple[int,int],builder:Callable[[QuantumCircuit,Any],QuantumCircuit],stateValidator:Callable[[Any],bool] = lambda s: True,state = None):
        self._builder = builder
        self._validator = stateValidator
        self.minCiruitsize = minCiruitsize

        if self.isValidState(state):
            self._state = state
        else:
            raise TypeError(f"Invalide state {state}")
        
    def __call__(self,circuit:QuantumCircuit) -> QuantumCircuit:
        return self._builder(circuit,self._state)
    
    def setState(self,state:Any):
        if self.isValidState(state):
            self._state = state
        else :
            raise TypeError(f"Invalide state {state}")
        
    def isValidState(self,state:Any) -> bool:
        return self._validator(state)


class Qubit(object):
    def __init__(self,c1:complex,c2:complex):
        if not math.isclose((abs(c1)**2+abs(c2)**2, 1)):
            raise ValueError(f"Invalid Qubit state {c1}|0> + {c2}|1> sum of amplitudes-squared does not equal one. ")
        self.c1 = c1
        self.c2 = c2

    def QubitValidator(s:Any) -> bool:
        return isinstance(s,Qubit)

    def toVector(self)->list:
        return [self.c1,self.c2]
    
    def __str__(self) -> str:
        return f"[{self.c1};{self.c2}]"

def teleportBuilder(circuit:QuantumCircuit,state:Qubit)->QuantumCircuit:

    circuit.initialize(state.toVector(),0)

    circuit.h(1)
    circuit.cnot(1,2)

    circuit.barrier()

    circuit.cnot(0,1)
    circuit.h(0)

    circuit.barrier()

    circuit.cnot(1,2)
    circuit.cz(0,2)

    circuit.barrier()

    circuit.measure(2,0)

    return circuit

import time

def autoSelectQCompute(filter:"list[str]",builder:circuitBuilder,states:list,maxQueuedJob:int = 10) -> IBMQBackend:
    provider=IBMQ.get_provider('ibm-q')
    simulator=Aer.get_backend('qasm_simulator')

    filter = filter.copy()

    for f in filter:
        qcomputer = provider.get_backend(f)
        if qcomputer.status().pending_jobs > maxQueuedJob:
            filter.remove(f)
            continue
        joblim = qcomputer.job_limit()
        if joblim.maximum_jobs - joblim.active_jobs > len(states):
            print(f"[Warning] number of states is superior to the number of available jobs for the backend {f} autoselection may take longer than expected")

    jobs = {s:{n:{"job":None,"expeResult":None,"status":None} for n in filter} for s in states}

    for s in states:
        builder.setState(s)
        circuit = QuantumCircuit(*builder.minCiruitsize)
        counts = execute(circuit,backend = simulator,shots=512).result().get_counts()
        jobs[s]["simResult"] = {k:counts[k] for k in counts}

        for f in filter:
            qcomputer = provider.get_backend(f)
            while (True):
                joblim = qcomputer.job_limit()
                if joblim.maximum_jobs - joblim.active_jobs >=1:
                    break
                time.sleep(2)
            jobs[s][f]["job"] = execute(circuit,backend = qcomputer,shots=512)
        
    jobsLeft = len(states)*len(filter)

    while jobsLeft >0:
        time.sleep(2)
        for s in states:
            for f in filter:
                status = jobs[s][f]["jobs"].status()
                if (status.name in ['DONE', 'CANCELLED', 'ERROR']):
                    jobsLeft -= 1

                    if status.name == 'ERROR':
                        print(f"An error occured while processing state {s} on {f}")
                    
                    if status.name == 'DONE':
                        counts = jobs[s][f]["jobs"].result().get_counts()
                        jobs[s][f]["expeResult"] = {k:counts[k] for k in counts}

                    jobs[s][f]["status"] = status.name

    errors = {f:{"count":0,"tot":0} for f in filter}

    for s in states:
        for f in filter:
            if jobs[s][f]["status"] == 'DONE':
                errors[f]["tot"] += 512
                for k in jobs[s]["simResult"].keys():
                    errors[f]["count"] += abs(jobs[s][f]["expeResult"][k] - jobs[s]["simResult"][k])
    
    back = None
    error = 2.0

    for (k,v) in errors :
        e = float(v["count"])/v["tot"]
        if e<error:
            error = e
            back = k
    
    print(error)
    print(back)

    return provider.get_backend(back)




            



    