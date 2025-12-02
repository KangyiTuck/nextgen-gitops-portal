#!/usr/local/python/bin/python
# -*- coding: UTF-8 -*-
"""
存储设备数据采集脚本
功能：从存储设备采集控制器、硬盘域、存储池、LUN、主机等信息，同步至应用系统
"""
import sys
import json
import time
import requests
import logging
from typing import List, Dict, Optional, Any

# 兼容Python2/3（如需仅支持Python3可删除）
try:
    reload(sys)
    sys.setdefaultencoding("utf-8")
except NameError:
    pass

# 忽略无关警告
import warnings
warnings.filterwarnings("ignore")

# ------------------------------ 日志配置（单例，全局复用）------------------------------
def setup_logger() -> logging.Logger:
    """配置日志系统，返回logger实例"""
    logger = logging.getLogger(__name__)
    if logger.handlers:  # 避免重复添加处理器
        return logger
    
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(module)s:%(lineno)d] %(message)s',
        '%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = setup_logger()

# ------------------------------ 常量定义（集中管理）------------------------------
class Constants:
    """常量类，集中存储固定配置"""
    # API相关（ORG、HOST为占位符）
    API_ORG = "XXXX"  # 占位符
    API_HOST = "app-resource.example.com"  # 示例域名
    API_PAGE_SIZE = 1000
    # 存储设备端口
    STORAGE_PORT = "XXXX"  # 占位符
    # 状态映射字典
    HEALTH_STATUS = {"0": "未知", "1": "正常", "2": "故障", "3": "即将故障", "5": "降级", "9": "不一致"}
    RUNNING_STATUS = {
        "0": "未知", "1": "正常", "2": "运行", "3": "未运行", "12": "正在上电", "14": "预拷贝",
        "16": "重构", "27": "在线", "28": "离线", "32": "正在均衡", "47": "正在下电",
        "51": "正在升级", "53": "初始化中"
    }
    PRODUCT_MODE = {
        "61": "XX 6800 V3", "62": "XX 6900 V3", "63": "XX 5600 V3", "64": "XX 5800 V3",
        "68": "XX 5500 V3", "70": "XX 5300 v3", "825": "XX 5300 V6"
    }  # XX占位符
    OPERATION_SYSTEM = {"0": "Linux", "4": "AIX", "7": "Vmware ESX"}
    RAID_LEVEL = {u"1": "RAID10", u"2": "RAID5", "3": "RAID0", "4": "RAID1", "5": "RAID6", "6": "RAID50", "7": "RAID3"}
    DISK_TYPE = {
        "0": "FC", "1": "SAS", "2": "SATA", "3": "SSD", "4": "NL-SAS", "5": "SLC SSD", "6": "MLC SSD",
        "7": "FC SED", "8": "SAS SED", "9": "SATA SED", "10": "SSD SED", "11": "NL-SAS SED",
        "12": "SLC SSD SED", "13": "MLC SSD SED", "14": "NVMe SSD", "16": "NVMe SSD SED"
    }
    HOT_STRATEGY = {"0": "无效", "1": "低", "2": "高", "3": "无"}
    APP_TYPE = {'0': 'other', '1': 'oracle', '2': 'exchange', '3': 'sqlserver', '4': 'vmware', '5': 'hyper-V'}
    USAGE_TYPE = {"0": "传统LUN", "1": "eDevLun", "2": "VVOL LUN", "3": "PE LUN", "1": "LUN", "2": "文件系统"}
    TIER_DISK_TYPE = {
        "Tier0": {"3": "SSD", "10": "SSD SED", "14": "NVMe SSD", "16": "NVMe SSD SED"},
        "Tier1": {"1": "SAS", "8": "SAS SED"},
        "Tier2": {"2": "SATA", "4": "NL-SAS", "11": "NL-SAS SED"}
    }

# ------------------------------ API请求类（职责单一，可复用）------------------------------
class AppApiClient:
    """应用系统API客户端"""
    def __init__(self, api_ip: str):
        self.api_ip = api_ip
        self.org = Constants.API_ORG
        self.page_size = Constants.API_PAGE_SIZE

    def _get_headers(self) -> Dict[str, str]:
        """获取HTTP请求头（私有方法，内部复用）"""
        return {
            'host': Constants.API_HOST,
            'content-type': 'application/json',
            'user': 'system_user',  # 通用占位符
            'org': self.org
        }

    def _build_url(self, api_path: str, instance_id: Optional[str] = None) -> str:
        """构建API URL（私有方法，内部复用）"""
        base_url = f'http://{self.api_ip}{api_path}'
        return f'{base_url}{instance_id}' if instance_id else base_url

    def request(self, method: str, api_path: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """通用API请求方法（统一错误处理）"""
        headers = self._get_headers()
        url = self._build_url(api_path)
        
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=params,
                timeout=30  # 添加超时控制
            )
            response.raise_for_status()  # 触发HTTP错误（4xx/5xx）
            
            result = response.json()
            if int(result.get('code', -1)) != 0:
                logger.error(f"API请求失败（业务码非0）: {url} -> {result}")
                return None
            return result
        
        except requests.exceptions.Timeout:
            logger.error(f"API请求超时: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求异常: {url} -> {str(e)}")
            return None
        except json.JSONDecodeError:
            logger.error(f"API响应格式错误（非JSON）: {url} -> {response.text}")
            return None

    def search_instances(self, object_id: str, params: Optional[Dict] = None) -> List[Dict]:
        """搜索实例（分页查询，自动拼接结果）"""
        params = params or {}
        params.update({'page_size': self.page_size, 'page': 1})
        api_path = f'/object/{object_id}/instance/_search'
        
        all_results = []
        while True:
            result = self.request('POST', api_path, params)
            if not result or 'data' not in result or 'list' not in result['data']:
                break
            
            data_list = result['data']['list']
            if not data_list:
                break
            
            all_results.extend(data_list)
            
            # 分页判断：如果当前页满了，继续下一页
            if len(data_list) < self.page_size:
                break
            params['page'] += 1
        
        logger.info(f"搜索实例 {object_id} 共获取 {len(all_results)} 条数据")
        return all_results

    def import_instances(self, object_id: str, params: Dict) -> Optional[Dict]:
        """导入实例"""
        api_path = f'/object/{object_id}/instance/_import'
        return self.request('POST', api_path, params)

    def update_instance(self, object_id: str, instance_id: str, params: Dict) -> Optional[Dict]:
        """更新实例"""
        api_path = f'/object/{object_id}/instance/{instance_id}'
        return self.request('PUT', api_path, params)

    def delete_instance(self, object_id: str, instance_id: str) -> Optional[Dict]:
        """删除实例"""
        api_path = f'/object/{object_id}/instance/{instance_id}'
        return self.request('DELETE', api_path)

    def clear_stale_data(self, existing_instances: List[Dict], valid_names: List[str]) -> None:
        """清理过期数据（删除不在有效列表中的实例）"""
        for instance in existing_instances:
            instance_name = instance.get('name')
            instance_id = instance.get('instanceId')
            object_id = instance.get('_object_id')
            
            if not all([instance_name, instance_id, object_id]):
                logger.warning(f"实例数据不完整，跳过清理: {instance}")
                continue
            
            if instance_name not in valid_names:
                logger.info(f"删除过期实例: {object_id} -> {instance_name}")
                self.delete_instance(object_id, instance_id)

