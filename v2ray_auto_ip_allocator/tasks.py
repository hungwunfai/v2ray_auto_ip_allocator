from typing import List
from v2ray_auto_ip_allocator.utils import AWSOperations, CloudflareOperations, OssOperations, V2raySubscriptionOperations, InstanceInfo
from time import sleep

import os
import logging


class Tasks():
    def __init__(self,
            root_domain: str,
            aws_region: str,
            oss_endpoint: str,
            oss_bucket: str,
            oss_subscription_key: str) -> None:
        self.root_domain = root_domain
        self.aws_region = aws_region
        self.oss_endpoint = oss_endpoint
        self.oss_bucket = oss_bucket
        self.oss_subscription_key = oss_subscription_key

    def update_and_publish(self, update_list: List[str]) -> None:
        logging.info("=== Start ===")

        aws = AWSOperations(region=self.aws_region)
        cf = CloudflareOperations(api_token=os.environ["CLOUDFLARE_API_TOKEN"])
        
        insts = [i for i in aws.get_v2ray_server_instance_infos()]
        new_insts: List[InstanceInfo] = []
        for inst in insts:
            new_inst = inst
            if inst.name in update_list:
                logging.info(f"Updating IP for {repr(inst)} ...")
                new_inst = aws.update_instance_with_new_ip(inst)
                logging.info(f"{repr(inst)} now has new IP {new_inst.ip}")
                cf_zone_id = cf.get_zone_id_by_name(self.root_domain)
                cf_dns_record_id = cf.get_dns_record_id_by_domain_name(cf_zone_id, f"{inst.name}.{self.root_domain}")
                cf.update_dns_record_ip(cf_zone_id, cf_dns_record_id, new_inst.ip)
                logging.info("DNS record updated")
            new_insts.append(new_inst)
        sleep(3)
        released_ips = aws.clean_up_unused_eips()
        logging.info(f"{len(released_ips)} unused IPs released: {', '.join(released_ips)}")

        oss = OssOperations(
            endpoint=self.oss_endpoint,
            bucket_name=self.oss_bucket,
            subscription_key=self.oss_subscription_key,
            access_key_id=os.environ["OSS_ACCESS_KEY_ID"],
            access_key_secret=os.environ["OSS_ACCESS_KEY_SECRET"])
        logging.info("Downloading current subscription configs ...")
        subs_current = oss.download_v2ray_subscription()
        subs_ops = V2raySubscriptionOperations(self.root_domain)
        subs_new = subs_ops.update_subscription(subs_current, new_insts)
        logging.info("Uploading new subscription configs ...")
        oss.upload_v2ray_subscription(subs_new)

        logging.info("=== Done ===")
