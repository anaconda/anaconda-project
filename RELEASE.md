# Release process

## To release a new version of **anaconda-project** on PyPI:

**1.)** Ensure you have the latest version from upstream and update your fork

    git pull upstream master
    git push origin master

**2.)** Update [CHANGELOG.md](https://github.com/anaconda-platform/anaconda-project/blob/master/CHANGELOG.md), using loghub itself

    loghub anaconda-platform/anaconda-project -u <username> -m <milestone> -ilg type:feature "Features " -ilg type:enhancement "Enhancements" -ilg type:bug "Bugs fixed" -ilr "reso:completed"

**3.)** Update [`anaconda_project/version.py`](https://github.com/anaconda-platform/anaconda-project/blob/master/anaconda_project/version.py) (set release version, remove 'dev0')

**4.)** Commit changes

    git add .
    git commit -m "Set release version"

**5.)** Create distributions

    python setup.py sdist bdist_wheel

**6.)** Upload distributions

    twine upload dist/* -u <username> -p <password>

**7.)** Add release tag

    git tag -a vX.X.X -m 'Tag release version vX.X.X'

**8.)** Update `version.py` (add 'dev0' and increment minor or major as needed)

**9.)** Commint changes

    git add . 
    git commit -m "Restore dev version"

**10.)** Push changes
    
    git push origin master
    git push origin --tags

    git push upstream master
    git push upstream --tags


## To release a new version of **anaconda-project** on anaconda-platform:

**1.)** After the previous steps on pypi (and tagging) run:

    bash scripts/build_and_upload.sh

## To release a new version of **anaconda-project** on conda-forge:

**1.)** Ensure you have the latest version from upstream and update your fork

    git pull upstream master
    git push origin master

**2.)** Update [meta.yaml](https://github.com/anaconda-platform/anaaconda-project/blob/master/conda.recipe/meta.yaml) version and hash

**3.)** Commit changes

    git add .
    git commit -m "Update conda recipe"

**4.)** Update recipe on [conda-forge/anaconda-project-feedstock](https://github.com/conda-forge/anaconda-project-feedstock)

**5.)** Push changes

    git push upstream master
    git push origin master
