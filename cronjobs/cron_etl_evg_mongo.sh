if [ ! -f evergreen.yml ]; then
cat > evergreen.yml <<EOF
evergreen: &EVERGREEN
  api_server_host: https://evergreen.mongodb.com/api
  ui_server_host: https://evergreen.mongodb.com
  api_key: $EVERGREEN_TOKEN
  user: xgen-evg-user
<<: *EVERGREEN
github:
  token: $GITHUB_TOKEN
EOF
fi
etl-evg-mongo --mongo-uri $MONGO_URI --evergreen-config evergreen.yml
