# CHANGE LOG FOR ANACONDA PROJECT

We [keep a changelog.](http://keepachangelog.com/)

## Version 0.11.0

### Bug fixes

* [PR 326](https://github.com/Anaconda-Platform/anaconda-project/pull/326) Fix extract for zipfiles from Github/Gitlab
* [PR 356](https://github.com/Anaconda-Platform/anaconda-project/pull/356) Add tdqm dependency for progress bars. Resolves [355](https://github.com/Anaconda-Platform/anaconda-project/issues/355), [382](https://github.com/Anaconda-Platform/anaconda-project/issues/382)
* [PR 380](https://github.com/Anaconda-Platform/anaconda-project/pull/380) realpath for safety on Windows. Resolves [Issue 379](https://github.com/Anaconda-Platform/anaconda-project/issues/379) and [Issue 344](https://github.com/Anaconda-Platform/anaconda-project/issues/344)

### Enhancements

* [PR 352](https://github.com/Anaconda-Platform/anaconda-project/pull/352) Add Linux and Mac arm platforms. Resolves [Issue 336](https://github.com/Anaconda-Platform/anaconda-project/issues/336) and [PR 274](https://github.com/Anaconda-Platform/anaconda-project/pull/274) **Breaking change**

### Maintenance

* [PR 358](https://github.com/Anaconda-Platform/anaconda-project/pull/358) Update CONTRIBUTING.md
* Docs PRs [369](https://github.com/Anaconda-Platform/anaconda-project/pull/369), [370](https://github.com/Anaconda-Platform/anaconda-project/pull/370), [371](https://github.com/Anaconda-Platform/anaconda-project/pull/371), [372](https://github.com/Anaconda-Platform/anaconda-project/pull/372), [373](https://github.com/Anaconda-Platform/anaconda-project/pull/373), [374](https://github.com/Anaconda-Platform/anaconda-project/pull/374)
* [PR 384](https://github.com/Anaconda-Platform/anaconda-project/pull/384) Drop Python 2.7 tests, add Python 3.9, 3.10 and Conda 4.11 - 4.13

### Issues closed
* [Issue 339](https://github.com/Anaconda-Platform/anaconda-project/issues/339) Downloading a file with no content-length in its header fails
* [Issue 379](https://github.com/Anaconda-Platform/anaconda-project/issues/379) infinite loop on windows: searching for files
* [Issue 344](https://github.com/Anaconda-Platform/anaconda-project/issues/344) Anaconda-project appears to lockup if run on an empty directory.
* [Issue 336](https://github.com/Anaconda-Platform/anaconda-project/issues/336) Allow one to use --override-channels for reproducibility

## Version 0.10.2

### Bug fixes

* [PR 340](https://github.com/Anaconda-Platform/anaconda-project/pull/340) Fix issue with progress bar



## Version 0.10.1

### Enhancements

* [PR 331](https://github.com/Anaconda-Platform/anaconda-project/pull/331) Add CLI progress bars for project download and extract
* [PR 330](https://github.com/Anaconda-Platform/anaconda-project/pull/330) Add CLI progress bars for data downloads

## Version 0.10.0

### Issues Closed

* [Issue 77](https://github.com/Anaconda-Platform/anaconda-project/issues/77) anaconda-project download feature request ([PR 217](https://github.com/Anaconda-Platform/anaconda-project/pull/217))
* [Issue 148](https://github.com/Anaconda-Platform/anaconda-project/issues/148) Packages installed when none requested ([PR 322](https://github.com/Anaconda-Platform/anaconda-project/pull/322))
* [Issue 151](https://github.com/Anaconda-Platform/anaconda-project/issues/151) anaconda-project-lock.yml does not contain pip depdendencies ([PR 317](https://github.com/Anaconda-Platform/anaconda-project/pull/317))
* [Issue 172](https://github.com/Anaconda-Platform/anaconda-project/issues/172) install pip packages from git ([PR 317](https://github.com/Anaconda-Platform/anaconda-project/pull/317))
* [Issue 181](https://github.com/Anaconda-Platform/anaconda-project/issues/181) list-packages excludes pip packages ([PR 317](https://github.com/Anaconda-Platform/anaconda-project/pull/317))
* [Issue 196](https://github.com/Anaconda-Platform/anaconda-project/issues/196) support multi-line commands ([PR 317](https://github.com/Anaconda-Platform/anaconda-project/pull/317))
* [Issue 252](https://github.com/Anaconda-Platform/anaconda-project/issues/252) Packages installed when none requested ([PR 322](https://github.com/Anaconda-Platform/anaconda-project/pull/322))
* [Issue 253](https://github.com/Anaconda-Platform/anaconda-project/issues/253) Docs rendering problem
* [Issue 329](https://github.com/Anaconda-Platform/anaconda-project/issues/329) file download progress bar

### Enhancements

* [PR 306](https://github.com/Anaconda-Platform/anaconda-project/pull/306) Build docker images with s2i
* [PR 311](https://github.com/Anaconda-Platform/anaconda-project/pull/311) Support `default` command alias with `anaconda-project prepare --command default` if no command is acutally named `default`
* [PR 313](https://github.com/Anaconda-Platform/anaconda-project/pull/313) Add `--pack-envs` to `anaconda-project archive` to add Conda-packed envs to the project archive
* [PR 317](https://github.com/Anaconda-Platform/anaconda-project/pull/317) Improve pip package support
* [PR 322](https://github.com/Anaconda-Platform/anaconda-project/pull/322) `anaconda-project init` makes an empty environment by default
* [PR 323](https://github.com/Anaconda-Platform/anaconda-project/pull/323) Changelog and maintenance

### Bug fixes

* [PR 312](https://github.com/Anaconda-Platform/anaconda-project/pull/312) Do not add `.projectignore` if `.gitignore` is found

## Version 0.9.1

### Issues Closed

* [Issue 270](https://github.com/Anaconda-Platform/anaconda-project/issues/270) read-only environments ([PR 299](https://github.com/Anaconda-Platform/anaconda-project/pull/299))


### Enhancements

* [PR 299](https://github.com/Anaconda-Platform/anaconda-project/pull/299) Support for read-only environments 
* [PR 307](https://github.com/Anaconda-Platform/anaconda-project/pull/307) Support .readonly file in environments
* [PR 309](https://github.com/Anaconda-Platform/anaconda-project/pull/309) Add option to replace read-only environment

## Version 0.9.0

### Issues Closed

* [Issue 190](https://github.com/Anaconda-Platform/anaconda-project/issues/238) anaconda-project commands in a subdrectory ([PR 215](https://github.com/Anaconda-Platform/anaconda-project/pull/215))
* [Issue 238](https://github.com/Anaconda-Platform/anaconda-project/issues/238) version file not updated for 0.8.4 ([PR 237](https://github.com/Anaconda-Platform/anaconda-project/pull/237))
* [PR 245](https://github.com/Anaconda-Platform/anaconda-project/pull/245) Fix prepare action when using global "dependencies:"
* [Issue 247](https://github.com/Anaconda-Platform/anaconda-project/issues/247) Graceful handling of read-only environments ([PR 250](https://github.com/Anaconda-Platform/anaconda-project/pull/250))
* [Issue 255](https://github.com/Anaconda-Platform/anaconda-project/issues/255) Version 0.8.4 modifies anaconda-project.yml during prepare ([PR 256](https://github.com/Anaconda-Platform/anaconda-project/pull/256))
* [Issue 285](https://github.com/Anaconda-Platform/anaconda-project/issues/285) .projectignore not created ([PR 215](https://github.com/Anaconda-Platform/anaconda-project/pull/215))

### Enhancements

* [PR 215](https://github.com/Anaconda-Platform/anaconda-project/pull/215) Run anaconda-project commands from a subdirectory
* [PR 244](https://github.com/Anaconda-Platform/anaconda-project/pull/244) Templating for commands
* [PR 257](https://github.com/Anaconda-Platform/anaconda-project/pull/257) list default command *only*
* [PR 265](https://github.com/Anaconda-Platform/anaconda-project/pull/265) 'default' is an alias for the actual default command
* [PR 286](https://github.com/Anaconda-Platform/anaconda-project/pull/286) Add command specific variables and define variable priority order
* [PR 292](https://github.com/Anaconda-Platform/anaconda-project/pull/292) Allow multiple environment path directories
* [PR 301](https://github.com/Anaconda-Platform/anaconda-project/pull/301) Allow unpacking into empty directory 
* [PR 302](https://github.com/Anaconda-Platform/anaconda-project/pull/302) Add support for .readonly file


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
