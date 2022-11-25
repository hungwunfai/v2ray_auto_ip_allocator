from typing import Iterable, List, Optional
from base64 import b64decode, b64encode

import boto3
import CloudFlare
import oss2
import re


class InstanceInfo():
    def __init__(self, name: str, id: str, ip: str) -> None:
        self.name = name
        self.id = id
        self.ip = ip
    def __repr__(self) -> str:
        return f"{self.name}({self.id})"


class AWSOperations():
    def __init__(self, region: str, access_key_id: Optional[str] =  None, secret_access_key: Optional[str] = None) -> None:
        self.region = region
        self.ec2 = boto3.resource("ec2",
            region_name=self.region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key)
        self.ec2_client = boto3.client("ec2",
            region_name=self.region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key)
        self.TAG_GROUP_NAME = "v2ray-server"

    def get_v2ray_server_instance_infos(self) -> Iterable[InstanceInfo]:
        instances = self.ec2.instances.filter(
            Filters=[
                {
                    "Name": "tag:Group",
                    "Values": [
                        self.TAG_GROUP_NAME
                    ]
                }
            ]
        )
        eipAddresses = self.ec2.vpc_addresses.all()
        for instance in instances:
            for tag in instance.tags:
                if tag.get("Key") == "Name":
                    inst_name = tag.get("Value")
                    ip = None
                    for addr in eipAddresses:
                        if addr.instance_id == instance.id:
                            ip = addr.public_ip
                    if inst_name and ip:
                        yield InstanceInfo(inst_name, instance.id, ip)

    def get_instance_by_instance_id(self, instance_id: str):
        target_instance = None
        for inst in self.ec2.instances.filter(Filters=[{"Name": "instance-id", "Values": [instance_id]}]):
            target_instance = inst
            break
        if target_instance:
            return target_instance
        else:
            raise Exception("Failed to find specified instance")

    def get_eip_address_by_ip(self, ip: str):
        eip = None
        for addr in self.ec2.vpc_addresses.filter(Filters=[{"Name": "public-ip", "Values": [ip]}]):
            eip = addr
            break
        if eip:
            return eip
        else:
            raise Exception("Failed to find specified elastic IP")
    
    def update_instance_with_new_ip(self, instance: InstanceInfo) -> InstanceInfo:
        new_ip = self.ec2_client.allocate_address(Domain="vpc",
            TagSpecifications=[{
                "ResourceType": "elastic-ip",
                "Tags": [{
                    "Key": "Group",
                    "Value": self.TAG_GROUP_NAME
                }]
            }])["PublicIp"]
        eip = self.get_eip_address_by_ip(new_ip)
        target_instance = self.get_instance_by_instance_id(instance.id)
        eip.associate(InstanceId=target_instance.id, AllowReassociation=True)
        return InstanceInfo(instance.name, instance.id, new_ip)

    def get_all_allocated_eips(self):
        return self.ec2.vpc_addresses.filter(Filters=[{
                "Name": "tag:Group",
                "Values": [self.TAG_GROUP_NAME]
            }])
    
    def clean_up_unused_eips(self) -> List[str]:
        released_ips: List[str] = []
        for eip in self.get_all_allocated_eips():
            if eip.instance_id:
                continue
            released_ips.append(eip.public_ip)
            eip.release()
        return released_ips


class CloudflareOperations():
    def __init__(self, api_token: str) -> None:
        self.cf = CloudFlare.CloudFlare(token=api_token)

    def get_zone_id_by_name(self, zone_name: str) -> str:
        for zone in self.cf.zones.get(params={"name": zone_name}):
            return zone["id"]
        raise Exception("Cannot find specified zone")

    def get_dns_record_id_by_domain_name(self, zone_id: str, domain_name: str) -> str:
        dns_records = self.cf.zones.dns_records.get(zone_id, params={"name": domain_name})
        for record in dns_records:
            return record["id"]
        raise Exception("Cannot find specified dns record")
    
    def update_dns_record_ip(self, zone_id: str, record_id: str, ip: str) -> None:
        record = self.cf.zones.dns_records.get(zone_id, record_id)
        self.cf.zones.dns_records.put(zone_id, record_id, data={
            "type": record["type"],
            "name": record["name"],
            "content": ip,
            "ttl": record["ttl"],
            "proxied": record["proxied"]
        })
        

class OssOperations():
    def __init__(self, endpoint: str, bucket_name: str, subscription_key: str, access_key_id: str, access_key_secret: str) -> None:
        auth = oss2.AuthV2(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
        self.subscription_key = subscription_key

    def download_v2ray_subscription(self) -> bytes:
        content = self.bucket.get_object(self.subscription_key).read()
        if isinstance(content, bytes):
            return content
        raise Exception("Unexpected content type")

    def upload_v2ray_subscription(self, content: bytes) -> None:
        self.bucket.put_object(self.subscription_key, content)


class V2raySubscriptionOperations():
    def __init__(self, root_domain: str) -> None:
        self.root_domain = root_domain

    def parse_subscription_content(self, subscription_content: bytes) -> List[str]:
        return b64decode(subscription_content, validate=True).decode(encoding="UTF-8").splitlines()
    
    def encode_as_subscription_content(self, server_configs: Iterable[str]) -> bytes:
        return b64encode("\n".join(server_configs).encode(encoding="UTF-8"))

    def update_subscription(self, existing_subscription: bytes, server_infos: Iterable[InstanceInfo]) -> bytes:
        configs = self.parse_subscription_content(existing_subscription)
        new_configs: List[str] = []
        for config in configs:
            new_config = config
            # vless://{guid}@{host:ip-address|domain-name}:{port}?{param-list:type,sni,...}#{entry-name}
            match = re.match(f"vless:\\/\\/[0-9a-f-]+@([0-9\\.]+):[0-9]+\\?.*&sni=([a-z0-9-]+)\\.", config)
            if match:
                for server_info in server_infos:
                    if match.group(2) == server_info.name:
                        new_config = config.replace(match.group(1), server_info.ip)
            new_configs.append(new_config)
        return self.encode_as_subscription_content(new_configs)
