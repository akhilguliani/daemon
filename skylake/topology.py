"""
CPU Tolopology class based on psutil cpu tree proof of concept
"""

class Core(dict):
    def thread_count(self):
        return len(self)

class Pack(dict):
    def core_count(self):
        return len(self)

    def thread_count(self):
        return sum([core.thread_count() for core in self.values()])

class Topology(dict):
    def pack_count(self):
        return len(self)

    def core_count(self):
        return sum([pack.core_count() for pack in self.values()])

    def thread_count(self):
        return sum([pack.thread_count() for pack in self.values()])

def cpu_tree():
    topology = Topology()
    current_info ={}
    with open('/proc/cpuinfo', 'rb') as procfile:
        for line in procfile:

            line = line.strip().lower()

            if not line:
                # got an empty line, lets init/update relevant dictionaries
                # New Section
                try:
                    phys_id = int(current_info[b'physical id'])
                except KeyError:
                    phys_id = 0

                try:
                    pack = topology[phys_id]
                except KeyError:
                    pack = Pack()
                    topology[phys_id] = pack

                try:
                    core_id = int(current_info[b'core id'])
                except KeyError:
                    # single core under KVM has no core id
                    core_id = 0

                try:
                    core = pack[core_id]
                except KeyError:
                    core = Core()
                    pack[core_id] = core

                processor = int(current_info[b'processor'])
                core[processor] = current_info
                current_info = {}

            else:
                # On-Going Section
                key, value = line.split(b':', 1)
                current_info[key.strip()] = value.strip()
    return topology


