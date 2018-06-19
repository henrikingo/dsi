HOWTO deploy etl_jira_mongo.py as a scheduled Lambda function
=============================================================

Table of contents:

 * Steps to deploy etl_jira_mongo.py as a Lambda
 * Next steps (there's a lot)
 * Links to literature

Steps to deploy
---------------

### AWS Credentials

Add this to ~/.aws/credentials:

    [Kernel_Performance_Lambda]
    aws_access_key_id = <insert here>
    aws_secret_access_key = <insert here>


### The Zappa part

You MUST be in a virtualenv:

    virtualenv venv
    source venv/bin/activate
    python ./setup.py develop

Then

    zappa deploy

Later you'll use

    zappa update

This will

    * Deploy all of the dsi repo as a Lambda, with etl_jira_mongo set as the entry point.
      (In other words, most of dsi is dead baggage for now.)
    * Automatically create an IAM role with needed permissions
    * NOT create the API Gateway stack, since we only want to run these as scheduled events.
        * To be able to trigger the lambda manually (not wait for event): `apigateway_enabled: true`
        * Alternatively, run it quicker: `expression: rate(1 minute)`
        * Note that the Test button in AWS Console won't work with Zappa (or rather, you'd have to
          know what input Zappa expects).

It will also

    * Configure a Zappa "slim handler" as the actual lambda function, which then calls
      etl_jira_mongo. For us this is unnecessary, but seems unavoidable if we want the deployment.

It will NOT

    * Clean up after itself. If you change some config, the old resources will be left behind.
      (In other words, this is not terraform.) There's `zappa undeploy` to remove everything, but
      also this is only removing the most recent configuration.
    * Do the things we'll do manually next

### Parameters

Now go to your 
[AWS Console for the Lambda function](https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions/etl-jira-mongo-dev?tab=graph).

Add the following environment variables:

* JIRA_USER
* JIRA_PASSWORD
* MONGO_URI

At this point you should be able [to see](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logStream:group=/aws/lambda/etl-jira-mongo-dev)
etl_jira_mongo executing (every 10 minutes), but it will get stuck and timeout as the MongoDB
Atlas instance isn't accesible to it. Please verify that it works so far.

### VPC

To do VPC peering with Atlas, we need a VPC. This is not automated by Zappa. As this is a one time
configuration, doing it manually is fine. But it's also complex and error prone. In particular,
when you create a VPC and add the Lambda to it, by default it will lose internet access. You will
notice this
[in the logs](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logStream:group=/aws/lambda/etl-jira-mongo-dev)
as the Lambda can no longer query Jira.

These articles explain how to do it:

* https://aws.amazon.com/premiumsupport/knowledge-center/internet-access-lambda-function/
  (The video is key. The article doesn't mention you need additional IAM permission!!!)
* https://aws.amazon.com/blogs/aws/new-vpc-endpoint-for-amazon-s3/
* https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/vpc-endpoints.html
* https://edgarroman.github.io/zappa-django-guide/aws_network_primer/

...but you'll probably get lost in the woods. So just try to get the below done. The parenthesis
are names I used and nat-..... is the AWS resource id. Each bullet point is a resource you must
create.

* VPC (lambda-vpc)
  * Subnet (lambda-public-subnet)
    * Route table (lambda-public-route)
      * 10.0.0.0/16 | local
      * 0.0.0.0/0 (igw-......)
        * Internet Gateway (lambda-igw)
    * Network ACL (default is good, don't touch)
  * Subnet (lambda-private-subnet-c)
    * Route table (lambda-private-route)
      * 10.0.0.0/16 | local
      * 0.0.0.0/0 | nat-......
        * NAT Gateway (nat-in-lambda-public)
          * Elastic IP
      * 192.168.248.0/21 | pcx-...... *This is the Atlas peer, see next section*
      * pl-...... com.amazonaws.us-east-1.s3 | vpce-...... *S3 is needed by Zappa bootstrapping*
    * Network ACL (default is good, don't touch)
  * Subnet (lambda-private-subnet-d)
    * Route table (lambda-private-route)
      * same as above
  * Security group (lambda-vpc-sg)
      * Default is good

*Note: The NAT Gateway is itself created inside lambda-public-subnet, and used as a target in lambda-private-route.*


Now add the Lambda to the VPC **private subnets**:

* Lambda (etl-jira-mongo-dev)
  * VPC (lambda-vpc)
  * Subnet (lambda-private-subnet-c)
  * Subnet (lambda-private-subnet-d)
  * Security group (lambda-vpc-sg)


At this point, you should
[check the logs](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logStream:group=/aws/lambda/etl-jira-mongo-dev).
Jira query should succeed again, while MongoDB connection will still timeout.


Atlas VPC Peering
-----------------

This worked easy: https://www.mongodb.com/blog/post/introducing-vpc-peering-for-mongodb-atlas?jmp=adref

Make sure to also enable DNS.


TODO
----

* Instead of Zappa automatically creating a role, we really need the build team to do that, and
  then provide the `role_arn` to zappa_settings.yml. I tried this, but it seems like it stopped
  working so I reverted for now. (It might be that it still works, and it was something else I
  did that broke it.)

* Once that works, we need to figure out the minimal amount of policies needed for the role.
  The Access Advisor tab should answer this question for us.

* Configure Lambda to use KMS for storing environment variables at rest. (They'll remain visible
  in the AWS console, which is ok?)
    * Mask sensitive environment variables as they are logged from etl_jira_mongo.

* In the VPC setup, I should use 2 NAT devices (and therefore 2 different private route tables) for
  high availability. Otoh, we don't really need HA for this. (So don't need 2 private subnets in
  the first place.)

* Change the Zappa stage from "dev" to "prod". (We only need one stage IMO.) Note that this will
  break links in this README.
  * Best is to `zappa undeploy` first, then change zappa_settings.yml and deploy new.

* In etl_jira_mongo refactor away the duplication between main() and zappa_handler(). Such as
  push all of it into the EtlJira class.

* Discuss how to generalize this to schedule more tasks. It seems like just adding more `events`
  in zappa_settings.yml is easy.
  * My 2 cents: Both Lambda and Zappa are much heavier than what we need. Lambda needs API gw,
    CloudWatch, IAM roles and obscure VPC setup to run a simple script. Zappa doesn't want to run
    a simple script but really would want us to run Flask or Django around it. A cron script in an
    EC2 instance is worth considering, as we won't need the scalability of the Lambda stack.
    Otoh VPC peering could be complicated for an EC2 as well, and EC2 will be more expensive.


Literature
----------

Seriously, I had to read all of these to make it work:

* https://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html
  (Zappa does this for us)
* https://github.com/Miserlou/Zappa
* https://aws.amazon.com/premiumsupport/knowledge-center/internet-access-lambda-function/
  (The video is key. The article doesn't mention you need additional IAM permission!!!)
* https://aws.amazon.com/blogs/aws/new-vpc-endpoint-for-amazon-s3/
* https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/vpc-endpoints.html
* https://www.mongodb.com/blog/post/introducing-vpc-peering-for-mongodb-atlas?jmp=adref
* https://edgarroman.github.io/zappa-django-guide/aws_network_primer/