class StorageApiClient:
    """存储设备API客户端"""
    def __init__(self):
        self.headers = {"Content-Type": "application/json"}
        self.cookies = None
        self.device_id = None

    def login(self, base_url: str, username: str, password: str) -> bool:
        """登录存储设备，获取会话信息"""
        login_url = f'{base_url}/deviceManager/rest/xxx/sessions'  # 占位符
        data = {"username": username, "password": password, "scope": "0"}
        
        try:
            response = requests.post(
                url=login_url,
                data=json.dumps(data),
                headers=self.headers,
                verify=False,
                timeout=15
            )
            response.raise_for_status()
            
            result = response.json()
            data = result.get('data', {})
            self.cookies = response.cookies
            self.device_id = data.get('deviceid')
            ibase_token = data.get('iBaseToken')
            
            if not all([self.device_id, ibase_token]):
                logger.error("登录失败：未获取到deviceid或iBaseToken")
                return False
            
            self.headers['iBaseToken'] = ibase_token
            logger.info("存储设备登录成功")
            return True
        
        except Exception as e:
            logger.error(f"存储设备登录失败: {str(e)}")
            return False

    def get_data(self, base_url: str, api_path: str) -> Optional[List[Dict]]:
        """获取存储设备数据"""
        full_url = f'{base_url}/deviceManager/rest/{self.device_id}/{api_path}'
        try:
            response = requests.get(
                url=full_url,
                cookies=self.cookies,
                headers=self.headers,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get('data', []) if isinstance(result, dict) else []
        
        except Exception as e:
            logger.error(f"获取存储数据失败: {full_url} -> {str(e)}")
            return None

# ------------------------------ 数据处理工具函数（纯函数，无副作用）------------------------------
def format_capacity(sectors: Any, sector_size: Any, unit: str = 'TB') -> float:
    """格式化容量（扇区数 * 扇区大小 -> 目标单位）"""
    try:
        sectors = int(sectors)
        sector_size = int(sector_size)
        total_bytes = sectors * sector_size
        
        # 转换为目标单位
        unit_map = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
        if unit not in unit_map:
            raise ValueError(f"不支持的单位: {unit}")
        
        return round(total_bytes / unit_map[unit], 2)
    except (ValueError, TypeError) as e:
        logger.warning(f"容量格式化失败: sectors={sectors}, sector_size={sector_size} -> {str(e)}")
        return 0.0

def build_storage_urls(base_url: str, device_id: str) -> Dict[str, str]:
    """构建存储设备所有API URL"""
    return {
        "system": f'{base_url}/deviceManager/rest/{device_id}/system/',
        "controller": f'{base_url}/deviceManager/rest/{device_id}/controller',
        "diskpool": f'{base_url}/deviceManager/rest/{device_id}/diskpool',
        "storagepool": f'{base_url}/deviceManager/rest/{device_id}/storagepool',
        "disk": f'{base_url}/deviceManager/rest/{device_id}/disk',
        "lun": f'{base_url}/deviceManager/rest/{device_id}/lun',
        "host": f'{base_url}/deviceManager/rest/{device_id}/host',
        "hostgroup": f'{base_url}/deviceManager/rest/{device_id}/hostgroup',
        "associate_host": f'{base_url}/deviceManager/rest/{device_id}/host/associate?TYPE=21&ASSOCIATEOBJTYPE=14&ASSOCIATEOBJID=',
        "associate_lungroup": f'{base_url}/deviceManager/rest/{device_id}/lun/associate?TYPE=11&ASSOCIATEOBJTYPE=256&ASSOCIATEOBJID=',
        "fc_initiator": f'{base_url}/deviceManager/rest/{device_id}/fc_initiator?PARENTID=',
        "lungroup": f'{base_url}/deviceManager/rest/{device_id}/LUNGroup?filter=GROUPTYPE::0&range=[0-100]',
        "mappingview": f'{base_url}/deviceManager/rest/{device_id}/mappingview',
        "associate_hostgroup": f'{base_url}/deviceManager/rest/{device_id}/host/associate?TYPE=21&ASSOCIATEOBJTYPE=14&ASSOCIATEOBJID=',
        "associate_lun_group": f'{base_url}/deviceManager/rest/{device_id}/lun/associate?TYPE=11&ASSOCIATEOBJTYPE=245&ASSOCIATEOBJID='
    }

# ------------------------------ 核心业务逻辑（按功能模块化）------------------------------
class StorageDataCollector:
    """存储数据采集器（统筹采集、处理、同步流程）"""
    def __init__(self, app_api: AppApiClient, storage_api: StorageApiClient, username: str, password: str):
        self.app_api = app_api
        self.storage_api = storage_api
        self.username = username
        self.password = password
        self.current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 有效数据名称缓存（用于清理过期数据）
        self.valid_names = {
            'controller': [], 'diskzone': [], 'pool': [], 'disk': [], 'lun': [], 'host': [], 'hostgroup': []
        }

    def collect_disk_array(self, storage_urls: Dict[str, str], disk_array_info: Dict[str, Any]) -> Dict[str, Any]:
        """采集磁盘阵列基本信息"""
        logger.info("开始采集磁盘阵列信息")
        system_data = self.storage_api.get_data(storage_urls["system"], '')
        if not system_data:
            logger.error("获取磁盘阵列系统信息失败")
            return {}
        
        system_data = system_data[0] if isinstance(system_data, list) else system_data
        sector_size = system_data.get('SECTORSIZE', 512)
        
        # 构建磁盘阵列结果
        return {
            "name": system_data.get("NAME", "unknown_array"),  # 通用名称
            "OSVersion": system_data.get("PRODUCTVERSION", "unknown_version"),
            "MgmtIP": disk_array_info.get("MgmtIP", "192.168.X.X"),  # 网段占位符
            "SN": f'SN-{system_data.get("ID", "XXXXXX")}',  # 占位符
            "CacheSize": system_data.get("CACHEWRITEQUOTA", 0),
            "Model": Constants.PRODUCT_MODE.get(system_data.get("PRODUCTMODE", ""), "未知型号"),
            "Allocated": f"{format_capacity(system_data.get('STORAGEPOOLUSEDCAPACITY', 0), sector_size)}T",
            "Total": f"{format_capacity(system_data.get('TOTALCAPACITY', 0), sector_size)}T",
            "UsedCapacity": f"{format_capacity(system_data.get('USEDCAPACITY', 0), sector_size)}T",
            "openReservedCapacity": f"{format_capacity(system_data.get('userFreeCapacity', 0), sector_size)}T",
            "wwnInfo": f'WWN-{system_data.get("wwn", "XXXXXXXXXXXXXXXX")}',  # 占位符
            "updateTime": self.current_time
        }

    def collect_hosts(self, storage_urls: Dict[str, str], disk_array_name: str) -> List[Dict[str, Any]]:
        """采集主机信息"""
        logger.info("开始采集主机信息")
        host_datas = self.storage_api.get_data(storage_urls["host"], '')
        if not host_datas:
            return []
        
        host_results = []
        for host_data in host_datas:
            host_name = host_data.get("NAME", "host-xxx")  # 占位符
            full_name = f"{disk_array_name}_{host_name}"
            self.valid_names['host'].append(full_name)
            
            # 获取WWPN信息
            host_id = host_data.get("ID", "")
            wwn_datas = self.storage_api.get_data(storage_urls["fc_initiator"] + host_id, '') or []
            wwn_list = [{"wwn": f'WWN-{item.get("ID", "XXXXXXXXXXXXXXXX")}', "parentName": item.get("PARENTNAME", "unknown_parent")} for item in wwn_datas]  # WWN
            
            host_results.append({
                "name": full_name,
                "hostname": host_name,
                "ip": host_data.get("IP", "192.168.X.X"),  # 网段占位符
                "location": host_data.get("LOCATION", "unknown_location"),  # 位置信息占位符
                "model": host_data.get("MODEL", "unknown_model"),
                "description": host_data.get("DESCRIPTION", "default_description"),
                "networkname": host_data.get("NETWORKNAME", "net-xxx"),
                "isadd2hostgroup": host_data.get("ISADD2HOSTGROUP", 0),
                "operationsystem": Constants.OPERATION_SYSTEM.get(host_data.get("OPERATIONSYSTEM", ""), "未知系统"),
                "initiatornun": host_data.get("INITIATORNUM", 0),
                "HostWwn": wwn_list,
                "cTime": self.current_time
            })
        
        # 导入到应用系统
        if host_results:
            self.app_api.import_instances("DISK_ARRAY_HOST", {'keys': ['name'], 'datas': host_results})
        return host_results

    def collect_host_groups(self, storage_urls: Dict[str, str], disk_array_name: str) -> List[Dict[str, Any]]:
        """采集主机组信息"""
        logger.info("开始采集主机组信息")
        hostgroup_datas = self.storage_api.get_data(storage_urls["hostgroup"], '')
        if not hostgroup_datas:
            return []
        
        hostgroup_results = []
        for hostgroup_data in hostgroup_datas:
            group_name = hostgroup_data.get("NAME", "hostgroup-xxx")  # 主机组名占位符
            group_id = hostgroup_data.get("ID", "")
            full_name = f"{disk_array_name}_{group_name}_{group_id}"
            self.valid_names['hostgroup'].append(full_name)
            
            hostgroup_results.append({
                "name": full_name,
                "groupName": group_name,
                "groupId": group_id,
                "type": hostgroup_data.get("TYPE", ""),
                "description": hostgroup_data.get("DESCRIPTION", "default_description"),
                "isadd2mapingview": hostgroup_data.get("ISADD2MAPPINGVIEW", 0),
                "cTime": self.current_time
            })
        
        # 导入到应用系统
        if hostgroup_results:
            self.app_api.import_instances("DISK_ARRAY_HOSTGROUP", {'keys': ['name'], 'datas': hostgroup_results})
        return hostgroup_results

    def collect_lun_groups(self, storage_urls: Dict[str, str], disk_array_name: str) -> List[Dict[str, Any]]:
        """采集LUN组信息"""
        logger.info("开始采集LUN组信息")
        lungroup_datas = self.storage_api.get_data(storage_urls["lungroup"], '')
        if not lungroup_datas:
            return []
        
        lungroup_results = []
        for lungroup_data in lungroup_datas:
            group_name = lungroup_data.get("NAME", "lungroup-xxx")  # LUN组名占位符
            full_name = f"{disk_array_name}_{group_name}"
            
            lungroup_results.append({
                "name": full_name,
                "groupName": group_name,
                "id": lungroup_data.get("ID", ""),
                "discription": lungroup_data.get("DESCRIPTION", "default_description"),
                "app_type": Constants.APP_TYPE.get(lungroup_data.get("APPTYPE", "0"), "other"),
                "capcity": lungroup_data.get("CAPCITY", 0),
                "cTime": self.current_time
            })
        
        # 导入到应用系统
        if lungroup_results:
            self.app_api.import_instances("DISK_ARRAY_LUNGROUP", {'keys': ['name'], 'datas': lungroup_results})
        return lungroup_results

    def collect_mapping_views(self, storage_urls: Dict[str, str], disk_array_name: str) -> List[Dict[str, Any]]:
        """采集映射视图信息"""
        logger.info("开始采集映射视图信息")
        mapping_datas = self.storage_api.get_data(storage_urls["mappingview"], '')
        if not mapping_datas:
            return []
        
        mapping_results = []
        for mapping_data in mapping_datas:
            mapping_results.append({
                "name": f"{disk_array_name}_{mapping_data.get('NAME', 'mapping-xxx')}",  # 映射视图名占位符
                "viewName": f"{disk_array_name}_{mapping_data.get('NAME', 'mapping-xxx')}",
                "id": mapping_data.get("ID", ""),
                "updateTime": self.current_time,
                "description": mapping_data.get("DESCRIPTION", "default_description")
            })
        
        # 导入到应用系统
        if mapping_results:
            self.app_api.import_instances("DISK_ARRAY_MAPPVIEW", {'keys': ['name'], 'datas': mapping_results})
        return mapping_results

    def collect_controllers(self, storage_urls: Dict[str, str], disk_array_name: str, disk_array_instance_id: str) -> List[Dict[str, Any]]:
        """采集控制器信息"""
        logger.info("开始采集控制器信息")
        controller_datas = self.storage_api.get_data(storage_urls["controller"], '')
        if not controller_datas:
            return []
        
        controller_results = []
        for controller_data in controller_datas:
            controller_id = controller_data.get("ID", "ctrl-xxx")  # 控制器ID占位符
            full_name = f"{disk_array_name}_{controller_id}"
            self.valid_names['controller'].append(full_name)
            
            controller_results.append({
                "name": full_name,
                "SOFTWARE_VERSION": controller_data.get("SOFTVER", "unknown_ver"),
                "HEALTH_STATUS": Constants.HEALTH_STATUS.get(controller_data.get("HEALTHSTATUS", "0"), "未知"),
                "RUNNING_STATE": Constants.RUNNING_STATUS.get(controller_data.get("RUNNINGSTATUS", "0"), "未知"),
                "LOCATION": controller_data.get("LOCATION", "unknown_location"),
                "ROLE": {"0": "普通成员", "1": "集群主", "2": "集群备"}.get(controller_data.get("ROLE", "0"), "未知"),
                "BMCVER": controller_data.get("BMCVER", "unknown_ver"),
                "CACHE": controller_data.get("MEMORYSIZE", 0),
                "BIOSVER": controller_data.get("BIOSVER", "unknown_ver"),
                "LOGICVER": controller_data.get("LOGICVER", "unknown_ver"),
                "CPUINFO": controller_data.get("CPUINFO", "unknown_cpu"),
                "DISK_ARRAY": [disk_array_instance_id],
                "cTime": self.current_time
            })
        
        # 导入到应用系统
        if controller_results:
            self.app_api.import_instances("DISK_ARRAY_CONTROLLER", {'keys': ['name'], 'datas': controller_results})
        return controller_results

    def collect_storage_pools(self, storage_urls: Dict[str, str], disk_array_name: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """采集存储池信息"""
        logger.info("开始采集存储池信息")
        storagepool_datas = self.storage_api.get_data(storage_urls["storagepool"], '')
        if not storagepool_datas:
            return [], {}
        
        storagepool_results = []
        disk_domain_pool_count = {}  # 硬盘域关联存储池数量
        
        for storagepool in storagepool_datas:
            pool_name = storagepool.get("NAME", "pool-xxx")  # 存储池名占位符
            full_name = f"{disk_array_name}_{pool_name}"
            self.valid_names['pool'].append(full_name)
            
            # 构建Tier相关信息
            tier_raid = []
            for tier in ['TIER0RAIDLV', 'TIER1RAIDLV', 'TIER2RAIDLV']:
                raid = Constants.RAID_LEVEL.get(storagepool.get(tier, ""), "")
                if raid:
                    tier_raid.append(raid)
            
            tier_disk_type = []
            for tier, disk_map in Constants.TIER_DISK_TYPE.items():
                disk_type_key = storagepool.get(f"{tier}DISKTYPE", "")
                if disk_type_key and disk_type_key in disk_map:
                    tier_disk_type.append(disk_map[disk_type_key])
            
            # 容量计算（扇区大小固定512字节）
            sector_size = 512
            total_cap = format_capacity(storagepool.get('USERTOTALCAPACITY', 0), sector_size)
            used_cap = format_capacity(storagepool.get('USERCONSUMEDCAPACITY', 0), sector_size)
            free_cap = format_capacity(storagepool.get('USERFREECAPACITY', 0), sector_size)
            
            # 硬盘域名称
            parent_name = f"{disk_array_name}_{storagepool.get('PARENTNAME', 'diskzone-xxx')}"
            disk_domain_pool_count[parent_name] = disk_domain_pool_count.get(parent_name, 0) + 1
            
            storagepool_results.append({
                "name": full_name,
                "PoolName": pool_name,
                "PoolId": storagepool.get("ID", ""),
                "AvailableCapacity": total_cap,
                "AvailableCapacityUsed": used_cap,
                "FreeCapacity": free_cap,
                "Medium": ''.join(tier_disk_type),
                "RaidType": ''.join(tier_raid),
                "updateTime": self.current_time,
                "DISK_ZONE": []  # 后续关联硬盘域实例ID
            })
        
        # 导入到应用系统
        if storagepool_results:
            self.app_api.import_instances("CENTRALIZED_STORAGE_POOL", {'keys': ['name'], 'datas': storagepool_results})
        return storagepool_results, disk_domain_pool_count

    def collect_luns(self, storage_urls: Dict[str, str], disk_array_name: str) -> List[Dict[str, Any]]:
        """采集LUN信息"""
        logger.info("开始采集LUN信息")
        lun_datas = self.storage_api.get_data(storage_urls["lun"], '')
        if not lun_datas:
            return []
        
        lun_results = []
        for lun in lun_datas:
            lun_name = lun.get("NAME", "lun-xxx")  # LUN名占位符
            full_name = f"{disk_array_name}_{lun_name}"
            self.valid_names['lun'].append(full_name)
            
            lun_results.append({
                "name": full_name,
                "LUN_ID": lun.get("ID", ""),
                "WWN": f'WWN-{lun.get("WWN", "XXXXXXXXXXXXXXXX")}',  # WWN添加前缀占位
                "ALLOCCAPACITY": lun.get("ALLOCCAPACITY", 0),
                "METACAPACITY": lun.get("METACAPACITY", 0),
                "DESC": lun.get("DESCRIPTION", "default_description"),
                "HEALTH_STATUS": Constants.HEALTH_STATUS.get(lun.get("HEALTHSTATUS", "1"), "正常"),
                "RUNNING_STATE": Constants.RUNNING_STATUS.get(lun.get("RUNNINGSTATUS", "27"), "在线"),
                "CAPACITY": format_capacity(lun.get("CAPACITY", 0), 512, 'GB'),
                "IOPRIORITY": {"1": "低", "2": "中", "3": "高"}.get(lun.get("IOPRIORITY", "2"), "中"),
                "ISADD2LUNGROUP": lun.get("ISADD2LUNGROUP", 0),
                "USAGETYPE": Constants.USAGE_TYPE.get(lun.get("USAGETYPE", "0"), "传统LUN"),
                "OWNINGCONTROLLER": f"{disk_array_name}_{lun.get('OWNINGCONTROLLER', 'ctrl-xxx')}",
                "PARENTNAME": f"{disk_array_name}_{lun.get('PARENTNAME', 'pool-xxx')}",
                "cTime": self.current_time
            })
        
        # 导入到应用系统
        if lun_results:
            self.app_api.import_instances("LUN", {'keys': ['name'], 'datas': lun_results})
        return lun_results

    def collect_disk_zones(self, storage_urls: Dict[str, str], disk_array_name: str, pool_count: Dict[str, int], disk_array_instance_id: str) -> List[Dict[str, Any]]:
        """采集硬盘域信息"""
        logger.info("开始采集硬盘域信息")
        diskpool_datas = self.storage_api.get_data(storage_urls["diskpool"], '')
        if not diskpool_datas:
            return []
        
        diskzone_results = []
        for diskpool in diskpool_datas:
            zone_name = diskpool.get("NAME", "diskzone-xxx")  # 硬盘域名占位符
            full_name = f"{disk_array_name}_{zone_name}"
            self.valid_names['diskzone'].append(full_name)
            
            # 硬盘数量统计
            disk_count = 0
            disk_num_info = []
            for disk_type, disk_key in [("SAS", "SASDISKNUM"), ("SSD", "SSDDISKNUM"), ("NL-SAS", "NLSASDISKNUM")]:
                num = diskpool.get(disk_key, 0)
                if num:
                    disk_count += int(num)
                    disk_num_info.append({"name": f"{disk_type}成员盘个数", "value": num})
            
            # 热备策略
            hot_strat_info = []
            for disk_type, strat_key in [("SAS", "SASHOTSPARESTRATEGY"), ("SSD", "SSDHOTSPARESTRATEGY"), ("NL-SAS", "NLSASHOTSPARESTRATEGY")]:
                strat = diskpool.get(strat_key, "")
                if strat:
                    hot_strat_info.append({
                        "name": f"{disk_type}热备策略",
                        "value": Constants.HOT_STRATEGY.get(strat, strat)
                    })
            
            # 容量计算
            sector_size = 512
            total_cap = format_capacity(diskpool.get('TOTALCAPACITY', 0), sector_size)
            spare_cap = format_capacity(diskpool.get('SPARECAPACITY', 0), sector_size)
            used_spare_cap = format_capacity(diskpool.get('USEDSPARECAPACITY', 0), sector_size)
            free_cap = format_capacity(diskpool.get('FREECAPACITY', 0), sector_size)
            
            diskzone_results.append({
                "name": full_name,
                "DomainName": zone_name,
                "TotalCapacity": total_cap,
                "SpareCapacity": spare_cap,
                "SpareCapacityUsed": used_spare_cap,
                "FreeCapacity": free_cap,
                "updateTime": self.current_time,
                "DiskNum": disk_num_info,
                "DiskCount": disk_count,
                "HotStrat": hot_strat_info,
                "StoragePool": pool_count.get(full_name, 0),
                "DISK_ARRAY": [disk_array_instance_id]
            })
        
        # 导入到应用系统
        if diskzone_results:
            self.app_api.import_instances("DISK_ZONE", {'keys': ['name'], 'datas': diskzone_results})
        return diskzone_results

    def collect_disks(self, storage_urls: Dict[str, str], disk_array_name: str) -> List[Dict[str, Any]]:
        """采集硬盘信息"""
        logger.info("开始采集硬盘信息")
        disk_datas = self.storage_api.get_data(storage_urls["disk"], '')
        if not disk_datas:
            return []
        
        disk_results = []
        for disk in disk_datas:
            disk_id = disk.get("ID", "disk-xxx")  # 硬盘ID占位符
            full_name = f"{disk_array_name}_{disk_id}"
            self.valid_names['disk'].append(full_name)
            
            disk_results.append({
                "name": full_name,
                "SECTOR_SIZE": str(disk.get('SECTORS', 0)),
                "SECTOR_COUNT": disk.get('SECTORSIZE', 512),
                "HEALTH_STATUS": Constants.HEALTH_STATUS.get(disk.get("HEALTHSTATUS", "0"), "未知"),
                "RUNNING_STATE": Constants.RUNNING_STATUS.get(disk.get("RUNNINGSTATUS", "0"), "未知"),
                "TYPE": Constants.DISK_TYPE.get(disk.get("DISKTYPE", "0"), "未知"),
                "SPEED_RPM": disk.get("SPEEDRPM", "unknown_rpm"),
                "MODEL": disk.get("MODEL", "unknown_model"),
                "SERIALNUMBER": f'SN-{disk.get("SERIALNUMBER", "XXXXXXXXX")}',  # 序列号添加前缀占位
                "FIRMWAREVER": disk.get("FIRMWAREVER", "unknown_ver"),
                "MANUFACTURER": disk.get("MANUFACTURER", "unknown_manufacturer"),
                "BAR_CODE": f'BAR-{disk.get("barcode", "XXXXXXXXX")}',  # 条码添加前缀占位
                "LOCATION": disk.get("LOCATION", "unknown_location"),
                "POOLNAME": f"{disk_array_name}_{disk.get('POOLNAME', 'pool-xxx')}",
                "disk_diskzone": f"{disk_array_name}_{disk.get('POOLNAME', 'diskzone-xxx')}",
                "cTime": self.current_time
            })
        
        # 导入到应用系统
        if disk_results:
            self.app_api.import_instances("DISK", {'keys': ['name'], 'datas': disk_results})
        return disk_results

    def sync_relations(self, storage_urls: Dict[str, str], disk_array_name: str) -> None:
        """同步各类关联关系"""
        logger.info("开始同步关联关系")
        # 1. 主机与主机组关系
        self._sync_host_hostgroup_relation(storage_urls, disk_array_name)
        # 2. 主机与存储关系
        self._sync_host_diskarray_relation(disk_array_name)
        # 3. 硬盘与硬盘域关系
        self._sync_disk_diskzone_relation(disk_array_name)
        # 4. 控制器与LUN关系
        self._sync_controller_lun_relation(disk_array_name)
        # 5. 存储池与LUN关系
        self._sync_pool_lun_relation(disk_array_name)
        # 6. LUN组与LUN关系
        self._sync_lungroup_lun_relation(storage_urls, disk_array_name)
        # 7. 映射视图与主机组/LUN组关系
        self._sync_mappingview_relations(storage_urls, disk_array_name)

    def _sync_host_hostgroup_relation(self, storage_urls: Dict[str, str], disk_array_name: str) -> None:
        """同步主机与主机组关系"""
        hostgroup_datas = self.storage_api.get_data(storage_urls["hostgroup"], '')
        if not hostgroup_datas:
            return
        
        # 获取所有主机实例
        host_instances = self.app_api.search_instances("DISK_ARRAY_HOST", {'fields': {"name": True}})
        host_name_id_map = {inst.get('name'): inst.get('instanceId') for inst in host_instances if inst.get('name')}
        
        for hostgroup in hostgroup_datas:
            group_id = hostgroup.get("ID", "")
            # 获取主机组关联的主机
            associate_hosts = self.storage_api.get_data(storage_urls["associate_host"] + group_id, '') or []
            if not associate_hosts:
                continue
            
            # 匹配主机实例ID
            host_instance_ids = []
            for host in associate_hosts:
                host_name = f"{disk_array_name}_{host.get('NAME', 'host-xxx')}"
                if host_name in host_name_id_map:
                    host_instance_ids.append(host_name_id_map[host_name])
            
            # 更新主机组关联关系
            group_name = f"{disk_array_name}_{hostgroup.get('NAME', 'hostgroup-xxx')}_{group_id}"
            self.app_api.import_instances("DISK_ARRAY_HOSTGROUP", {
                'keys': ['name'],
                'datas': [{"name": group_name, "_HOSTGROUP_HOST": host_instance_ids, "hostNum": len(host_instance_ids)}]
            })

    def _sync_host_diskarray_relation(self, disk_array_name: str) -> None:
        """同步主机与存储关系"""
        # 获取存储实例ID
        diskarray_instances = self.app_api.search_instances("DISK_ARRAY", {'query': {"name": {'$eq': disk_array_name}}})
        diskarray_ids = [inst.get('instanceId') for inst in diskarray_instances if inst.get('instanceId')]
        if not diskarray_ids:
            return
        
        # 获取主机实例ID
        host_instances = self.app_api.search_instances("DISK_ARRAY_HOST", {'query': {"name": {'$like': f"{disk_array_name}_%"}}})
        host_ids = [inst.get('instanceId') for inst in host_instances if inst.get('instanceId')]
        if not host_ids:
            return
        
        # 同步关系
        self.app_api.request(
            'POST',
            f'/object/DISK_ARRAY/relation/_ARRAY_HOST/append',
            params={"instance_ids": diskarray_ids, "related_instance_ids": host_ids}
        )

    def _sync_disk_diskzone_relation(self, disk_array_name: str) -> None:
        """同步硬盘与硬盘域关系"""
        diskzone_instances = self.app_api.search_instances("DISK_ZONE", {'query': {"name": {'$like': f"{disk_array_name}_%"}}})
        for zone in diskzone_instances:
            zone_name = zone.get('name', '')
            zone_id = zone.get('instanceId', '')
            if not zone_name or not zone_id:
                continue
            
            # 获取该硬盘域下的硬盘
            disk_instances = self.app_api.search_instances("DISK", {'query': {"disk_diskzone": {'$eq': zone_name}}})
            disk_ids = [inst.get('instanceId') for inst in disk_instances if inst.get('instanceId')]
            if not disk_ids:
                continue
            
            # 更新硬盘域关联关系
            self.app_api.import_instances("DISK_ZONE", {
                'keys': ['name'],
                'datas': [{"name": zone_name, "DISK": disk_ids}]
            })

    def _sync_controller_lun_relation(self, disk_array_name: str) -> None:
        """同步控制器与LUN关系"""
        controller_instances = self.app_api.search_instances("DISK_ARRAY_CONTROLLER", {'query': {"name": {'$like': f"{disk_array_name}_%"}}})
        for controller in controller_instances:
            controller_name = controller.get('name', '')
            controller_id = controller.get('instanceId', '')
            if not controller_name or not controller_id:
                continue
            
            # 获取该控制器下的LUN
            lun_instances = self.app_api.search_instances("LUN", {'query': {"OWNINGCONTROLLER": {'$eq': controller_name}}})
            lun_ids = [inst.get('instanceId') for inst in lun_instances if inst.get('instanceId')]
            if not lun_ids:
                continue
            
            # 更新控制器关联关系
            self.app_api.import_instances("DISK_ARRAY_CONTROLLER", {
                'keys': ['name'],
                'datas': [{"name": controller_name, "LUN": lun_ids}]
            })

    def _sync_pool_lun_relation(self, disk_array_name: str) -> None:
        """同步存储池与LUN关系"""
        pool_instances = self.app_api.search_instances("CENTRALIZED_STORAGE_POOL", {'query': {"name": {'$like': f"{disk_array_name}_%"}}})
        for pool in pool_instances:
            pool_name = pool.get('name', '')
            pool_id = pool.get('instanceId', '')
            if not pool_name or not pool_id:
                continue
            
            # 获取该存储池下的LUN
            lun_instances = self.app_api.search_instances("LUN", {'query': {"PARENTNAME": {'$eq': pool_name}}})
            lun_ids = [inst.get('instanceId') for inst in lun_instances if inst.get('instanceId')]
            if not lun_ids:
                continue
            
            # 更新存储池关联关系
            self.app_api.import_instances("CENTRALIZED_STORAGE_POOL", {
                'keys': ['name'],
                'datas': [{"name": pool_name, "LUN": lun_ids, "LunNum": len(lun_ids)}]
            })

    def _sync_lungroup_lun_relation(self, storage_urls: Dict[str, str], disk_array_name: str) -> None:
        """同步LUN组与LUN关系"""
        lungroup_datas = self.storage_api.get_data(storage_urls["lungroup"], '')
        if not lungroup_datas:
            return
        
        # 获取所有LUN实例
        lun_instances = self.app_api.search_instances("LUN", {'fields': {"name": True}})
        lun_name_id_map = {inst.get('name'): inst.get('instanceId') for inst in lun_instances if inst.get('name')}
        
        for lungroup in lungroup_datas:
            group_id = lungroup.get("ID", "")
            # 获取LUN组关联的LUN
            associate_luns = self.storage_api.get_data(storage_urls["associate_lungroup"] + group_id, '') or []
            if not associate_luns:
                continue
            
            # 匹配LUN实例ID
            lun_instance_ids = []
            for lun in associate_luns:
                lun_name = f"{disk_array_name}_{lun.get('NAME', 'lun-xxx')}"
                if lun_name in lun_name_id_map:
                    lun_instance_ids.append(lun_name_id_map[lun_name])
            
            # 更新LUN组关联关系
            group_name = f"{disk_array_name}_{lungroup.get('NAME', 'lungroup-xxx')}"
            self.app_api.import_instances("DISK_ARRAY_LUNGROUP", {
                'keys': ['name'],
                'datas': [{"name": group_name, "LUNGROUP_LUN": lun_instance_ids, "LunNum": len(lun_instance_ids)}]
            })

    def _sync_mappingview_relations(self, storage_urls: Dict[str, str], disk_array_name: str) -> None:
        """同步映射视图与主机组/LLUN组关系"""
        mapping_views = self.storage_api.get_data(storage_urls["mappingview"], '')
        if not mapping_views:
            return
        
        # 获取主机组和LUN组实例
        hostgroup_instances = self.app_api.search_instances("DISK_ARRAY_HOSTGROUP", {})
        hostgroup_name_id_map = {inst.get('name'): inst.get('instanceId') for inst in hostgroup_instances if inst.get('name')}
        
        lungroup_instances = self.app_api.search_instances("DISK_ARRAY_LUNGROUP", {})
        lungroup_name_id_map = {inst.get('name'): inst.get('instanceId') for inst in lungroup_instances if inst.get('name')}
        
        for view in mapping_views:
            view_id = str(view.get("ID", ""))
            view_name = f"{disk_array_name}_{view.get('NAME', 'mapping-xxx')}"
            
            # 同步主机组关系
            adjusted_id = str(int(view_id) - 1) if int(view_id) < 4 else str(int(view_id) + 1) if int(view_id) >=14 else view_id
            hostgroups = self.storage_api.get_data(storage_urls["associate_hostgroup"] + adjusted_id, '') or []
            hostgroup_ids = []
            for hg in hostgroups:
                hg_name = f"{disk_array_name}_{hg.get('NAME', 'hostgroup-xxx')}_"
                for instance_name, instance_id in hostgroup_name_id_map.items():
                    if hg_name.upper() in instance_name.upper():
                        hostgroup_ids.append(instance_id)
            
            # 同步LUN组关系
            lungroup_ids = []
            for lg_name, lg_id in lungroup_name_id_map.items():
                if view_name == lg_name:
                    lungroup_ids.append(lg_id)
            
            # 更新映射视图关联关系
            self.app_api.import_instances("DISK_ARRAY_MAPPVIEW", {
                'keys': ['name'],
                'datas': [{"name": view_name, "_mapp_hostGroup": hostgroup_ids, "_mapp_lunGroup": lungroup_ids}]
            })

    def run(self, disk_array_list: List[Dict[str, Any]]) -> None:
        """执行完整采集流程"""
        for disk_array in disk_array_list:
            mgmt_ip = disk_array.get("MgmtIP", "192.168.X.X")  # 管理IP占位符
            instance_id = disk_array.get("instanceId")
            if not mgmt_ip or not instance_id:
                logger.warning("磁盘阵列信息不完整（缺少管理IP或实例ID），跳过采集")
                continue
            
            logger.info(f"\n{'='*50} 开始采集 {mgmt_ip} 数据 {'='*50}")
            base_url = f'https://{mgmt_ip}:{Constants.STORAGE_PORT}'
            
            # 1. 登录存储设备
            if not self.storage_api.login(base_url, self.username, self.password):
                logger.error(f"{mgmt_ip} 登录失败，跳过该设备")
                continue
            
            # 2. 构建存储API URL
            storage_urls = build_storage_urls(base_url, self.storage_api.device_id)
            
            # 3. 采集各类数据
            disk_array_name = disk_array.get("name", f"array-{mgmt_ip}")
            disk_array_info = self.collect_disk_array(storage_urls, disk_array)
            
            hosts = self.collect_hosts(storage_urls, disk_array_name)
            host_groups = self.collect_host_groups(storage_urls, disk_array_name)
            lun_groups = self.collect_lun_groups(storage_urls, disk_array_name)
            mapping_views = self.collect_mapping_views(storage_urls, disk_array_name)
            controllers = self.collect_controllers(storage_urls, disk_array_name, instance_id)
            storage_pools, pool_count = self.collect_storage_pools(storage_urls, disk_array_name)
            luns = self.collect_luns(storage_urls, disk_array_name)
            disk_zones = self.collect_disk_zones(storage_urls, disk_array_name, pool_count, instance_id)
            disks = self.collect_disks(storage_urls, disk_array_name)
            
            # 4. 更新磁盘阵列统计信息
            disk_array_info.update({
                "HostGroup": len(hosts),
                "LunGroup": len(luns),
                "MapView": len(mapping_views),
                "StorePool": len(storage_pools),
                "Domain": len(disk_zones),
                "DiskQuantity": len(disks)
            })
            self.app_api.update_instance("DISK_ARRAY", instance_id, disk_array_info)
            
            # 5. 同步关联关系
            self.sync_relations(storage_urls, disk_array_name)
            
            logger.info(f"{'='*50} {mgmt_ip} 数据采集完成 {'='*50}\n")

# ------------------------------ 入口函数（简洁调度，无业务逻辑）------------------------------
def main(username: str, password: str, app_host: str, target_ip: Optional[str] = None) -> None:
    """
    脚本入口函数（参数通过外部传入）
    :param username: 存储设备用户名
    :param password: 存储设备密码
    :param app_host: 应用系统主机地址
    :param target_ip: 目标存储设备IP（可选，指定后仅采集该设备）
    """
    try:
        # 1. 初始化API客户端
        app_ip = app_host.split(':')[0]
        app_api = AppApiClient(app_ip)
        storage_api = StorageApiClient()
        
        # 2. 查询现有实例（用于后续清理过期数据）
        logger.info("查询应用系统现有实例信息")
        existing_controllers = app_api.search_instances('DISK_ARRAY_CONTROLLER', {'fields': {"name": True}})
        existing_disk_zones = app_api.search_instances('DISK_ZONE', {'fields': {"name": True}})
        existing_pools = app_api.search_instances('CENTRALIZED_STORAGE_POOL', {'fields': {"name": True}})
        existing_disks = app_api.search_instances('DISK', {'fields': {"name": True}})
        existing_luns = app_api.search_instances('LUN', {'fields': {"name": True}})
        existing_hosts = app_api.search_instances('DISK_ARRAY_HOST', {'fields': {"name": True}})