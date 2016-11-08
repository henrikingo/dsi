
variable "amis" {
    default = {
        "us-west-2a" = "ami-e7527ed7"
        "us-west-2b" = "ami-e7527ed7"
        "us-west-2c" = "ami-e7527ed7"
        "us-west-2d" = "ami-e7527ed7"

        "us-east-1a" = "ami-60b6c60a"   # Amazon Linux AMI 2015.09.1 (HVM), SSD Volume Type - ami-60b6c60a
    }
}

variable "private_ips" {
    default = {
        "mongod_ebs0" = "10.2.0.200"
        "mongod_ebs1" = "10.2.0.201"
        "mongod_ebs2" = "10.2.0.202"
        "mongod_ebs3" = "10.2.0.203"
        "mongod_ebs4" = "10.2.0.204"
        "mongod_ebs5" = "10.2.0.205"

        "mongod_seeded_ebs0" = "10.2.0.210"
        "mongod_seeded_ebs1" = "10.2.0.211"
        "mongod_seeded_ebs2" = "10.2.0.212"
        "mongod_seeded_ebs3" = "10.2.0.213"
        "mongod_seeded_ebs4" = "10.2.0.214"
        "mongod_seeded_ebs5" = "10.2.0.215"


        "mongod0" = "10.2.0.100"
        "mongod1" = "10.2.0.101"
        "mongod2" = "10.2.0.102"
        "mongod3" = "10.2.0.103"
        "mongod4" = "10.2.0.104"
        "mongod5" = "10.2.0.105"
        "mongod6" = "10.2.0.106"
        "mongod7" = "10.2.0.107"
        "mongod8" = "10.2.0.108"
        "mongod9" = "10.2.0.109"
        "mongod10" = "10.2.0.110"
        "mongod11" = "10.2.0.111"
        "mongod12" = "10.2.0.112"
        "mongod13" = "10.2.0.113"
        "mongod14" = "10.2.0.114"
        "mongod15" = "10.2.0.115"
        "mongod16" = "10.2.0.116"
        "mongod17" = "10.2.0.117"
        "mongod18" = "10.2.0.118"
        "mongod19" = "10.2.0.119"
        "mongod20" = "10.2.0.120"
        "mongod21" = "10.2.0.121"
        "mongod22" = "10.2.0.122"
        "mongod23" = "10.2.0.123"
        "mongod24" = "10.2.0.124"
        "mongod25" = "10.2.0.125"
        "mongod26" = "10.2.0.126"
        "mongod27" = "10.2.0.127"
        "mongod28" = "10.2.0.128"
        "mongod29" = "10.2.0.129"
        "mongod30" = "10.2.0.130"
        "mongod31" = "10.2.0.131"
        "mongod32" = "10.2.0.132"
        "mongod33" = "10.2.0.133"
        "mongod34" = "10.2.0.134"
        "mongod35" = "10.2.0.135"
        "mongod36" = "10.2.0.136"
        "mongod37" = "10.2.0.137"
        "mongod38" = "10.2.0.138"
        "mongod39" = "10.2.0.139"
        "mongod40" = "10.2.0.140"
        "mongod41" = "10.2.0.141"
        "mongod42" = "10.2.0.142"
        "mongod43" = "10.2.0.143"
        "mongod44" = "10.2.0.144"
        "mongod45" = "10.2.0.145"
        "mongod46" = "10.2.0.146"
        "mongod47" = "10.2.0.147"
        "mongod48" = "10.2.0.148"
        "mongod49" = "10.2.0.149"
        "mongod50" = "10.2.0.150"
        "mongod51" = "10.2.0.151"
        "mongod52" = "10.2.0.152"
        "mongod53" = "10.2.0.153"
        "mongod54" = "10.2.0.154"
        "mongod55" = "10.2.0.155"
        "mongod56" = "10.2.0.156"
        "mongod57" = "10.2.0.157"
        "mongod58" = "10.2.0.158"
        "mongod59" = "10.2.0.159"
        "workloadclient0" = "10.2.0.98"
        "mongos0" = "10.2.0.99"
        "configsvr0" = "10.2.0.81"
        "configsvr1" = "10.2.0.82"
        "configsvr2" = "10.2.0.83"
    }
}

variable "placement_groups" {
    default = {
        "us-west-2a.yes" = "dsi-perf-us-west-2a"
        "us-west-2b.yes" = "dsi-perf-us-west-2b"
        "us-west-2c.yes" = "dsi-perf-us-west-2c"
        "us-west-2d.yes" = "dsi-perf-us-west-2d"

        "us-east-1a.yes" = "dsi-perf-us-east-1a"

        "us-west-2a.no" = ""
        "us-west-2b.no" = ""
        "us-west-2c.no" = ""
        "us-west-2d.no" = ""

        "us-east-1a.no" = ""
   }
}


