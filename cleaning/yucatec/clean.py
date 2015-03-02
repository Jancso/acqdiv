# -*- coding: utf-8 -*-

"""
Clean Yucatec corpus

# TODO: remove numbers that prepend lines

"Klar kann ich mich entsinnen, was die Zahlen bedeuten. Diese bezeichnen die Nummern, mit der die Sätze in den Kassetten erscheinen, ob das nach der Digitalisierung noch Wichtigkeit hat, bezweifle ich."

To be honest I'm not sure what this means (are they a kind of time stamp?), but since she says herself that the numbers are not relevant for digitised data, let's ignore (i.e. drop) those numbers. 
"""

import os
import re
import sys
import csv
from path import path


def replacement(line):
    for f, t in replacements:
        line = line.replace(f, t)
    return(line)

replacements = []
def get_replacements(filepath):
    # load replacement strings
    with open(filepath, "r") as infile:
        d = csv.reader(infile, delimiter=",")
        for row in d:
            if not len(row) == 2:
                sys.exit("Replacements input longer than two columns")
            replacements.append(tuple(row))

def rules(s):
    # be ware of feeding and bleeding substrings!
    s = re.sub(":\s+", ":\t", s, 1)
    s = re.sub("^@Begi$", "@Begin", s)
    s = re.sub("^@Fin$", "@End", s)
    return(s.strip())

def create_header(line):
    pass
    
cc = [6, 130, 26, 96]
def normalize_sting(line):
    # remove weird characters
    return ''.join(c for c in line if not ord(c) in cc)

changeables = ["@Activities:", "@Bck:", "@Bg", "@Bg:", "@Blank", "@Comment:", "@Date:", "@Eg", "@Eg:", "@EndTurn", "@G:", "@New Episode", "@New Language:", "@Page", "@Situation:", "@T:"]
header = ["@UTF8", "@Begin", "@Languages:\tiku"]
no_tab = ["@UTF8", "@Begin", "@End", "@New Episode"]

def process(path):
    infile = open(path, "r")
    outpath = path.replace(path.ext, ".cha")
    outfile = open(outpath, "w")

    # TODO: create header

    # process file contents
    n = 0
    line = infile.readline()
    prev = ""
    while len(line) > 0:
        n += 1
        line = line.strip()
        line = normalize_sting(line) # do character replacements for each line
        line = replacement(line) # do manual replacements for each line
        line = rules(line) # do regex replacements for each line

        # skip blank lines, etc.
        if line == "" or line == "*" or line == "%" or line == " ":
            line = infile.readline()
            continue

        # skip empty header lines
        if line.startswith("@") and line.endswith(":") or line.endswith(":\t"):
            line = infile.readline()
            continue

        # skip empty body lines
        if line.startswith("%") and line.endswith(":") or line.endswith(":\t"):
            line = infile.readline()
            continue

        # catch broken lines
        if not line.startswith("*") and not line.startswith("@") and not line.startswith("%"):
            prev += " "+line
            line = infile.readline()
        else:
            if prev:
                outfile.write(prev+"\n")
            prev = line
            line = infile.readline()
    if prev:
        outfile.write(prev+"\n")

    outfile.write("@End\n")
    infile.close()
    outfile.close()

def main(dir, type):
    # get_replacements("notes/replacements.csv")
    # get_participants()
    # TODO -- add in participants data; create the @Ids...
    for f in path(dir).files(type):
        if not f.basename().startswith('.'):
            process(f)
            print("PROCESSING:", f.basename())

if __name__=="__main__":
    dir = sys.argv[1]
    type = sys.argv[2]
    main(dir, type)
    print(dir, type)

# python clean.py ../yucatec/cha *.txt
