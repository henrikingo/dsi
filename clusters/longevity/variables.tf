variable "count" {
    default = 3
}

variable "configcount" {
    default = 3
}

variable "mastercount" {
    default = 2
}

variable "mongoversion" {
    default = "3.0.1"
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
        "0" = "10.2.5.100"
        "1" = "10.2.5.101"
        "2" = "10.2.5.102"
        "3" = "10.2.5.103"
        "4" = "10.2.5.104"
        "5" = "10.2.5.105"
        "6" = "10.2.5.106"
        "7" = "10.2.5.107"
        "8" = "10.2.5.108"
        "9" = "10.2.5.109"
        "10" = "10.2.5.110"
        "11" = "10.2.5.111"
        "12" = "10.2.5.112"
        "13" = "10.2.5.113"
        "14" = "10.2.5.114"
        "15" = "10.2.5.115"
        "16" = "10.2.5.116"
        "17" = "10.2.5.117"
        "18" = "10.2.5.118"
        "19" = "10.2.5.119"
        "20" = "10.2.5.120"
        "21" = "10.2.5.121"
        "22" = "10.2.5.122"
        "23" = "10.2.5.123"
        "24" = "10.2.5.124"
        "25" = "10.2.5.125"
        "26" = "10.2.5.126"
        "27" = "10.2.5.127"
        "28" = "10.2.5.128"
        "29" = "10.2.5.129"
        "30" = "10.2.5.130"
        "31" = "10.2.5.131"
        "32" = "10.2.5.132"
        "33" = "10.2.5.133"
        "34" = "10.2.5.134"
        "35" = "10.2.5.135"
        "36" = "10.2.5.136"
        "37" = "10.2.5.137"
        "38" = "10.2.5.138"
        "39" = "10.2.5.139"
        "40" = "10.2.5.140"
        "41" = "10.2.5.141"
        "42" = "10.2.5.142"
        "43" = "10.2.5.143"
        "44" = "10.2.5.144"
        "45" = "10.2.5.145"
        "46" = "10.2.5.146"
        "47" = "10.2.5.147"
        "48" = "10.2.5.148"
        "49" = "10.2.5.149"
        "50" = "10.2.5.150"
        "51" = "10.2.5.151"
        "52" = "10.2.5.152"
        "53" = "10.2.5.153"
        "54" = "10.2.5.154"
        "55" = "10.2.5.155"
        "56" = "10.2.5.156"
        "57" = "10.2.5.157"
        "58" = "10.2.5.158"
        "59" = "10.2.5.159"
        "master0" = "10.2.5.98"
        "master1" = "10.2.5.99"
        "config0" = "10.2.5.81"
        "config1" = "10.2.5.82"
        "config2" = "10.2.5.83"
    }
}
