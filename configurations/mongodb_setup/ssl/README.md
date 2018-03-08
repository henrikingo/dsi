# SSL #

## Keys ##

The following SSL keys to be used, by default, when monogod is configured with SSL/TSL. To recreate
them please follow the steps at the end of this document.

`root.crt`:
- The self signed certificate authority (CA) used for signing all other certificates.

`member.pem`:
- This consists of the key and certificate for the mongod server. The certificate is signed by
  root.crt.

`client.crt`:
- The certificate signed by root.crt used by the mongo client using the mongod server with
  member.pem credentials.

`client.key`:
- The key used by mongo client, client.crt is the signed certificate for this key.

By specifying all of the private IP addresses for the AWS machines running DSI in the SAN of both
the client and member certificates. The .cnf files contain all the necessary information to make the
keys valid. Not obviously, to be valid among replica set nodes both clientAuth and serverAuth need
to be specified for extendedUsage in the member.cnf; the client.cnf needs only clientAuth specified.
This is the only difference in member.cnf and client.cnf, otherwise they are identical.

## Java Truststore and Keystore ##
These are essential for Java programs dealing with SSL connections. Please note that there is a
default TrustStore called cacerts (/usr/java/\<java_version>/jre/lib/security/cacerts for linux
boxes) which stores CA certificates. `keystore.jks` was created using [this guide](https://blogs.oracle.com/jtc/installing-trusted-certificates-into-a-java-keystore).

Learn more [here](https://docs.oracle.com/cd/E19509-01/820-3503/ggffo/index.html).

## SSL Key and Java Keystore Creation ##

To recreate these keys you will need to have a copy openssl.cnf, member.cnf, and client.cnf.

### ROOT CA ###
`openssl genrsa -out root.key 4096`

`openssl req -new -x509 -days 365000 -key root.key -out root.crt -config openssl.cnf`

When prompted to enter values, leave every field blank by pressing enter (they have already been
filled from the .cnf file).

### MEMBER CERT ###
`openssl genrsa -out member.key 4096`

`openssl req -new -key member.key -out member.csr -config member.cnf`

When prompted to enter values, leave every field blank by pressing enter (they have already been
filled from the .cnf file).

`openssl x509 -req -days 365000 -in member.csr -CA root.crt -CAkey root.key -CAcreateserial -out member.crt -extfile member.cnf -extensions v3_req`

`cat member.crt member.key > member.pem`

### CLIENT CERT ###
`openssl genrsa -out client.key 4096`

`openssl req -new -key client.key -out client.csr -config client.cnf`

When prompted to enter values, leave every field blank by pressing enter (they have already been
filled from the .cnf file).

`openssl x509 -req -days 365000 -in client.csr -CA root.crt -CAkey root.key -CAcreateserial -out client.crt -extfile client.cnf -extensions v3_req`

### KEYSTORE ###
`openssl pkcs12 -export -chain -in client.crt -inkey client.key -out keystore.p12 -name client -CAfile root.crt`

`keytool -importkeystore -destkeystore keystore.jks -srckeystore keystore.p12 -alias client`
