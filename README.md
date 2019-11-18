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
4. Execute  ```python mks_checkpoints_to_git.py <MKS_project_path/project.pj> | git fast-import``` from within the initialized git repository (this may take a while depending on how big your project is)
   * You may need to execute `export MSYS_NO_PATHCONV=1` to prevent Git Bash from expanding the path to the project file.
   * If you need to change the date format add the parameters: `--date-format "<format directives>"` with the format directives you wish to use.
5. Once the import is complete, git will output import statistics
6. Run `git reset head --hard` to resynchronize your git folder.


## Known bugs/problems

### Shared subprojects

MKS supports [shared subprojects](http://support.ptc.com/help/integrity_hc/integrity120_hc/en/IntegrityHelp/client_proj_adding_shared_subprojects.mif-1.html), i.e. the content of a specific version of a project can be included into another project. While git supports a similar mechanism ([git submodules](https://git-scm.com/book/de/v1/Git-Tools-Submodule)), the script does not convert between these two. Instead, the subprojects are recursively checked out from MKS and checked in into git as normal content. Thus, the shared-ness is lost.

### Date parsing

The date depends on the locale. Depending on the locale settings of your machine the [datetime format string](https://www.programiz.com/python-programming/datetime/strftime#format-code) has to be adjusted. You can use the command line argument `--date-format "..."` to achieve that.

### Tags that differ only in case

MKS and git both have case-sensitive tags (i.e., the tag "abcd" and "Abcd" are not the same). If `git fast-import` is running on a case-insensitive filesystem (like NTFS), such tags are considered duplicate ([see mailing list](https://marc.info/?l=git&m=155157276401181&w=2) and git fails with an error like "cannot lock ref". In this case you either have to ignore one of the tags (e.g. because it is a duplicate anyway, probably in line 86) or use a case-sensitive filesystem (NTFS can do that, too: `fsutil.exe file SetCaseSensitiveInfo C:\sensitive enable`).

