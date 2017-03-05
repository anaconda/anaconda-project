To build a local copy of the docs, install the programs in
docs/environment.yml and run 'make html'. If you use the conda
package manager these commands suffice:

```
git clone git@github.com:anaconda-platform/anaconda-project.git
cd anaconda-project/docs
conda env create
source activate anaconda-project-docs
make html
open build/html/index.html
```
