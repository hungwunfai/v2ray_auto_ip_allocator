from v2ray_auto_ip_allocator.utils import AWSOperations, CloudflareOperations, OssOperations, V2raySubscriptionOperations, InstanceInfo

import pytest
import os


@pytest.mark.skip(reason="This test actually triggers AWS and Cloudflare operation")
def test_ip_update() -> None:
    aws = AWSOperations(region="us-west-2")
    cf = CloudflareOperations(api_token=os.environ["CLOUDFLARE_API_TOKEN"])
    insts = [i for i in aws.get_v2ray_server_instance_infos()]
    assert(len(insts) == 2)

    server_name = "mk"
    root_domain = "irisium.info"
    for inst in insts:
        if inst.name == server_name:
            new_inst = aws.update_instance_with_new_ip(inst)
            assert(new_inst.ip)
            assert(new_inst.ip != inst.ip)
            cf_zone_id = cf.get_zone_id_by_name(root_domain)
            cf_dns_record_id = cf.get_dns_record_id_by_domain_name(cf_zone_id, f"{inst.name}.{root_domain}")
            cf.update_dns_record_ip(cf_zone_id, cf_dns_record_id, new_inst.ip)
    aws.clean_up_unused_eips()


@pytest.mark.skip(reason="This test actually triggers Aliyun OSS operation")
def test_oss_download_upload() -> None:
    oss = OssOperations(
        endpoint="https://oss-cn-zhangjiakou.aliyuncs.com",
        bucket_name="irisium-gen",
        subscription_key="v2r/subs/v2r-subs-test",
        access_key_id=os.environ["OSS_ACCESS_KEY_ID"],
        access_key_secret=os.environ["OSS_ACCESS_KEY_SECRET"])
    subs_content = oss.download_v2ray_subscription()
    oss.upload_v2ray_subscription(subs_content)

def test_subscription_content_update() -> None:
    subs = V2raySubscriptionOperations("example.xyz")
    original_configs = [
        r"vless://11111111-ffff-4444-bbbb-777777777777@44.236.29.187:443?encryption=none&security=tls&sni=altria.example.xyz&type=ws&host=altria.example.xyz&path=%2Ftugcws#KINGK-altria.example.xyz_VLESS_WS",
        r"vless://44444444-aaaa-4444-9999-eeeeeeeeeeee@44.231.161.36:443?encryption=none&flow=xtls-rprx-direct&security=xtls&sni=mk.example.xyz&type=tcp&headerType=none#KINGK-mk.example.xyz_VLESS_XTLS%2FTLS-direct_TCP",
        r"vless://11111111-ffff-4444-bbbb-777777777777@altria.example.xyz:443?encryption=none&security=tls&sni=altria.example.xyz&type=ws&host=altria.example.xyz&path=%2Ftugcws#BLINGK-altria.example.xyz_VLESS_WS",
        r"vless://44444444-aaaa-4444-9999-eeeeeeeeeeee@mk.example.xyz:443?encryption=none&flow=xtls-rprx-direct&security=xtls&sni=mk.example.xyz&type=tcp&headerType=none#BLINGK-mk.example.xyz_VLESS_XTLS%2FTLS-direct_TCP",
    ]
    expected_result_configs = [
        r"vless://11111111-ffff-4444-bbbb-777777777777@44.236.29.187:443?encryption=none&security=tls&sni=altria.example.xyz&type=ws&host=altria.example.xyz&path=%2Ftugcws#KINGK-altria.example.xyz_VLESS_WS",
        r"vless://44444444-aaaa-4444-9999-eeeeeeeeeeee@44.230.160.30:443?encryption=none&flow=xtls-rprx-direct&security=xtls&sni=mk.example.xyz&type=tcp&headerType=none#KINGK-mk.example.xyz_VLESS_XTLS%2FTLS-direct_TCP",
        r"vless://11111111-ffff-4444-bbbb-777777777777@altria.example.xyz:443?encryption=none&security=tls&sni=altria.example.xyz&type=ws&host=altria.example.xyz&path=%2Ftugcws#BLINGK-altria.example.xyz_VLESS_WS",
        r"vless://44444444-aaaa-4444-9999-eeeeeeeeeeee@mk.example.xyz:443?encryption=none&flow=xtls-rprx-direct&security=xtls&sni=mk.example.xyz&type=tcp&headerType=none#BLINGK-mk.example.xyz_VLESS_XTLS%2FTLS-direct_TCP",
    ]
    server_infos = [
        InstanceInfo("mk", "i-12345678ab", "44.230.160.30"),
        InstanceInfo("altria", "i-12345678ab", "44.236.29.187"),
    ]

    original_subs = subs.encode_as_subscription_content(original_configs)
    result_subs = subs.update_subscription(original_subs, server_infos)
    result_configs = subs.parse_subscription_content(result_subs)

    assert(result_configs == expected_result_configs)
    