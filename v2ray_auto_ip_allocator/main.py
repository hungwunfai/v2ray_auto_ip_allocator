from argparse import ArgumentParser, ArgumentError
from v2ray_auto_ip_allocator.tasks import Tasks
from datetime import datetime, timezone

import logging
import sys


def main() -> int:
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    logging.Formatter.formatTime = (lambda self, record, datefmt=None: datetime.fromtimestamp(record.created, timezone.utc).astimezone().isoformat(sep="T",timespec="milliseconds"))

    arg_parser = ArgumentParser()
    arg_parser.add_argument("--root-domain", required=True, help="Root domain for SNI")
    arg_parser.add_argument("--aws-region", required=True, help="AWS region for servers")
    arg_parser.add_argument("--oss-endpoint", required=True, help="Aliyun OSS endpoint for publishing subscription")
    arg_parser.add_argument("--oss-bucket", required=True, help="Aliyun OSS bucket for publishing subscription")
    arg_parser.add_argument("--oss-subscription-key", required=True, help="Aliyun OSS object key for publishing subscription")
    arg_parser.add_argument("--update-list", required=True, nargs="+", help="Space-separated list of names for servers whose IPs are to be updated")
    try:
        args = arg_parser.parse_args()
    except ArgumentError:
        arg_parser.print_help()
        return 1
    
    task = Tasks(
        root_domain=args.root_domain,
        aws_region=args.aws_region,
        oss_endpoint=args.oss_endpoint,
        oss_bucket=args.oss_bucket,
        oss_subscription_key=args.oss_subscription_key,
    )
    task.update_and_publish(args.update_list)
    return 0

if __name__ == "__main__":
    sys.exit(main())
