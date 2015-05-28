#!/usr/bin/env python
# encoding: utf-8

import os
import re
import sys
import select
import time
from I2C import *

i2c = None
i2c_addr = 0x1a

bp_device = "/dev/cu.usbserial-AD01U6CB"
# bp_device = "COM23"

bp_baud_rate = 115200
bp_timeout = 0.1


def config_bp_i2c():
    global i2c
    i2c = I2C(bp_device, bp_baud_rate, timeout=bp_timeout)
    i2c.resetBP()
    i2c.BBmode()
    i2c.enter_I2C()
    # i2c.cfg_pins(I2CPins.POWER | I2CPins.PULLUPS)
    i2c.set_speed(I2CSpeed._400KHZ)
    i2c.timeout(0.2)


def i2c_read(addr, reg, sz):
    i2c.write_then_read(chr(addr << 1) + reg, 0)
    return i2c.write_then_read(chr((i2c_addr << 1)|1), sz)


def i2c_write(addr, reg, data):
    i2c.write_then_read(chr(addr << 1) + reg + data, 0)


def do_shell():
    global i2c_addr
    run = True
    while run:
        cmd = raw_input(">>> ")
        cmd.strip()
        if cmd.startswith("r"):
            # >>> r 0c 1
            reg, sz = cmd.split(" ")[1:]
            reg = reg.decode("hex")
            sz = int(sz)
            reply = i2c_read(i2c_addr, reg, sz)
            print "REPR:", repr(reply)
            print "HEX:", ":".join(map(lambda x: x.encode("hex"), reply))

        elif cmd.startswith("w"):
            # >>> w 1234 abcd
            reg, data = cmd.split(" ")[1:]
            reg = reg.decode("hex")
            data = data.decode("hex")
            i2c_write(i2c_addr, reg, data)

        elif cmd.startswith("d"):
            all_regs = i2c_read(i2c_addr, "\x00", 128)
            header = []
            regs = []
            for i in xrange(0, 0x40):
                header.append("%02X" % i)
                regs.append("%02X" % ord(all_regs[i]))
            print "=" * (0x40*3)
            print "|".join(header)
            print ":".join(regs)
            header = []
            regs = []
            print "-" * (0x40*3)

            for i in xrange(0x40, 0x80):
                header.append("%02X" % i)
                regs.append("%02X" % ord(all_regs[i]))
            print "|".join(header)
            print ":".join(regs)

        elif cmd.startswith("q"):
            run = False
            print "bye bye ..."

        # elif repr(cmd) == '\x1b[A':
        #     print "AAAAAA"
        #     sys.stdin(last_cmd)
        #     print last_cmd
        #     cmd = last_cmd

        else:
            print "unknown command %s" % repr(cmd)
            print "read command: r <reg> <len>"
            print "  example: r 0c 1"
            print "write command: w <reg> <data>"
            print "  example: w 0C A3"

        # last_cmd = cmd


def decode_frames(buf):
    first_tr = True
    last_pos = 0
    frames = []
    tp = re.compile("\[(.*?)\]")

    for m in tp.finditer(buf):
        if first_tr:
            first_tr = False
            if m.start() != 0:
                print "warning, we are skipping some data ..."

        # syntax: [\][byte][+-]
        data = filter(bool, m.group(1).split("\\")) # split by '\' and remove empty strings

        """ first byte has a special meaning """
        addr = hex(ord(data[0][0]) >> 1)
        op = "READ" if ord(data[0][0]) & 0x1 else "WRITE"
        ack = "ACK" if data[0][1] ==  "+" else "NAK"
        data.pop(0)

        data = [d[0] for d in data]

        frames.append((op, addr, data))
        last_pos = m.end()

    print frames
    return frames, buf[last_pos:]



def process_transactions():
    pass


def do_monitor():
    buf = ""
    frames = []
    transactions = []
    print "press Enter to stop"
    i2c.start_bus_sniffer()
    while len(select.select([sys.stdin], [], [], 0.1)[0]) == 0:
        data = i2c.response(1000, return_data=True)
        if data:
            # print repr(data.incode()
            print "len:%s" % len(data)
            # print "Got: %s" % str(" ".join(map(hex,map(ord,data))))
            print "Got: %s" % repr(data)
            buf += data
            frms, buf = decode_frames(buf)
            frames.extend(frms)
            # buf += data
            # buf, new_transactions = decode_frames(buf)

    i2c.stop_bus_sniffer()


def main():
    global i2c_addr

    if len(sys.argv) == 1:
        print "Usage: %s <shell> [target i2c addr]" % os.path.splitext(sys.argv[0])[0]
        print "\tExample: %s shell 0x1a" % os.path.splitext(sys.argv[0])[0]
        sys.exit()

    print "setting up BP to I2C"
    config_bp_i2c()

    if sys.argv[1].lower() == "shell":
        if len(sys.argv) > 2:
            i2c_addr = int(sys.argv[2], 16)
        print "starting shell ... I2C ADDR:0x%02X" % i2c_addr
        do_shell()

    if sys.argv[1].lower() == "monitor":
        if len(sys.argv) > 2:
            i2c_addr = int(sys.argv[2], 16)
        print "starting I2C monitor ... filtering ADDR:0x%02X" % i2c_addr
        do_monitor()

    if sys.argv[1].lower() == "loop":
        print "starting ..."
        for i in xrange(0x60, 0xFF+1, 1):
            i2c_write(i2c_addr, "\x01", "\x01")
            time.sleep(0.02)
            print "trying: %02X" % i
            i2c_write(i2c_addr, "\x01", chr(i))
            time.sleep(0.5)
        print "done"


    # reset to command line
    i2c.resetBP()

if __name__ == '__main__':
    main()
