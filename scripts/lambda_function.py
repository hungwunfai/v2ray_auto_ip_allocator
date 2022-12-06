from typing import Any
from v2ray_auto_ip_allocator.tasks import Tasks

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Any, context: Any):
    logger.info(json.dumps(event, indent=4))
    task = Tasks(
        root_domain=event["root_domain"],
        aws_region=event["aws_region"],
        oss_endpoint=event["oss_endpoint"],
        oss_bucket=event["oss_bucket"],
        oss_subscription_key=event["oss_subscription_key"],
    )
    task.update_and_publish(event["update_list"])
