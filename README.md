## What slivka-bio-installer does

This project makes it easy for you to create a new installation of **slivka-bio** - a slivka based web services stack that provides access to a range of tools for bioinformatics and molecular modelling. Once you've installed the pre-requisites, you'll be able to run the slivka-bioi

## Cloning the respository

This repository uses other repositories which are included as git submodules.
By default `git clone` does not clone submodules recursively.
Use `--recurse-submodules` clone the repo with all included submodules e.g.

```
git clone --recurse-submodules https://github.com/proteinverse/slivka-bio-installer.git
```

If you have already cloned the repository without submodules then run

```
git submodule init && git submodule update
```

## Prerequisities

As a bare minimum, the installer requires python, click, ruamel.yaml and slivka.
You can install all the dependencies with conda package manager:

```
conda create -n slivka-installer -c conda-forge python=3.10 click ruamel.yaml slivka::slivka
```

If you prefer the latest beta version of slivka then install slivka from the _beta_ subdirectory

```
conda create -n slivka-installer -c conda-forge python=3.10 click ruamel.yaml slivka/label/beta::slivka
```

The installer uses _conda_ and _docker_ which need to be available for proper functiononing. 

## Installing tools

Move to the directory where you cloned the installer repository and run:

```
python install.py <PATH>
```
Where _&lt;PATH&gt;_ is the location where you want the installer to create the new Slivka application. 
The installer will display the list of tools that will be installed and prompt for the installation method for each one of them.
If the installation fails, you will be prompted to retry, skip the installation of that service, abort and stop the installer or ignore the error and proceed with the installation.

Once you've completed the installation, you'll still need to do the following:

  - Review ```<PATH>/settings.yaml```:
    - Make sure the correct port is specified for your own mongodb instance (and that mongodb is running!)
    - Make sure the server port is correctly configured - either localhost (127.0.0.1) or (0.0.0.0) if you want slivka to be accessible from other machines.
  - Configure the default service runners ```<PATH>/services/_profiles.yaml```:
    - Switch between ShellRunner (no load balancing) and SlivaQueueRunner (simple executable queue)
    - Add additional options
  - 

