#!/usr/bin/env python

import sys,re

# to find and print list of bad instances. 
# take input from stdin
# print to stdout
# no output if no "bad" instance found

clat_threshold=7000
p = re.compile(' avg=[0-9\.]+,')

'''
format of input:
     aws_instance.member (remote-exec):     clat (usec): min=104, max=93265, avg=19980.03, stdev=20666.44
     aws_instance.member (remote-exec):     clat (usec): min=105, max=97675, avg=20374.75, stdev=20305.26
'''

for line in sys.stdin:

    m = re.search('clat \(msec\):', line)
    
    if m:
        # sometime it is really bad, clat will be in msec level
        i = re.search('(aws_instance.[a-zA-Z0-9_\.]+) ', line)
        if i:
            print  i.group(1)
    else:
        t = re.search(' avg=([0-9\.]+),', line)
        if float(t.group(1)) > 7000.00:
            i = re.search('(aws_instance.[a-zA-Z0-9_\.]+) ', line)
            if i:
                print  i.group(1)

