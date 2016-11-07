output "address" {
  value = "Instances: ${join(", ", aws_instance.ebs_member.*.id)}"
}

output "private_ips" {
  value = "${join(" ", aws_instance.ebs_member.*.private_ip)}"
}

output "public_ips" {
  value = "${join(" ", aws_instance.ebs_member.*.public_ip)}"
}
