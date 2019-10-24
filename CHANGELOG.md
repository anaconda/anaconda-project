# CHANGE LOG FOR ANACONDA PROJECT

We [keep a changelog.](http://keepachangelog.com/)

## Version 0.8.4 (2019/10/24) - Public Release

### Issues Closed

* [Issue 201](https://github.com/Anaconda-Platform/anaconda-project/issues/201) Version pins were not respected in all cases. ([PR 203](https://github.com/Anaconda-Platform/anaconda-project/pull/203)/[227](https://github.com/Anaconda-Platform/anaconda-project/pull/227)/[233](https://github.com/Anaconda-Platform/anaconda-project/pull/233))

#### Enhancements

* [Issue 222](https://github.com/Anaconda-Platform/anaconda-project/issues/222) Make `env_specs` optional ([PR 232](https://github.com/Anaconda-Platform/anaconda-project/pull/232))
* [Issue 221](https://github.com/Anaconda-Platform/anaconda-project/issues/221) Accept additional user-defined fields without warnings ([PR 228](https://github.com/Anaconda-Platform/anaconda-project/pull/228)/[224](https://github.com/Anaconda-Platform/anaconda-project/pull/224))
* [Issue 204](https://github.com/Anaconda-Platform/anaconda-project/issues/204) `anaconda-project upload` to upload projects to Anaconda Cloud ([PR 208](https://github.com/Anaconda-Platform/anaconda-project/pull/208))
* [Issue 189](https://github.com/Anaconda-Platform/anaconda-project/issues/189) `anaconda-project prepare --all` will prepare all environments in a multi-environment project ([PR 213](https://github.com/Anaconda-Platform/anaconda-project/pull/213))
* [Issue 173](https://github.com/Anaconda-Platform/anaconda-project/issues/173) `anaconda-project prepare --refresh` will perform a full rebuild of a project environment ([PR 223](https://github.com/Anaconda-Platform/anaconda-project/pull/223)/[229](https://github.com/Anaconda-Platform/anaconda-project/pull/229))

## Version 0.8.3 (2019/06/20) - Public Release

### Issues Closed

* [Issue 202](https://github.com/Anaconda-Platform/anaconda-project/issues/201) - Not respecting version pins when adding new packages to a project ([PR 203](https://github.com/Anaconda-Platform/anaconda-project/pull/203))
* [Issue 154](https://github.com/Anaconda-Platform/anaconda-project/issues/154) - switching between prompts for commands on Windows ([PR 177](https://github.com/Anaconda-Platform/anaconda-project/pull/177))
* [Issue 70](https://github.com/Anaconda-Platform/anaconda-project/issues/70) - `run` in absence of yaml file should return error ([PR 176](https://github.com/Anaconda-Platform/anaconda-project/pull/176))
* [PR 171](https://github.com/Anaconda-Platform/anaconda-project/pull/171) - avoid crash in prepare/update if env_specs is missing
* [PR 167](https://github.com/Anaconda-Platform/anaconda-project/pull/167), [PR 142](https://github.com/Anaconda-Platform/anaconda-project/pull/142) - issues with the latest versions of pip, conda, tornado
* [PR 162](https://github.com/Anaconda-Platform/anaconda-project/pull/162) - properly honor `supports_http_options: false`

#### Enhancements

* [Issue 194](https://github.com/Anaconda-Platform/anaconda-project/issues/194) - Allow "dependencies" as a synonym for "packages" to facilitate use of `anaconda-project.yml` files by `conda env` ([PR 200](https://github.com/Anaconda-Platform/anaconda-project/pull/200))
* [PR 192](https://github.com/Anaconda-Platform/anaconda-project/pull/192) - Provide the ability to set a project uploaded to anaconda.org as private
* [PR 178](https://github.com/Anaconda-Platform/anaconda-project/pull/178) - Add an `--empty-environment` option to the `init` command
* [PR 144](https://github.com/Anaconda-Platform/anaconda-project/pull/144) - Remove `--no-deps` from pip install command

## Version 0.8.2 (2017/10/19) - Public Release

### Issues Closed

#### Enhancements

* [Issue 134](https://github.com/anaconda-platform/anaconda-project/issues/134) - Add bootstrap environments for projects to run plugins from there ([PR 109](https://github.com/Anaconda-Platform/anaconda-project/pull/109))

In this release 1 issue was closed.

### Pull Requests Merged

* [PR 109](https://github.com/anaconda-platform/anaconda-project/pull/109) - PR: Add bootstrap envs ([134](https://github.com/Anaconda-Platform/anaconda-project/issues/134))

In this release 1 pull request was closed


## Version 0.8.1 (2017/10/03) - Public Release

### Pull Requests Merged

* [PR 125](https://github.com/anaconda-platform/anaconda-project/pull/125) - PR: Update/test conda
* [PR 122](https://github.com/anaconda-platform/anaconda-project/pull/122) - PR: Fix copyright for brand change and add explicit license type
* [PR 119](https://github.com/anaconda-platform/anaconda-project/pull/119) - PR: Simplify setup to make it more standard and create scripts in scripts/ folder
* [PR 116](https://github.com/anaconda-platform/anaconda-project/pull/116) - PR: Enable configuration of environments paths via environment variable
* [PR 112](https://github.com/anaconda-platform/anaconda-project/pull/112) - PR: Update recipe
* [PR 111](https://github.com/anaconda-platform/anaconda-project/pull/111) - PR: Add LICENSE to manifest
* [PR 101](https://github.com/anaconda-platform/anaconda-project/pull/101) - PR: InfoPros docs rewrite [skip ci]
* [PR 100](https://github.com/anaconda-platform/anaconda-project/pull/100) - PR: Command Plugins 
* [PR 93](https://github.com/anaconda-platform/anaconda-project/pull/93) - PR: resolve using an underscore prefixed environment
* [PR 92](https://github.com/anaconda-platform/anaconda-project/pull/92) - PR: Rename plugins

In this release 10 pull requests were closed.
