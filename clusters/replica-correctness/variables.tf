variable "count" {
    default = 3
}

variable "configcount" {
    default = 3
}

variable "mastercount" {
    default = 2
}

variable "mongourl" {
    default = "https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.0.5.tgz"
}

variable "user" {
    default = "CHANGEME"
}

variable "owner" {
    default = "CHANGEME"
}

variable "secondary_type" {
    default = "m3.2xlarge"
}

variable "configserver_type" {
    default = "m3.xlarge"
}

variable "primary_type" {
    default = "m3.2xlarge"
}

variable "instance_ips" {
    default = {
        "0" = "10.2.0.100"
        "1" = "10.2.0.101"
        "2" = "10.2.0.102"
        "3" = "10.2.0.103"
        "4" = "10.2.0.104"
        "5" = "10.2.0.105"
        "6" = "10.2.0.106"
        "7" = "10.2.0.107"
        "8" = "10.2.0.108"
        "9" = "10.2.0.109"
        "10" = "10.2.0.110"
        "11" = "10.2.0.111"
        "12" = "10.2.0.112"
        "13" = "10.2.0.113"
        "14" = "10.2.0.114"
        "15" = "10.2.0.115"
        "16" = "10.2.0.116"
        "17" = "10.2.0.117"
        "18" = "10.2.0.118"
        "19" = "10.2.0.119"
        "20" = "10.2.0.120"
        "21" = "10.2.0.121"
        "22" = "10.2.0.122"
        "23" = "10.2.0.123"
        "24" = "10.2.0.124"
        "25" = "10.2.0.125"
        "26" = "10.2.0.126"
        "27" = "10.2.0.127"
        "28" = "10.2.0.128"
        "29" = "10.2.0.129"
        "30" = "10.2.0.130"
        "31" = "10.2.0.131"
        "32" = "10.2.0.132"
        "33" = "10.2.0.133"
        "34" = "10.2.0.134"
        "35" = "10.2.0.135"
        "36" = "10.2.0.136"
        "37" = "10.2.0.137"
        "38" = "10.2.0.138"
        "39" = "10.2.0.139"
        "40" = "10.2.0.140"
        "41" = "10.2.0.141"
        "42" = "10.2.0.142"
        "43" = "10.2.0.143"
        "44" = "10.2.0.144"
        "45" = "10.2.0.145"
        "46" = "10.2.0.146"
        "47" = "10.2.0.147"
        "48" = "10.2.0.148"
        "49" = "10.2.0.149"
        "50" = "10.2.0.150"
        "51" = "10.2.0.151"
        "52" = "10.2.0.152"
        "53" = "10.2.0.153"
        "54" = "10.2.0.154"
        "55" = "10.2.0.155"
        "56" = "10.2.0.156"
        "57" = "10.2.0.157"
        "58" = "10.2.0.158"
        "59" = "10.2.0.159"
        "master0" = "10.2.0.98"
        "master1" = "10.2.0.99"
        "config0" = "10.2.0.81"
        "config1" = "10.2.0.82"
        "config2" = "10.2.0.83"
    }
}
