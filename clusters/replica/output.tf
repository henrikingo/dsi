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
