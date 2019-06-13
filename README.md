# DSI: distributed system test infrastructure
Please consult the full documentation available at http://bit.ly/2ufjQ0R for more information about
installing required binaries and dependencies. To set up your environment for locally running 
performance tests, please see configurations/bootstrap/bootstrap.example.yml and follow the inline documentation.

## Environment

This project uses python 2.7, and you may want to set up a virtual environment to support this, e.g. using [virtualenv](https://virtualenv.pypa.io/en/latest/)
```
// Create the virtual environment
virtualenv -p python2.7 venv
// activate it
source venv/bin/activate
// deactivate when done developing
deactivate
```


## Installing DSI

You can install a version for development:
```
cd $DSI_REPO_DIR # the git checkout location
pip install -e . # install a development version
```

You can install a github (master or BRANCHNAME) with :

```
pip install --verbose -e . git+ssh://git@github.com/10gen/dsi.git --upgrade
pip install --verbose -e . git+ssh://git@github.com/10gen/dsi.git@BRANCHNAME --upgrade
```
## Development Dependencies

As a developer, extra requirements are needed, run the following command:
```
pip install -r requirements-dev.txt
```

## Testing
The repo's tests are all packaged into `/testscripts/runtests.sh`, which must be run from the repo
root and it requires:
 
  - a `/config.yml` file (see `/example_config.yml`).
    - *Evergreen credentials*: found in your local `~/.evergreen.yml` file. 
(Instructions [here](http://evergreen.mongodb.com/settings) if you are missing this file.)
    - *Github authentication token*:
`curl -i -u <USERNAME> -H 'X-GitHub-OTP: <2FA 6-DIGIT CODE>' -d '{"scopes": ["repo"], "note": 
"get full git hash"}' https://api.github.com/authorizations`
    - (You only need `-H 'X-GitHub-OTP: <2FA 6-DIGIT CODE>` if you have 2-factor authentication on.) 
  - Python 2.7 *ONLY*.
  - The correct packages. It is recommended that you use some python package manager.
    - `$ pip install -r ./requirements-dev.txt             
`

### Testing Examples

Run all the unit tests:

    $ testscripts/run-nosetest.sh

Run all the tests including system tests:

    $ DSI_SYSTEM_TEST=true testscripts/run-nosetest.sh

Run only the system tests:

    $ DSI_SYSTEM_TEST=true testscripts/run-nosetest.sh -a system-test

Run a specific test:

    $ testscripts/run-nosetest.sh  signal_processing/outliers/tests/test_config.py 

Run all tests in a module:

    $ testscripts/run-nosetest.sh signal_processing/outliers/tests/test_*.py 

Note: the `.py`, using `signal_processing/outliers/tests/test_*` may run all the tests twice if
there are py and pyc files. 
