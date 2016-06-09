output "private_member_ip" {
  value = "${module.cluster.private_member_ip}"
}

output "public_member_ip" {
  value = "${module.cluster.public_member_ip}"
}

output "public_ip_mc" {
  value = "${module.cluster.public_ip_mc}"
}

output "total_count" {
  value = "${module.cluster.total_count}"
}

output "private_mongos_ip" {
  value = "${module.cluster.private_mongos_ip}"
}

output "public_mongos_ip" {
  value = "${module.cluster.public_mongos_ip}"
}

output "private_config_ip" {
  value = "${module.cluster.private_configserver_ip}"
}

output "public_config_ip" {
  value = "${module.cluster.public_configserver_ip}"
}
