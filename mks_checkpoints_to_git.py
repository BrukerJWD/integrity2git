#!/usr/bin/python

# ADDITIONAL CONFIGURATION
additional_si_args = ""
ignore_devpaths = []
rename_devpaths = {}
ignore_revisions = []
ignore_tags = []
rename_tags = {}

def convert_branch_name(name: str):
    if name in rename_devpaths:
        name = rename_devpaths[name]
    else:
        name = name.replace(" ", "_")
    return name
def convert_tag_name(name: str):
    if name in rename_tags:
        name = rename_tags[name]
    else:
        name = name.replace(" ", "_")
    return name


import os, sys, re, time, platform, shutil
import subprocess
import locale
import argparse
import tempfile
from datetime import datetime
from git import Repo
from typing import List, Tuple

parser = argparse.ArgumentParser(description="Convert MKS to Git")
parser.add_argument("pathToProject",                help="MKS' path to project.pj that shall be converted")
parser.add_argument("--date-format",                help="alternative date format for parsing MKS' output", default="%x %X")
parser.add_argument("--input-encoding",             help="encoding that MKS uses to output it's information", default="cp850")
parser.add_argument("--drop-and-create-sandboxes",  help="don't use retarget, but drop the sandbox and create it again", action='store_true')
args = parser.parse_args()

assert os.path.isdir(".git"), "Call git init first"




class Console:
    @staticmethod
    def trace(message: str):
        """
        Writes a message to stdout
        """
        print("%s %s" % (datetime.now().strftime("%H:%M:%S"), message))

    @staticmethod
    def error(message: str):
        """
        Writes a message to stderr
        """
        print(message, file=sys.stderr)

    @classmethod
    def set_total_steps(cls, total_steps: int, already_done: int=0):
        cls.total_steps = total_steps
        cls.current_step = already_done

    @classmethod
    def step(cls):
        cls.current_step += 1
        Console.trace("%d of %d (%0.2f%%)" % (cls.current_step, cls.total_steps, cls.current_step/cls.total_steps*100))



class GitFastImport:
    def __init__(self):
        self.process = subprocess.Popen(["git", "fast-import"], stdin=subprocess.PIPE)

    def command(self, data: str):
        """
        Writes a command to git fast-import
        """
        self.process.stdin.write(data.encode("utf-8"))
        self.process.stdin.write('\n'.encode("utf-8"))

    def export_data(self, string: bytes):
        """
        Writes binary data to git
        """
        self.process.stdin.write(('data %d\n' % len(string)).encode("utf-8"))
        self.process.stdin.write(string)
        self.process.stdin.write('\n'.encode("utf-8"))

    def export_string(self, string: str):
        """
        Writes a string to git
        """
        self.export_data(string.encode("utf-8"))

    def export_file(self, filename: str, code = 'M', mode = '644'):
        """
        Writes a file to git
        """
        content = open(filename, 'rb').read()
        if platform.system() == 'Windows':
            #this is a hack'ish way to get windows path names to work git (is there a better way to do this?)
            filename = filename.replace('\\','/')
        self.command("%s %s inline %s" % (code, mode, filename))
        self.export_data(content)


