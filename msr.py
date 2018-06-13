
import struct
import os
import subprocess
import glob

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
        print(val)
        os.close(file_id)
        return val[0]
    except:
        raise OSError("msr module not loaded (run modprobe msr)")

def track_percore_energy():
    for i in range(0, 15, 2):
        print(format(readmsr(power_msr, i), '08X'))

def main():
    if os.geteuid() != 0:
        raise OSError("Need sudo to run")
    else:
        # ensure modprobe msr is run
        subprocess.run(["modprobe", "msr"])

    AMD_MSR_PWR_UNIT =  0xC0010299
    AMD_MSR_CORE_ENERGY = 0xC001029A
    AMD_MSR_PACKAGE_ENERGY = 0xC001029B

    power_msr = AMD_MSR_CORE_ENERGY
    for i in range(0, 15, 2):
        print(format(readmsr(power_msr, i), '08X'))

## Starting point
if __name__ == "__main__":
    main()
