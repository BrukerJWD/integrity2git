import os
import subprocess
import time
import sys

"""
This is a small script around integrity2git.py to call it for many projects.
This code is neither beautiful nor well tested, but it seems to do the job.
"""

# File(s) with one MKS project path per line
files = [ "inputfile.txt" ]
# MKS prefix of all project paths
prefix = "c:/prefix/"
# Encoding of Console and MKS
encoding = "Windows-1252"
# Command to the other python script
conversion_command = r'C:\Python\python C:\integrity2git\mks_checkpoints_to_git.py --date-format "%d.%m.%Y %H:%M:%S" --input-encoding "' + encoding + '"'


working_dir = os.getcwd()

def get_projects():
    projects = []
    for file in files:
        projects.extend(open(file, 'r').readlines())
    projects = set([ p.strip() for p in projects ])
    return projects

def check_project_existance(projects):
    data = subprocess.check_output("si projects")
    existing_projects = [ p.decode(encoding).strip() for p in data.split(b"\n") ]
    wrong_projects = [ p for p in projects if p not in existing_projects ]
    if (wrong_projects):
        raise Exception("These projects do not exist: "+ "\n".join(wrong_projects))

def convert_project(projectPath):
    # create directory (removing some prefix)
    dir = projectPath[len(prefix):]
    #if os.path.isdir(dir): return
    print(f"##### {projectPath} #####", file=sys.stdout, flush=True)
    print(f"##### {projectPath} #####", file=sys.stderr, flush=True)
    os.makedirs(dir)
    os.chdir(dir)
    # run the conversion
    subprocess.run("git init")
    subprocess.run("git checkout -b main --quiet")
    subprocess.run(conversion_command + ' "' + projectPath + '"')



projects = get_projects()
check_project_existance(projects)
for project in projects:
    os.chdir(working_dir)
    convert_project(project)