class MKS:
    def __init__(self, project: str):
        self.project = project.replace('"', '')
        if not project.endswith(".pj"): self.project += "/project.pj"
        self.projectName = os.path.basename(self.project)
        self.sandboxPath = os.path.join(os.getcwd(), "tmp").replace("\\", "/")
        pass

    class Revision:
        def __init__(self):
            self.number = None          # str with version number
            self.author = None          # str
            self.seconds = None         # posix time
            self.tags = None            # list of Tags with tags for this revision
            self.description = None     # str message
            self.ancestor = None        # previous Revision

    class Tag:
        def __init__(self, name):
            self.name = name                            # str with name of tag in MKS
            self.git_name = convert_tag_name(name)      # str with name of tag in Git

    class DevPath:
        def __init__(self, name, ancestor):
            self.name = name                            # str with name of branch in MKS
            self.git_name = convert_branch_name(name)   # str with alternative name of branch
            self.ancestor = ancestor                    # str with revision where the branch starts, and after a while the Revision with this number
            self.revisions = None                       # Revisions in this branch


    def __si(self, command: str) -> str:
        """
        Executes the MKS CLI command
        """
        Console.trace(command)
        for i in range(20):
            try:
                data = subprocess.check_output(command, stderr=subprocess.STDOUT)
                exitcode = 0
            except subprocess.CalledProcessError as ex:
                data = ex.output
                exitcode = ex.returncode
            if data[-1:] == '\n':
                data = data[:-1]

            if exitcode == 0: break
            Console.error(">>> Returned %d: %s" % (exitcode, data))
            Console.error(">>> %s trying again" % datetime.now().strftime("%H:%M:%S"))
            time.sleep(1)
        else:
            raise Exception("Command failed")
        return data.decode(args.input_encoding)


    def retrieve_revisions(self, devpath: DevPath=None) -> List[Revision]:
        devpathStr = '"' + devpath.name + '"' if devpath else ":current"

        versions = self.__si('si viewprojecthistory %s --quiet --rfilter=devpath:%s --project="%s"' % (additional_si_args, devpathStr, self.project))
        versions = versions.split('\n')
        versions = versions[1:]
        version_re = re.compile('^\d+(\.\d+)+\t')

        revisions = []
        for version in versions:
            match = version_re.match(version)
            if match:
                version_cols = version.split('\t')
                revision = MKS.Revision()
                revision.number = version_cols[0]
                revision.author = version_cols[1]
                revision.seconds = int(time.mktime(datetime.strptime(version_cols[2], args.date_format).timetuple()))
                revision.tags = [ MKS.Tag(v) for v in version_cols[5].split(",") if v and v not in ignore_tags ]
                revision.description = version_cols[6]
                if not revision.number in ignore_revisions:
                    revisions.append(revision)
            else: # append to previous description
                if not version: continue
                if revision.description: revision.description += '\n'
                revision.description += version

        revisions.reverse() # Old to new
        return revisions

    def retrieve_devpaths(self) -> List[DevPath]:
        devpaths = self.__si('si projectinfo %s --devpaths --quiet --noacl --noattributes --noshowCheckpointDescription --noassociatedIssues --project="%s"' % (additional_si_args, self.project))
        devpaths = devpaths [1:]
        devpaths_re = re.compile('    (.+) \(([0-9][\.0-9]+)\)\n')
        devpath_col = devpaths_re.findall(devpaths)
        devpath_col.sort(key=lambda x: [int(i) for i in x[1].split('.')]) #order development paths by version
        return [ MKS.DevPath(dp[0], dp[1]) for dp in devpath_col if not dp[0] in ignore_devpaths ]

    def create_sandbox(self, revision: Revision):
        self.__si('si createsandbox %s --populate --recurse --quiet --project="%s" --projectRevision=%s "%s"' % (additional_si_args, self.project, revision.number, self.sandboxPath))

    def drop_sandbox(self):
        self.__si('si dropsandbox --yes -f --delete=all "%s/%s"' % (self.sandboxPath, self.projectName))

    def retarget(self, revision: Revision):
        self.__si('si retargetsandbox %s --quiet --project="%s" --projectRevision=%s "%s/%s"' % (additional_si_args, self.project, revision.number, self.sandboxPath, self.projectName))

    def resync(self):
        self.__si('si resync --yes --recurse %s --quiet --sandbox="%s/%s"' % (additional_si_args, self.sandboxPath, self.projectName))

    def retarget_to(self, revision: Revision):
        if args.drop_and_create_sandboxes:
            self.drop_sandbox()
            self.create_sandbox(revision)
        else:
            self.retarget(revision)
            self.resync()
        return



