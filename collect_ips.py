import requests
import re
import os
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 目标URL列表
urls_ipv4 = [
    'https://ip.164746.xyz', 
    'https://api.uouin.com/cloudflare.html', 
    'https://www.wetest.vip/page/cloudflare/address_v4.html',
    'https://www.wetest.vip/page/cloudfront/address_v4.html', 
    'https://www.wetest.vip/page/edgeone/address_v4.html', 
    'https://stock.hostmonit.com/CloudFlareYes', 
    'https://stock.hostmonit.com/CloudFlareYesV6', 
    'https://vps789.com/public/sum/cfIpApi' 
]

urls_ipv6 = [
    'https://api.uouin.com/cloudflare.html', 
    'https://www.wetest.vip/page/cloudflare/address_v6.html', 
    'https://www.wetest.vip/page/cloudfront/address_v6.html', 
    'https://stock.hostmonit.com/CloudFlareYes', 
    'https://stock.hostmonit.com/CloudFlareYesV6'
]

# 匹配IPv4地址的正则表达式
ipv4_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'

# 改进的IPv6正则表达式 - 匹配完整的IPv6地址
ipv6_pattern = r'[a-fA-F0-9:]+(?:::)?[a-fA-F0-9:]*(?::[a-fA-F0-9:]+)*'

# 更精确的IPv6正则表达式
ipv6_pattern_precise = r'(?:(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:))'

# 删除旧的 ip.txt 文件
if os.path.exists('ip.txt'):
    os.remove('ip.txt')
    print("已删除旧的 ip.txt 文件")

# 用字典存储IP地址和来源，自动去重
ipv4_sources = {}  # ip: source
ipv6_sources = {}  # ip: source

# 获取北京时间
def get_beijing_time():
    # UTC时间+8小时得到北京时间
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
    return beijing_time.strftime("%Y%m%d%H%M")

current_time = get_beijing_time()

# 获取IP延迟（3次ping，每次间隔1秒，计算平均延迟）
def get_ping_latency(ip: str, num_pings: int = 3, interval: int = 1) -> tuple[str, float]:
    print(f"正在测试IP {ip} 的延迟...")
    latencies = []
    
    for i in range(num_pings):
        try:
            start = time.time()
            # 使用HTTP请求模拟ping，设置较短超时时间
            # 对IPv6地址使用方括号
            if ':' in ip:
                target_url = f"http://[{ip}]"
            else:
                target_url = f"http://{ip}"
            
            requests.get(target_url, timeout=5)
            latency = (time.time() - start) * 1000  # 毫秒
            latencies.append(round(latency, 3))
            print(f"  IP {ip} 第 {i+1} 次ping延迟: {latency:.3f}ms")
            if i < num_pings - 1:  # 最后一次不需要sleep
                time.sleep(interval)
        except requests.RequestException as e:
            print(f"  IP {ip} 第 {i+1} 次ping失败: {e}")
            latencies.append(float('inf'))  # 请求失败返回无限延迟
    
    # 计算平均延迟
    avg_latency = sum(latencies) / len(latencies) if latencies else float('inf')
    print(f"IP {ip} 平均延迟: {avg_latency:.3f}ms")
    return ip, avg_latency

# 从URLs抓取IP地址，避免无效请求并提高异常处理
def fetch_ips(urls, pattern, ip_store, ip_type="IPv4"):
    print(f"开始从URL抓取{ip_type}地址...")
    total_ips_found = 0
    
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] 正在从 {url} 获取{ip_type}...")
        try:
            # 延长超时时间到15秒
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                # 对于IPv6，使用更宽松的匹配模式
                if ip_type == "IPv6":
                    # 先尝试精确匹配
                    ips_precise = re.findall(ipv6_pattern_precise, resp.text)
                    # 再尝试宽松匹配，然后过滤
                    ips_loose = re.findall(pattern, resp.text)
                    # 合并并去重
                    all_ips = list(set(ips_precise + ips_loose))
                    # 过滤掉明显不完整的IPv6地址
                    ips = [ip for ip in all_ips if len(ip) > 5 and ':' in ip]
                else:
                    ips = re.findall(pattern, resp.text)
                
                before_count = len(ip_store)
                
                # 提取来源名称（从URL中提取有意义的名称）
                source_name = extract_source_name(url)
                
                for ip in ips:
                    # 对于IPv6，进一步验证格式
                    if ip_type == "IPv6":
                        # 确保是有效的IPv6格式
                        if re.match(r'^[a-fA-F0-9:]+$', ip) and ip.count(':') >= 2:
                            ip_store[ip] = source_name
                    else:
                        ip_store[ip] = source_name
                
                after_count = len(ip_store)
                new_ips = after_count - before_count
                total_ips_found += len(ips)
                print(f"  从 {url} 找到 {len(ips)} 个{ip_type}，其中 {new_ips} 个是新{ip_type}")
                print(f"  来源标识: {source_name}")
                
                # 显示找到的部分IP示例
                if ips:
                    print(f"  示例IP: {ips[:3]}")  # 显示前3个作为示例
            else:
                print(f"  请求失败，状态码: {resp.status_code}")
        except requests.RequestException as e:
            print(f"  警告: 获取{ip_type}失败，URL: {url}, 错误: {e}")
    
    print(f"{ip_type}抓取完成，总共找到 {total_ips_found} 个{ip_type}地址，去重后剩余 {len(ip_store)} 个唯一{ip_type}")

