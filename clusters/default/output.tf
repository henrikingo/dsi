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

output "private_mongod_ebs_ip" {
  value = "${module.cluster.private_mongod_ebs_ip}"
}

output "public_mongod_ebs_ip" {
  value = "${module.cluster.public_mongod_ebs_ip}"
}

output "private_mongod_seeded_ebs_ip" {
  value = "${module.cluster.private_mongod_seeded_ebs_ip}"
}

output "public_mongod_seeded_ebs_ip" {
  value = "${module.cluster.public_mongod_seeded_ebs_ip}"
}

output "public_all_host_ip" {
  value = "${module.cluster.public_mongod_seeded_ebs_ip} ${module.cluster.public_mongod_ebs_ip} ${module.cluster.public_member_ip}"
}

output "private_all_host_ip" {
  value = "${module.cluster.private_mongod_seeded_ebs_ip} ${module.cluster.private_mongod_ebs_ip} ${module.cluster.private_member_ip}"
}
