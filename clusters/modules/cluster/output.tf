output "private_member_ip" {
  value = "${module.mongod_instance.private_ips}"
}

output "public_member_ip" {
  value = "${module.mongod_instance.public_ips}"
}

output "public_ip_mc" {
  value = "${module.workload_instance.public_ips}"
}

output "total_count" {
  value = "${var.mongod_instance_count}"
}