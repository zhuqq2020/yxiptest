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

# 匹配IPv4地址的正则表达式
ipv4_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'

# 删除旧的 ip.txt 文件
if os.path.exists('ip.txt'):
    os.remove('ip.txt')
    print("已删除旧的 ip.txt 文件")

# 用字典存储IP地址和来源，自动去重
ipv4_sources = {}  # ip: source

# 获取北京时间
def get_beijing_time():
    # 使用时区感知的UTC时间
    utc_now = datetime.now(timezone.utc)
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
def fetch_ips(urls, pattern, ip_store):
    print(f"开始从URL抓取IPv4地址...")
    total_ips_found = 0
    
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] 正在从 {url} 获取IPv4...")
        try:
            # 延长超时时间到15秒
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                ips = re.findall(pattern, resp.text)
                
                before_count = len(ip_store)
                
                # 提取来源名称（从URL中提取有意义的名称）
                source_name = extract_source_name(url)
                
                for ip in ips:
                    ip_store[ip] = source_name
                
                after_count = len(ip_store)
                new_ips = after_count - before_count
                total_ips_found += len(ips)
                print(f"  从 {url} 找到 {len(ips)} 个IPv4，其中 {new_ips} 个是新IPv4")
                print(f"  来源标识: {source_name}")
                
                # 显示找到的部分IP示例
                if ips:
                    print(f"  示例IP: {ips[:3]}")  # 显示前3个作为示例
            else:
                print(f"  请求失败，状态码: {resp.status_code}")
        except requests.RequestException as e:
            print(f"  警告: 获取IPv4失败，URL: {url}, 错误: {e}")
    
    print(f"IPv4抓取完成，总共找到 {total_ips_found} 个IPv4地址，去重后剩余 {len(ip_store)} 个唯一IPv4")

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
def fetch_ip_delays(ip_store) -> dict:
    if not ip_store:
        print(f"没有找到IPv4地址进行延迟测试")
        return {}
        
    print(f"\n开始测试 {len(ip_store)} 个IPv4的延迟...")
    ip_delays = {}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_ping_latency, ip): ip for ip in ip_store.keys()}
        
        completed_count = 0
        for future in as_completed(futures):
            ip, latency = future.result()
            ip_delays[ip] = latency
            completed_count += 1
            print(f"[{completed_count}/{len(ip_store)}] 已完成IPv4 {ip} 的延迟测试: {latency:.3f}ms")
    
    print(f"所有IPv4延迟测试完成，共测试 {len(ip_delays)} 个IPv4")
    return ip_delays

# 合并保存所有IP到一个文件
def save_all_ips_to_file(ipv4_delays, ipv4_sources, filename):
    all_ips = []
    
    # 处理IPv4地址
    if ipv4_delays:
        valid_ipv4 = {ip: latency for ip, latency in ipv4_delays.items() if latency != float('inf')}
        for ip, latency in valid_ipv4.items():
            source = ipv4_sources.get(ip, 'unknown')
            all_ips.append((ip, latency, source, "IPv4"))
    
    if not all_ips:
        print("错误: 所有IP测试均失败，未找到有效的IP地址")
        return
    
    # 按延迟升序排列
    sorted_ips = sorted(all_ips, key=lambda x: x[1])
    
    print(f"\n排序后的IP列表 (共 {len(sorted_ips)} 个):")
    
    for i, (ip, latency, source, ip_type) in enumerate(sorted_ips, 1):
        if latency == float('inf'):
            print(f"{i}. {ip} - 延迟: 未测试 - 类型: {ip_type} - 来源: {source}")
        else:
            print(f"{i}. {ip} - 平均延迟: {latency:.3f}ms - 类型: {ip_type} - 来源: {source}")
    
    # 写入文件，在备注中添加IP类型
    with open(filename, 'w') as f:
        for ip, latency, source, ip_type in sorted_ips:
            if latency == float('inf'):
                f.write(f'{ip}#{ip_type}_{current_time}_{source}优选_未测试\n')
            else:
                f.write(f'{ip}#{ip_type}_{current_time}_{source}优选_{latency:.3f}ms\n')
    
    print(f'\n已保存 {len(sorted_ips)} 个IP到 {filename}')
    print(f'格式: IP#类型_时间_来源_延迟')

# 主流程
print("=== Cloudflare IP收集工具开始运行 ===")

# 获取IPv4地址
fetch_ips(urls_ipv4, ipv4_pattern, ipv4_sources)

if not ipv4_sources:
    print("错误: 未找到任何IP地址，程序退出")
    exit(1)

# 处理IPv4地址
ipv4_delays = {}
if ipv4_sources:
    ipv4_delays = fetch_ip_delays(ipv4_sources)
else:
    print("未找到IPv4地址")

# 合并保存所有IP到一个文件
save_all_ips_to_file(ipv4_delays, ipv4_sources, 'ip.txt')

print("\n=== IP收集完成 ===")