class Convert:
    def __init__(self, mks: MKS, git: GitFastImport):
        self.mks = mks
        self.git = git
        self.repo = Repo(os.getcwd())
        self.marks = {}
        Console.trace("Git directory: %s" % self.repo.common_dir)
        pass


    def export_to_git(self, revisions, devpath: MKS.DevPath=None):
        if len(revisions) == 0: return

        git_folder_re = re.compile("\.git(\\\|$)")  #any path named .git, with or without child elements. But will not match .gitignore

        if revisions[0].ancestor: ancestor = revisions[0].ancestor
        elif devpath: ancestor = devpath.ancestor
        else: ancestor = None

        for revision in revisions:
            Console.step()

            mark = self.marks[revision.number]

            self.mks.retarget_to(revision)

            if devpath: self.git.command('commit refs/heads/devpath/%s' % devpath.git_name)
            else:       self.git.command('commit refs/heads/master')
            self.git.command('mark %s' % mark)
            self.git.command('committer %s <> %d +0000' % (revision.author, revision.seconds))
            self.git.export_string(revision.description)
            if ancestor:
                self.git.command('from %s' % self.marks[ancestor.number]) # we're starting a development path so we need to start from where it was originally branched from
                ancestor = None #set to zero so it doesn't loop back in to here
            self.git.command('deleteall')
            tree = os.walk('.')
            for dir in tree:
                for filename in dir[2]:
                    if (dir[0] == '.'):
                        fullfile = filename
                    else:
                        fullfile = os.path.join(dir[0], filename)[2:]
                    if '.pj' in fullfile: continue
                    if git_folder_re.search(fullfile): continue
                    if 'mks_checkpoints_to_git' in fullfile: continue
                    self.git.export_file(fullfile)

            for tag in revision.tags:
                self.git.command('tag %s' % tag.git_name)
                self.git.command('from %s' % mark)
                self.git.command('tagger %s <> %d +0000' % (revision.author, revision.seconds))
                self.git.export_string("") # Tag message

        self.git.command('checkpoint')

    def find_continuation_point(self, done_count: int, revisions: List[MKS.Revision]) -> Tuple[int, List[MKS.Revision]]:
        if not self.repo.head.is_valid(): return done_count, revisions
        last_commit_date = self.repo.head.commit.committed_date
        revisions2 = [r for r in revisions if r.seconds > last_commit_date]
        done_count += len(revisions) - len(revisions2)
        if len(revisions2) > 0:
            revisions2[0].ancestor = revisions[len(revisions) - len(revisions2)-1]
        return done_count, revisions2

    def find_continuation_point_devpath(self, done_count: int, devpath: MKS.DevPath) -> int:
        branch = [ b for b in self.repo.branches if b.path == "refs/heads/devpath/" + devpath.git_name]
        if len(branch) == 0: return done_count
        last_commit_date = branch[0].commit.committed_date
        revisions2 = [r for r in devpath.revisions if r.seconds > last_commit_date]
        done_count += len(devpath.revisions) - len(revisions2)
        if len(revisions2) > 0:
            revisions2[0].ancestor = devpath.revisions[len(devpath.revisions) - len(revisions2)-1]
        devpath.revisions = revisions2
        return done_count

    def create_marks(self, master_revisions : List[MKS.Revision], devpaths : List[MKS.DevPath]):
        def convert_revision_to_mark(revision : MKS.Revision, allowNew, date=False):
            if revision.number in self.marks:
                return self.marks[revision.number]

            if allowNew:
                mark = ":" + str(len(self.marks)+1)
                self.marks[revision.number] = mark
                return mark
            else:
                assert date, "No date given, cannot find commit"
                date = datetime.strftime(datetime.fromtimestamp(date), args.date_format)
                commits = [c for c in self.repo.iter_commits("--all", before=date, after=date)]
                if len(commits) == 0: assert len(commits) == 1, "No commit found for date " + date
                assert len(commits) == 1, f"Multiple commits found for date {date}: " + ", ".join([c.hexsha for c in commits])
                self.marks[revision.number] = commits[0].hexsha
                return commits[0].hexsha

        if len(master_revisions) > 0:
            if master_revisions[0].ancestor: # we are continuing master
                convert_revision_to_mark(master_revisions[0].ancestor, allowNew=False, date=master_revisions[0].ancestor.seconds)
            for revision in master_revisions:
                convert_revision_to_mark(revision, allowNew=True)
        for devpath in devpaths:
            convert_revision_to_mark(devpath.ancestor, allowNew=False, date=devpath.ancestor.seconds)
            if devpath.revisions and devpath.revisions[0].ancestor: # we are continuing branch
                convert_revision_to_mark(devpath.revisions[0].ancestor, allowNew=False, date=devpath.revisions[0].ancestor.seconds)
            for revision in devpath.revisions:
                convert_revision_to_mark(revision, allowNew=True)


    def check_tags_for_uniqueness(self, all_revisions: List[MKS.Revision]):
        """
        Check whether all tags of all revisions are unique, possibly case insensitive
        """
        def is_filesystem_case_sensitive():
            tmphandle, tmppath = tempfile.mkstemp()
            case_sensitive = not os.path.exists(tmppath.upper())
            os.close(tmphandle)
            os.remove(tmppath)
            return case_sensitive
        case_sensitive = is_filesystem_case_sensitive()

        class RevisionInfo:
            def __init__(self, revision, tag):
                self.revision = revision
                self.tag = tag

        tags = {}
        for revision in all_revisions:
            for tag in revision.tags:
                tagL = tag.git_name if case_sensitive else tag.git_name.lower()
                tags.setdefault(tagL, []).append(RevisionInfo(revision, tag))

        error = False
        for tag, revisions in tags.items():
            if len(revisions) > 1:
                error = True
                if not case_sensitive:
                    Console.error(f"{len(revisions)} revisions found for tag {tag}: " + ", ".join([ f"{ri.revision.number} ({ri.tag.git_name})" for ri in revisions ]))
                    Console.error("This error is raised to avoid problems with a case-insensitive file system (see README)")
                else:
                    Console.error(f"{len(revisions)} revisions found for tag {tag.git_name}: " + ", ".join([ ri.revision.number for ri in revisions ]))
        assert not error, "duplicate tags"

    def check_branch_tag_names(self, names: List[str], type: str):
        """
        Check the name of a branch or a tag for git compliance
        """
        def git_check(name: str):
            process = subprocess.Popen(["git", "check-ref-format", "--branch", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            exit_status = process.wait()
            return exit_status == 0

        def begins_width_dot(name: str):
            for part in name.split("/"):
                if part.startswith("."): return "Begins with '.'"
            return None
        def ends_with_lock(name: str):
            if name.endswith(".lock"): return "Ends with '.lock'"
            return None
        def ends_with_dot(name: str):
            if name.endswith("."): return "Ends with '.'"
            return None
        def dot_dot(name: str):
            if ".." in name: return "Contains '..'"
            return None
        def backslash(name: str):
            if "\\" in name: return "Contains '\\'"
            return None
        def at_brace(name: str):
            if "@{" in name: return "Contains '@{'"
        def invalid_chars(name: str):
            invalids = set(re.compile("[\000-\037\177 ~^:?*[]").findall(name))
            if invalids: return "Contains any of '" + "".join(invalids) + "'"
            return None
        def at(name: str):
            if name == "@": return "It's simply @"
            return None

        checks = [begins_width_dot, ends_with_lock, ends_with_dot, dot_dot, backslash, at_brace, invalid_chars, at]

        any_error = False
        for name in names:
            #if git_check(name): continue # takes too much time
            errors = []
            for check in checks:
                errors.append(check(name))
            errors = [ e for e in errors if e ]
            if errors:
                any_error = True
                Console.error(f"{type} name '{name}' is invalid: " + ", ".join(errors))
        assert not any_error, f"{type} names are incorrect"




git = GitFastImport()
mks = MKS(args.pathToProject)
convert = Convert(mks, git)


Console.trace("Retreiving master revisions")
all_revisions = mks.retrieve_revisions()
revisions = all_revisions[:]

Console.trace("Retreiving branches")
devpaths = mks.retrieve_devpaths()
Console.trace("Retreiving branch revisions")
for devpath in devpaths:
    devpath.revisions = mks.retrieve_revisions(devpath)
    all_revisions.extend(devpath.revisions)

for devpath in devpaths:
    ancestors = [ r for r in all_revisions if r.number == devpath.ancestor ]
    if len(ancestors) == 0: assert len(ancestors) == 1, f"Could not find ancestor revision {devpath.ancestor} for devpath {devpath.name}"
    assert len(ancestors) == 1, f"Multiple ancestor revisions found for devpath {devpath.name}: " + ", ".join([ a.number for a in ancestors ])
    devpath.ancestor = ancestors[0]

Console.trace("Checking branch and tag names")
convert.check_branch_tag_names([dp.git_name for dp in devpaths], "Branch")
convert.check_tags_for_uniqueness(all_revisions)
convert.check_branch_tag_names([t.git_name for rev in all_revisions for t in rev.tags ], "Tag")


Console.trace("Checking where to continue conversion")
done_count = 0
done_count, revisions = convert.find_continuation_point(done_count, revisions)
for devpath in devpaths:
    done_count = convert.find_continuation_point_devpath(done_count, devpath)


Console.set_total_steps(len(all_revisions), done_count)
Console.trace(f"Found {len(revisions)} revisions and {len(devpaths)} devpaths")
if len(revisions) == 0 and sum([ len(dp.revisions) for dp in devpaths ]) == 0:
    exit(0)

convert.create_marks(revisions, devpaths)
convert.repo = None # Close handle on git repository

if not os.path.isdir(mks.sandboxPath):
    # Create a build sandbox of the first revision
    revision = None
    if len(revisions) > 0:
        revision = revisions[0]
    else:
        for devpath in devpaths:
            if len(devpath.revisions) > 0:
                revision = devpath.revisions[0]
                break

    mks.create_sandbox(revision)

os.chdir(mks.sandboxPath)
convert.export_to_git(revisions) # export master branch first

for devpath in devpaths:
    convert.export_to_git(devpath.revisions, devpath)
os.chdir("..")

mks.drop_sandbox()
