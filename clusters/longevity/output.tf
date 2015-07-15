output "address" {
  value = "Instances: ${join(", ", aws_instance.shardmember.*.id)}"
}

output "private_member_ip" {
  value = "${join(" ", aws_instance.shardmember.*.private_ip)}"
}

output "public_member_ip" {
  value = "${join(" ", aws_instance.shardmember.*.public_ip)}"
}

output "private_mongos_ip" {
  value = "${aws_instance.master.1.private_ip}"
}

output "public_mongos_ip" {
  value = "${aws_instance.master.1.public_ip}"
}

output "public_ip_mc" {
  value = "${aws_instance.master.0.public_ip}"
}

output "total_count" {
  value = "${var.count}"
}

output "private_config_ip" {
  value = "${join(" ", aws_instance.configserver.*.private_ip)}"
}

output "public_config_ip" {
  value = "${join(" ", aws_instance.configserver.*.public_ip)}"
}



#output "ip" {
#  value = "\nPublic IP : ${join(", ", aws_instance.shardmember.*.public_ip)}\nPrivate IP : ${join(", ", aws_instance.shardmember.*.private_ip)}"
#}
