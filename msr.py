
import struct
import os
import glob

AMD_MSR_PWR_UNIT =  0xC0010299
AMD_MSR_CORE_ENERGY = 0xC001029A
AMD_MSR_PACKAGE_ENERGY = 0xC001029B

def writemsr(msr, val, cpu=-1):
    """
    Function for writing to an msr register
    """
    try:
        if cpu == -1:
            for cpu_msr in glob.glob('/dev/cpu/[0-9]*/msr'):
                file_id = os.open(cpu_msr, os.O_WRONLY)
                os.lseek(file_id, msr, os.SEEK_SET)
                os.write(file_id, struct.pack('Q', val))
                os.close(file_id)
        else:
            file_id = os.open('/dev/cpu/%d/msr' % (cpu), os.O_WRONLY)
            os.lseek(file_id, msr, os.SEEK_SET)
            os.write(file_id, struct.pack('Q', val))
            os.close(file_id)
    except:
        raise OSError("msr module not loaded (run modprobe msr)")

def readmsr(msr, cpu=0):
    """
    function for readin an msr register
    """
    try:
        file_id = os.open('/dev/cpu/%d/msr' % cpu, os.O_RDONLY)
        os.lseek(file_id, msr, os.SEEK_SET)
        val = struct.unpack('Q', os.read(file_id, 8))
        os.close(file_id)
        return val[0]
    except:
        raise OSError("msr module not loaded (run modprobe msr)")

def get_percore_energy(cpulist=[0]):
    return [readmsr(AMD_MSR_CORE_ENERGY, i) & 0xFFFFFFFF for i in cpulist]

def get_units():
    result = readmsr(AMD_MSR_PWR_UNIT, 0)
    power_unit = 0.5 ** (result & 0xF)
    energy_unit = 0.5 **  ((result >> 8) & 0x1F)
    time_unit = 0.5 ** ((result >> 16) & 0xF)

    print(hex(result), " ", power_unit, " ", energy_unit, " ", time_unit)

    return energy_unit
