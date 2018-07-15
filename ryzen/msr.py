
import struct
import os
import glob

AMD_MSR_PWR_UNIT =  0xC0010299
AMD_MSR_CORE_ENERGY = 0xC001029A
AMD_MSR_PACKAGE_ENERGY = 0xC001029B

PSTATES = range(0xC0010064, 0xC001006C)

def writemsr(msr, val, cpu=-1):
    """ Function for writing to an msr register """
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
    """ function for readin an msr register """
    try:
        file_id = os.open('/dev/cpu/%d/msr' % cpu, os.O_RDONLY)
        os.lseek(file_id, msr, os.SEEK_SET)
        val = struct.unpack('Q', os.read(file_id, 8))
        os.close(file_id)
        return val[0]
    except:
        raise OSError("msr module not loaded (run modprobe msr)")

def get_percore_msr(MSR, cpulist=[0]):
    """ Return Raw 64 bit MSR value for CPUs given """
    return [readmsr(MSR, i) & 0xFFFFFFFFFFFFFFFF for i in cpulist]

def get_percore_energy(cpulist=[0]):
    """ Return per core energy MSR value for Ryzen """
    return [readmsr(AMD_MSR_CORE_ENERGY, i) & 0xFFFFFFFF for i in cpulist]

def get_units():
    """ Get the various units for Power Units MSR """
    result = readmsr(AMD_MSR_PWR_UNIT, 0)
    power_unit = 0.5 ** (result & 0xF)
    energy_unit = 0.5 **  ((result >> 8) & 0x1F)
    time_unit = 0.5 ** ((result >> 16) & 0xF)

    print(hex(result), " ", power_unit, " ", energy_unit, " ", time_unit)

    return energy_unit

def setup_perf():
    """ Set bits to lock TSC value and enable Instruction count MSR """
    val = readmsr(0xC0010015,0)
    for i in range(16):
        writemsr(0xC0010015, 0x4B200011, i)

def pstate2str(val):
    """
    Print human readble configuration for Pstate
    Adapted from ZenStates.py
    """
    if val & (1 << 63):
        fid = val & 0xff
        did = (val & 0x3f00) >> 8
        vid = (val & 0x3fc000) >> 14
        ratio = 25*fid/(12.5 * did)
        vcore = 1.55 - 0.00625 * vid
        return "Enabled - FID = %X - DID = %X - VID = %X - Ratio = %.2f - vCore = %.5f" % (fid, did, vid, ratio, vcore)
    else:
        return "Disabled"

def print_pstate_values():
    """ Debug function to read pstate configs"""
    for i in range(3):
        pstate_val = readmsr(PSTATES[i], cpu=0)
        pstate2str(pstate_val)
