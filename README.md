# Export MKS (PTC) Integrity to GIT
* This python script will export the project history from MKS (PTC) Integrity to a GIT repository
* Currently imports checkpoints and development paths only
* This does not currently support incremental imports

## HOW TO USE
1. You must have
   - python on the PATH variable
   - si on the PATH variable (MKS/PTC command line tools)
   - git on the PATH variable
   - git-python (`pip install git-python`)
2. Make a folder for where you want your git repository to reside
3. Initialize the git repository by running `git init`
4. Execute  ```python mks_checkpoints_to_git.py <MKS_project_path/project.pj> | git fast-import``` from within the initialized git repository (this may take a while depending on how big your project is)
5. Once the import is complete, git will output import statistics

## Shared subprojects

MKS supports [shared subprojects](http://support.ptc.com/help/integrity_hc/integrity120_hc/en/IntegrityHelp/client_proj_adding_shared_subprojects.mif-1.html), i.e. the content of a specific version of a project can be included into another project. While git supports a similar mechanism ([git submodules](https://git-scm.com/book/de/v1/Git-Tools-Submodule)), the script does not convert between these two. Instead, the subprojects are recursively checked out from MKS and checked in into git as normal content. Thus, the shared-ness is lost.