# 从URL中提取有意义的来源名称
def extract_source_name(url: str) -> str:
    """从URL中提取简短的来源名称"""
    if '164746' in url:
        return 'ip164746'
    elif '090227' in url:
        return 'cf090227'
    elif 'hostmonit' in url:
        return 'hostmonit'
    elif 'wetest' in url:
        return 'wetest'
    elif 'uouin' in url:
        return 'uouin'
    elif 'vps789' in url:
        return 'vps789'
    else:
        # 如果都不匹配，使用域名的主要部分
        domain = re.search(r'https?://([^/]+)', url)
        if domain:
            main_domain = domain.group(1).split('.')[-2]  # 获取主域名部分
            return main_domain
        return 'unknown'

# 并发获取延迟
def fetch_ip_delays(ip_store, ip_type="IPv4") -> dict:
    if not ip_store:
        print(f"没有找到{ip_type}地址进行延迟测试")
        return {}
        
    print(f"\n开始测试 {len(ip_store)} 个{ip_type}的延迟...")
    ip_delays = {}
    
    # 如果是IPv6，跳过ping测试，直接返回无限延迟
    if ip_type == "IPv6":
        print("跳过IPv6的ping测速...")
        for ip in ip_store.keys():
            ip_delays[ip] = float('inf')
        return ip_delays
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_ping_latency, ip): ip for ip in ip_store.keys()}
        
        completed_count = 0
        for future in as_completed(futures):
            ip, latency = future.result()
            ip_delays[ip] = latency
            completed_count += 1
            print(f"[{completed_count}/{len(ip_store)}] 已完成{ip_type} {ip} 的延迟测试: {latency:.3f}ms")
    
    print(f"所有{ip_type}延迟测试完成，共测试 {len(ip_delays)} 个{ip_type}")
    return ip_delays

# 合并保存所有IP到一个文件
def save_all_ips_to_file(ipv4_delays, ipv6_delays, ipv4_sources, ipv6_sources, filename):
    all_ips = []
    
    # 处理IPv4地址
    if ipv4_delays:
        valid_ipv4 = {ip: latency for ip, latency in ipv4_delays.items() if latency != float('inf')}
        for ip, latency in valid_ipv4.items():
            source = ipv4_sources.get(ip, 'unknown')
            all_ips.append((ip, latency, source, "IPv4"))
    
    # 处理IPv6地址 - 即使延迟为inf也保存，但放在最后
    if ipv6_delays:
        for ip, latency in ipv6_delays.items():
            source = ipv6_sources.get(ip, 'unknown')
            all_ips.append((ip, latency, source, "IPv6"))
    
    if not all_ips:
        print("错误: 所有IP测试均失败，未找到有效的IP地址")
        return
    
    # 先按类型排序（IPv4在前），然后按延迟升序排列
    sorted_ips = sorted(all_ips, key=lambda x: (x[3] != "IPv4", x[1]))
    
    print(f"\n排序后的IP列表 (共 {len(sorted_ips)} 个):")
    ipv4_count = 0
    ipv6_count = 0
    
    for i, (ip, latency, source, ip_type) in enumerate(sorted_ips, 1):
        if latency == float('inf'):
            print(f"{i}. {ip} - 延迟: 未测试 - 类型: {ip_type} - 来源: {source}")
        else:
            print(f"{i}. {ip} - 平均延迟: {latency:.3f}ms - 类型: {ip_type} - 来源: {source}")
        
        if ip_type == "IPv4":
            ipv4_count += 1
        else:
            ipv6_count += 1
    
    # 写入文件，在备注中添加IP类型
    with open(filename, 'w') as f:
        for ip, latency, source, ip_type in sorted_ips:
            if latency == float('inf'):
                f.write(f'{ip}#{ip_type}_{current_time}_{source}优选_\n')
            else:
                f.write(f'{ip}#{ip_type}_{current_time}_{source}优选\n')
    
    print(f'\n已保存 {len(sorted_ips)} 个IP到 {filename}')
    print(f'其中 IPv4: {ipv4_count} 个, IPv6: {ipv6_count} 个')
    print(f'格式: IP#来源_类型_时间_延迟')

# 主流程
print("=== Cloudflare IP收集工具开始运行 ===")

# 获取IPv4地址
fetch_ips(urls_ipv4, ipv4_pattern, ipv4_sources, "IPv4")

# 获取IPv6地址 - 使用改进的正则表达式
fetch_ips(urls_ipv6, ipv6_pattern, ipv6_sources, "IPv6")

if not ipv4_sources and not ipv6_sources:
    print("错误: 未找到任何IP地址，程序退出")
    exit(1)

# 处理IPv4地址
ipv4_delays = {}
if ipv4_sources:
    ipv4_delays = fetch_ip_delays(ipv4_sources, "IPv4")
else:
    print("未找到IPv4地址")

# 处理IPv6地址
ipv6_delays = {}
if ipv6_sources:
    ipv6_delays = fetch_ip_delays(ipv6_sources, "IPv6")
else:
    print("未找到IPv6地址")

# 合并保存所有IP到一个文件
save_all_ips_to_file(ipv4_delays, ipv6_delays, ipv4_sources, ipv6_sources, 'ip.txt')

print("\n=== IP收集完成 ===")
