# Export MKS (PTC) Integrity to GIT
* This python script will export the project history from MKS (PTC) Integrity to a GIT repository
* Currently imports checkpoints and development paths only
* This does not currently support incremental imports

## HOW TO USE
1. You must have
   - `python` on the PATH variable
   - `si` on the PATH variable (MKS/PTC command line tools)
   - `git` on the PATH variable
   - GitPython module (`pip install GitPython`)
2. Make a folder for where you want your git repository to reside
3. Initialize the git repository by running `git init`
4. Execute  ```python mks_checkpoints_to_git.py <MKS_project_path/project.pj>``` from within the initialized git repository (this may take a while depending on how big your project is)
   * You may need to execute `export MSYS_NO_PATHCONV=1` to prevent Git Bash from expanding the path to the project file.
   * If you need to change the date format add the parameters: `--date-format "<format directives>"` with the format directives you wish to use.
5. Once the import is complete, git will output import statistics
6. Run `git reset head --hard` to resynchronize your git folder.


## Optional arguments

### Date parsing

The date depends on the locale. Depending on the locale settings of your machine the [datetime format string](https://www.programiz.com/python-programming/datetime/strftime#format-code) has to be adjusted. You can use the command line argument `--date-format "..."` to achieve that.

### Encoding

It is not really clear to me what encoding `si` is using. There are some settings in the MKS preferences, but I do not know which one is affecting si. If you get error regarding the encoding or some characters are replaced by question marks, this helped for me:

 - set encoding of Windows command line to Windows-1252: `CHCP 1252`
 - add argument: `--input-encoding windows-1252`

### Retarget&Resync vs. Drop&Create

Some projects are messed up in a way, that retargeting the sandbox is not possible, e.g. it fails for many revisions with a corrupt subproject (or so). For this case, one can pass the argument `--drop-and-create-sandboxes` as a more robust, but also more slow way to iterate through the checkpoints in MKS.

## Known bugs/problems

### Shared subprojects

MKS supports [shared subprojects](http://support.ptc.com/help/integrity_hc/integrity120_hc/en/IntegrityHelp/client_proj_adding_shared_subprojects.mif-1.html), i.e. the content of a specific version of a project can be included into another project. While git supports a similar mechanism ([git submodules](https://git-scm.com/book/de/v1/Git-Tools-Submodule)), the script does not convert between these two. Instead, the subprojects are recursively checked out from MKS and checked in into git as normal content. Thus, the shared-ness is lost.

### Tags that differ only in case

MKS and git both have case-sensitive tags (i.e., the tag "abcd" and "Abcd" are not the same). If `git fast-import` is running on a case-insensitive filesystem (like NTFS), such tags are considered duplicate ([see mailing list](https://marc.info/?l=git&m=155157276401181&w=2) and git fails with an error like "cannot lock ref". In this case you either have to ignore one of the tags (e.g. because it is a duplicate anyway, by adding it to `ignore_tags`) or use a case-sensitive filesystem (NTFS can do that, too: `fsutil.exe file SetCaseSensitiveInfo C:\sensitive enable`).

### DevPath that equals :current

Some of our projects seem to have a development path that equals the Normal path. It leads to errors such as "duplicate tag detected" for many, many revisions. I do not know how these development paths were created or how to distinguish them from regular development paths. My only recommendation is to ignore this devpath completely by adding it to `ignore_devpaths`

### Encoding for devpath names

If a development path's name contains special characters, the script may exit with the following error:

> UnboundLocalError: local variable 'revision' referenced before assignment

This is caused by `si` not being able to correctly parse the command line argument with the specified devpath. With [this question](https://community.ptc.com/t5/Integrity-Windchill-Systems/Are-CLI-commands-taking-into-account-the-code-page-that-is-set/td-p/142055) in mind, I assume that `si` is always parsing the command line arguments using the codepage of its projects, but python3 uses UTF-8.

Perhaps we could use the `--selectionFile` argument to work around this issue.

### "Unsupported command: 10:32:05"

Do not pipe this script's output to `git fast-import` anymore. Instead, the script will launch `git fast-import` itself to talk to it directly. The conversion can still have succeded, though.

### Corrupt checkpoints

Some checkpoints in MKS may be corrupt (e.g., a member revision is missing). To still be able to convert the project, one can skip checkpoints by adding it to `ignore_revisions`

### Invalid branch or tag names

Git branches and tags do have (other) restrictions on [which characters one can use](https://wincent.com/wiki/Legal_Git_branch_names). To map a branch/tag to another name, add an entry to the map `rename_devpaths` or `rename_tags` respectively. If you want to apply some more general conversion (e.g. replacing all '>' by '-') you can add a rule in the functions `convert_branch_name` or `convert_tag_name` respectively.

Other restrictions are added by the operating system because a lock file is created for each tag. Thus, a tag cannot contain characters that are not allowed in filenames (e.g. '<' on Windows). These restrictions are not checked beforehand and don't lead to an abortion of the conversion. You can only see the errors being printed to the console by `git`.

### Deleted development paths

If development paths have been deleted, their revisions are not converted. If from such a deleted devpath another devpath was created, the conversion script may fail as it does not know about the base revision of the existing devpath.
