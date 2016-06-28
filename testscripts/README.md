# runtests.sh:
This script must be run from the **dsi** repository root. 

## Tests for dsi/analysis:
There are a handful of tests in **analysis/testcases** that will fail without a required API credentials file.

From within **analysis/testcases**:

- `test_update_overrides.sh`, `test_override.py`, and `test_evergreen_helpers.py` rely on a `./config.yml` file. 
  - `./config.yml` should be formatted to match `./example_update_override_config.yml`.
  - *Evergreen credentials*: found in your local `~/.evergreen.yml` file. (Instructions [here](http://evergreen.mongodb.com/settings) if you are missing this file.)
  - *Github authentication token*:   
`curl -i -u <USERNAME> -H 'X-GitHub-OTP: <2FA 6-DIGIT CODE>' -d '{"scopes": ["repo"], "note": "get full git hash"}' https://api.github.com/authorizations`
    - (You only need `-H 'X-GitHub-OTP: <2FA 6-DIGIT CODE>` if you have 2-factor authentication on.)