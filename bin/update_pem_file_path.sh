#!/bin/bash

sed -i -- "s#../../keys/aws.pem#${1}#g" *.json
