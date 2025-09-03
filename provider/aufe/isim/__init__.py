import re
import hashlib
import random
from typing import List, Optional, Dict
from loguru import logger
from provider.aufe.isim.model import (
    BuildingInfo,
    FloorInfo,
    RoomInfo,
    RoomBindingInfo,
    ElectricityBalance,
    ElectricityUsageRecord,
    ElectricityInfo,
    PaymentRecord,
    PaymentInfo,
    ErrorElectricityInfo,
    ErrorPaymentInfo,
    UnboundRoomElectricityInfo,
    UnboundRoomPaymentInfo,
)
from provider.aufe.client import (
    AUFEConnection,
    aufe_config_global,
    activity_tracker,
    retry_async,
    AUFEConnectionError,
    RetryConfig
)
from bs4 import BeautifulSoup


class ISIMConfig:
    """ISIM后勤电费系统配置常量"""
    DEFAULT_BASE_URL = "http://hqkd-aufe-edu-cn.vpn2.aufe.edu.cn/"
    
    # 各类请求的相对路径
    ENDPOINTS = {
        "init_session": "/go",
        "about_page": "/about",
        "floors_api": "/about/floors/",
        "rooms_api": "/about/rooms/",
        "rebinding_api": "/about/rebinding",
        "usage_records": "/use/record",
        "payment_records": "/pay/record",
    }


class ISIMClient:
    """ISIM后勤电费系统客户端"""

    def __init__(
        self,
        vpn_connection: AUFEConnection,
        base_url: str = ISIMConfig.DEFAULT_BASE_URL,
        retry_config: Optional[RetryConfig] = None
    ):
        """
        初始化ISIM系统客户端

        Args:
            vpn_connection: VPN连接实例
            base_url: ISIM系统基础URL
            retry_config: 重试配置
        """
        self.vpn_connection = vpn_connection
        self.base_url = base_url.rstrip("/")
        self.retry_config = retry_config or RetryConfig()
        self.session_cookie = None
        
        # 从VPN连接获取用户ID和twfid
        self.user_id = getattr(vpn_connection, 'student_id', 'unknown')
        self.twfid = vpn_connection.get_twfid()
        
        logger.info(f"ISIM系统客户端初始化: base_url={self.base_url}, user_id={self.user_id}, twfid={'***' + self.twfid[-4:] if self.twfid else 'None'}")
        
        # 验证twfid是否可用
        if not self.twfid:
            logger.warning("警告: 未获取到twfid，VPN访问可能会失败")
    
    def is_session_valid(self) -> bool:
        """
        检查ISIM会话是否仍然有效
        依赖于AUFE连接状态
        
        Returns:
            bool: 会话是否有效
        """
        # 检查AUFE连接状态
        if not (self.vpn_connection.is_active()):
            logger.info(f"AUFE连接已断开，清理ISIM会话: user_id={self.user_id}")
            self._cleanup_session()
            return False
        if not self.session_cookie:
            return self.init_session()
        return True
    
    def _cleanup_session(self) -> None:
        """
        清理ISIM会话数据
        """
        if self.session_cookie:
            logger.info(f"清理ISIM会话: user_id={self.user_id}, session={self.session_cookie[:8]}...")
            self.session_cookie = None
        
        # 从缓存中移除自己
        self._remove_from_cache()
    
    def _remove_from_cache(self) -> None:
        """
        从客户端缓存中移除自己
        """
        try:
            from provider.aufe.isim.depends import _isim_clients
            if self.user_id in _isim_clients:
                del _isim_clients[self.user_id]
                logger.info(f"从缓存中移除ISIM客户端: user_id={self.user_id}")
        except Exception as e:
            logger.error(f"移除ISIM客户端缓存失败: {str(e)}")
        
    def _get_default_headers(self) -> dict:
        """获取默认请求头"""
        return aufe_config_global.DEFAULT_HEADERS.copy()
        
    def _get_isim_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> dict:
        """获取ISIM系统专用请求头"""
        headers = {
            **self._get_default_headers(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # 处理Cookie，确保包含twfid
        if additional_headers:
            # 如果有额外的headers，先合并
            headers.update(additional_headers)
            
            # 特殊处理Cookie，确保包含twfid
            if "Cookie" in headers and self.twfid:
                existing_cookie = headers["Cookie"]
                # 检查是否已包含TWFID
                if "TWFID=" not in existing_cookie.upper():
                    headers["Cookie"] = f"{existing_cookie}; TWFID={self.twfid}"
            elif "Cookie" not in headers and self.twfid:
                headers["Cookie"] = f"TWFID={self.twfid}"
                
        elif self.twfid:
            # 如果没有额外headers但有twfid，直接设置
            headers["Cookie"] = f"TWFID={self.twfid}"
            
        return headers
        
    def _generate_session_params(self) -> Dict[str, str]:
        """生成会话参数（openid和sn）"""
        # 使用学号作为种子生成随机数
        seed = self.user_id if self.user_id != 'unknown' else 'default'
        
        # 生成openid - 基于学号的哈希值
        openid_hash = hashlib.md5(f"{seed}_openid".encode()).hexdigest()
        openid = openid_hash[:15] + str(random.randint(100, 999))
        
        # 生成sn - 简单使用固定值
        sn = "sn"
        
        return {"openid": openid, "sn": sn}

    @activity_tracker
    @retry_async()
    async def init_session(self) -> bool:
        """
        初始化ISIM会话，获取JSESSIONID

        Returns:
            bool: 是否成功获取会话
        """
        try:
            logger.info("开始初始化ISIM会话")
            
            params = self._generate_session_params()
            # 初始化会话时只使用基本的VPN头信息，不添加额外的Cookie
            headers = self._get_default_headers()
            logger.info(f"初始化会话请求头: {headers}")
            
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/go",
                params=params,
                headers=headers,
                follow_redirects=False  # 不自动跟随重定向，我们需要获取Set-Cookie
            )
            
            # 检查是否收到302重定向响应
            if response.status_code == 302:
                # 从Set-Cookie头中提取JSESSIONID
                set_cookie_header = response.headers.get('set-cookie', '')
                if 'JSESSIONID=' in set_cookie_header:
                    # 提取JSESSIONID值
                    jsessionid_match = re.search(r'JSESSIONID=([^;]+)', set_cookie_header)
                    if jsessionid_match:
                        self.session_cookie = jsessionid_match.group(1)
                        logger.info(f"成功获取JSESSIONID: {self.session_cookie[:8]}...")
                        
                        # 验证重定向位置是否正确
                        location = response.headers.get('location', '')
                        if 'home' in location and 'jsessionid' in location:
                            logger.info(f"重定向位置正确: {location}")
                            return True
                        else:
                            logger.warning(f"重定向位置异常: {location}")
                            return True  # 仍然返回True，因为已获取到JSESSIONID
                
                logger.error("未能从Set-Cookie头中提取JSESSIONID")
                return False
            else:
                logger.error(f"期望302重定向，但收到状态码: {response.status_code}")
                # 检查响应内容，可能包含错误信息
                if response.text:
                    logger.debug(f"响应内容: {response.text[:200]}...")
                return False
            
        except Exception as e:
            logger.error(f"初始化ISIM会话异常: {str(e)}")
            return False

    @activity_tracker
    @retry_async()
    async def get_buildings(self) -> List[BuildingInfo]:
        """
        获取楼栋列表

        Returns:
            List[BuildingInfo]: 楼栋信息列表
        """
        try:
            logger.info("开始获取楼栋列表")
            
            # 检查AUFE连接状态，如果断开则清理会话
            if not self.is_session_valid():
                logger.warning("AUFE连接已断开或会话无效，尝试重新初始化")
            
            # 确保会话已初始化
            if not self.session_cookie:
                if not await self.init_session():
                    return []
            
            headers = self._get_isim_headers({
                "Cookie": f"JSESSIONID={self.session_cookie}",
                "Referer": f"{self.base_url}/home;jsessionid={self.session_cookie}",
            })
            logger.info(f"获取楼栋列表请求头: {headers}")
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/about",
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AUFEConnectionError(f"获取楼栋信息失败，状态码: {response.status_code}")
            
            # 解析HTML页面获取楼栋信息
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找JavaScript中的楼栋数据
            buildings = []
            scripts = soup.find_all('script')
            
            for script in scripts:
                if script.string and 'pickerBuilding' in script.string:
                    # 提取values和displayValues
                    values_match = re.search(r'values:\s*\[(.*?)\]', script.string)
                    display_values_match = re.search(r'displayValues:\s*\[(.*?)\]', script.string)
                    
                    if values_match and display_values_match:
                        values_str = values_match.group(1)
                        display_values_str = display_values_match.group(1)
                        
                        # 解析values
                        values = [v.strip().strip('"') for v in values_str.split(',')]
                        display_values = [v.strip().strip('"') for v in display_values_str.split(',')]
                        
                        # 过滤掉空值和"请选择"
                        for i, (code, name) in enumerate(zip(values, display_values)):
                            if code and code != '""' and name != "请选择":
                                buildings.append(BuildingInfo(code=code, name=name))
                        break
            
            logger.info(f"成功获取{len(buildings)}个楼栋信息")
            return buildings
            
        except Exception as e:
            logger.error(f"获取楼栋列表异常: {str(e)}")
            return []

    @activity_tracker
    @retry_async()
    async def get_floors(self, building_code: str) -> List[FloorInfo]:
        """
        获取指定楼栋的楼层列表

        Args:
            building_code: 楼栋代码

        Returns:
            List[FloorInfo]: 楼层信息列表
        """
        try:
            logger.info(f"开始获取楼层列表，楼栋代码: {building_code}")
            
            # 检查AUFE连接状态
            if not self.is_session_valid():
                logger.warning("AUFE连接已断开或会话无效，尝试重新初始化")
            
            if not self.session_cookie:
                if not await self.init_session():
                    return []
            
            headers = self._get_isim_headers({
                "Cookie": f"JSESSIONID={self.session_cookie}",
                "Referer": f"{self.base_url}/about",
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest",
            })
            
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/about/floors/{building_code}",
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AUFEConnectionError(f"获取楼层信息失败，状态码: {response.status_code}")
            
            # 解析响应（可能是JavaScript对象字面量格式）
            try:
                data_str = response.text.strip()
                logger.debug(f"楼层响应原始数据: {data_str[:200]}...")
                
                # 先尝试标准JSON解析
                try:
                    json_data = response.json()
                except Exception:
                    # 如果JSON解析失败，手动转换JavaScript对象字面量为JSON格式
                    # 将属性名添加双引号
                    import re
                    json_str = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', data_str)
                    logger.debug(f"转换后的JSON字符串: {json_str[:200]}...")
                    import json
                    json_data = json.loads(json_str)
                
                floors = []
                
                if isinstance(json_data, list) and len(json_data) > 0:
                    floor_data = json_data[0]
                    floor_codes = floor_data.get('floordm', [])
                    floor_names = floor_data.get('floorname', [])
                    
                    # 跳过第一个空值（"请选择"）
                    for code, name in zip(floor_codes[1:], floor_names[1:]):
                        if code and name and name != "请选择":
                            floors.append(FloorInfo(code=code, name=name))
                    
                    logger.info(f"成功获取{len(floors)}个楼层信息")
                    return floors
                else:
                    logger.warning(f"楼层数据格式异常: {json_data}")
                    return []
                    
            except Exception as parse_error:
                logger.error(f"解析楼层数据异常: {str(parse_error)}")
                logger.error(f"响应内容: {response.text[:500]}")
                return []
            
        except Exception as e:
            logger.error(f"获取楼层列表异常: {str(e)}")
            return []

    @activity_tracker
    @retry_async()
    async def get_rooms(self, floor_code: str) -> List[RoomInfo]:
        """
        获取指定楼层的房间列表

        Args:
            floor_code: 楼层代码

        Returns:
            List[RoomInfo]: 房间信息列表
        """
        try:
            logger.info(f"开始获取房间列表，楼层代码: {floor_code}")
            
            # 检查AUFE连接状态
            if not self.is_session_valid():
                logger.warning("AUFE连接已断开或会话无效，尝试重新初始化")
            
            if not self.session_cookie:
                if not await self.init_session():
                    return []
            
            headers = self._get_isim_headers({
                "Cookie": f"JSESSIONID={self.session_cookie}",
                "Referer": f"{self.base_url}/about",
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest",
            })
            
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/about/rooms/{floor_code}",
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AUFEConnectionError(f"获取房间信息失败，状态码: {response.status_code}")
            
            # 解析响应（可能是JavaScript对象字面量格式）
            try:
                data_str = response.text.strip()
                logger.debug(f"房间响应原始数据: {data_str[:200]}...")
                
                # 先尝试标准JSON解析
                try:
                    json_data = response.json()
                except Exception:
                    # 如果JSON解析失败，手动转换JavaScript对象字面量为JSON格式
                    # 将属性名添加双引号
                    import re
                    json_str = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', data_str)
                    logger.debug(f"转换后的JSON字符串: {json_str[:200]}...")
                    import json
                    json_data = json.loads(json_str)
                
                rooms = []
                
                if isinstance(json_data, list) and len(json_data) > 0:
                    room_data = json_data[0]
                    room_codes = room_data.get('roomdm', [])
                    room_names = room_data.get('roomname', [])
                    
                    # 跳过第一个空值（"请选择"）
                    for code, name in zip(room_codes[1:], room_names[1:]):
                        if code and name and name != "请选择":
                            rooms.append(RoomInfo(code=code, name=name))
                    
                    logger.info(f"成功获取{len(rooms)}个房间信息")
                    return rooms
                else:
                    logger.warning(f"房间数据格式异常: {json_data}")
                    return []
                    
            except Exception as parse_error:
                logger.error(f"解析房间数据异常: {str(parse_error)}")
                logger.error(f"响应内容: {response.text[:500]}")
                return []
            
        except Exception as e:
            logger.error(f"获取房间列表异常: {str(e)}")
            return []

    @activity_tracker
    @retry_async()
    async def bind_room(self, building_code: str, floor_code: str, room_code: str) -> Optional[RoomBindingInfo]:
        """
        绑定房间

        Args:
            building_code: 楼栋代码
            floor_code: 楼层代码
            room_code: 房间代码

        Returns:
            Optional[RoomBindingInfo]: 绑定结果信息
        """
        try:
            logger.info(f"开始绑定房间: {building_code}-{floor_code}-{room_code}")
            
            if not self.session_cookie:
                if not await self.init_session():
                    return None
            
            # 首先获取楼栋、楼层、房间的显示名称
            buildings = await self.get_buildings()
            building_name = next((b.name for b in buildings if b.code == building_code), "")
            
            floors = await self.get_floors(building_code) if building_name else []
            floor_name = next((f.name for f in floors if f.code == floor_code), "")
            
            rooms = await self.get_rooms(floor_code) if floor_name else []
            room_name = next((r.name for r in rooms if r.code == room_code), "")
            
            if not all([building_name, floor_name, room_name]):
                logger.error("无法获取完整的房间信息")
                return None
            
            # room_code就是完整的房间ID，无需拼接
            room_id = room_code
            display_text = f"{building_name}/{floor_name}/{room_name}"
            
            # 执行绑定请求
            params = self._generate_session_params()
            
            headers = self._get_isim_headers({
                "Cookie": f"JSESSIONID={self.session_cookie}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/about",
                "X-Requested-With": "XMLHttpRequest",
            })
            
            data = {
                "sn": params["sn"],
                "openid": params["openid"],
                "roomdm": room_id,
                "room": display_text,
                "mode": "u"  # u表示更新绑定
            }
            
            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/about/rebinding",
                headers=headers,
                data=data,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AUFEConnectionError(f"房间绑定失败，状态码: {response.status_code}")
            
            # 解析响应（可能是JavaScript对象字面量格式）
            try:
                data_str = response.text.strip()
                logger.debug(f"房间绑定响应原始数据: {data_str}")
                
                if data_str and len(data_str) > 0:
                    # 先尝试标准JSON解析
                    try:
                        json_data = response.json()
                    except Exception:
                        # 如果JSON解析失败，手动转换JavaScript对象字面量为JSON格式
                        import re
                        json_str = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', data_str)
                        logger.debug(f"转换后的JSON字符串: {json_str}")
                        import json
                        json_data = json.loads(json_str)
                    
                    # 解析绑定信息
                    if isinstance(json_data, list) and len(json_data) > 0:
                        binding_data = json_data[0]
                        binding_info = binding_data.get('bindinginfo', '')
                        
                        if binding_info:
                            binding_result = RoomBindingInfo(
                                building=BuildingInfo(code=building_code, name=building_name),
                                floor=FloorInfo(code=floor_code, name=floor_name),
                                room=RoomInfo(code=room_code, name=room_name),
                                room_id=room_id,
                                display_text=binding_info
                            )
                            logger.info(f"房间绑定成功: {binding_result.display_text}")
                            return binding_result
                
                logger.error(f"房间绑定响应格式异常: {data_str}")
                return None
                
            except Exception as parse_error:
                logger.error(f"解析绑定结果异常: {str(parse_error)}")
                return None
            
        except Exception as e:
            logger.error(f"绑定房间异常: {str(e)}")
            return None

    async def _check_room_binding_with_data(self, binding_record) -> bool:
        """
        使用提供的绑定记录检查房间绑定状态
        
        Args:
            binding_record: 数据库中的绑定记录
            
        Returns:
            bool: 是否绑定验证成功
        """
        try:
            if not binding_record:
                logger.warning(f"用户 {self.user_id} 没有房间绑定记录")
                return False
            
            # 首先检查AUFE连接状态，如果已断开则直接返回False
            if not self.vpn_connection.login_status() or not self.vpn_connection.uaap_login_status():
                logger.warning(f"用户 {self.user_id} AUFE连接已断开，无法验证房间绑定")
                return False
            
            # 使用真实的绑定数据进行验证
            if not self.session_cookie:
                if not await self.init_session():
                    return False
            
            params = self._generate_session_params()
            
            headers = self._get_isim_headers({
                "Cookie": f"JSESSIONID={self.session_cookie}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/about",
                "X-Requested-With": "XMLHttpRequest",
            })
            
            # 使用数据库中的真实房间信息进行绑定验证
            data = {
                "sn": params["sn"],
                "openid": params["openid"],
                "roomdm": binding_record.room_id,  # 使用真实的房间ID
                "room": f"{binding_record.building_name}/{binding_record.floor_name}/{binding_record.room_name}",
                "mode": "u"
            }
            
            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/about/rebinding",
                headers=headers,
                data=data,
                follow_redirects=True
            )
            
            if response.status_code == 200:
                # 检查响应中是否包含有效的绑定信息
                data_str = response.text.strip()
                if "bindinginfo" in data_str and len(data_str) > 10:
                    logger.info(f"用户 {self.user_id} 房间绑定验证成功")
                    return True
            
            logger.warning(f"用户 {self.user_id} 房间绑定验证失败，响应: {response.text}")
            return False
            
        except Exception as e:
            logger.error(f"房间绑定验证异常: {str(e)}")
            return False

    @activity_tracker
    @retry_async()
    async def get_electricity_info(self, binding_record=None) -> ElectricityInfo:
        """
        获取电费信息（余额和用电记录）
        需要先绑定房间才能查询

        Returns:
            ElectricityInfo: 电费信息，失败时返回错误模型
        """
        def _create_error_info() -> ErrorElectricityInfo:
            """创建错误电费信息"""
            return ErrorElectricityInfo()
            
        def _create_unbound_error_info() -> UnboundRoomElectricityInfo:
            """创建未绑定房间错误信息"""
            return UnboundRoomElectricityInfo()
            
        try:
            logger.info("开始获取电费信息")
            
            # 检查AUFE连接状态
            if not self.is_session_valid():
                logger.warning("AUFE连接已断开或会话无效，无法获取电费信息")
                return _create_error_info()
            
            # 检查房间绑定状态
            if not binding_record:
                logger.warning(f"用户 {self.user_id} 未绑定房间，返回未绑定错误信息")
                return _create_unbound_error_info()
            
            if not self.session_cookie:
                if not await self.init_session():
                    return _create_error_info()
            
            headers = self._get_isim_headers({
                "Cookie": f"JSESSIONID={self.session_cookie}",
                "Referer": f"{self.base_url}/about",
            })
            
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/use/record",
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AUFEConnectionError(f"获取电费信息失败，状态码: {response.status_code}")
            
            # 解析HTML页面
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取余额信息
            balance_items = soup.find_all('li', class_='item-content')
            remaining_purchased = 0.0
            remaining_subsidy = 0.0
            
            for item in balance_items:
                title_div = item.find('div', class_='item-title')
                after_div = item.find('div', class_='item-after')
                
                if title_div and after_div:
                    title = title_div.get_text(strip=True)
                    value_text = after_div.get_text(strip=True)
                    
                    # 提取数值
                    value_match = re.search(r'([\d.]+)', value_text)
                    if value_match:
                        value = float(value_match.group(1))
                        
                        if '剩余购电' in title:
                            remaining_purchased = value
                        elif '剩余补助' in title:
                            remaining_subsidy = value
            
            # 提取用电记录
            usage_records = []
            record_items = soup.select('#divRecord ul li')
            
            for item in record_items:
                title_div = item.find('div', class_='item-title')
                after_div = item.find('div', class_='item-after')
                subtitle_div = item.find('div', class_='item-subtitle')
                
                if title_div and after_div and subtitle_div:
                    record_time = title_div.get_text(strip=True)
                    usage_text = after_div.get_text(strip=True)
                    meter_text = subtitle_div.get_text(strip=True)
                    
                    # 提取用电量
                    usage_match = re.search(r'([\d.]+)度', usage_text)
                    if usage_match:
                        usage_amount = float(usage_match.group(1))
                        
                        # 提取电表名称
                        meter_match = re.search(r'电表:\s*(.+)', meter_text)
                        meter_name = meter_match.group(1) if meter_match else meter_text
                        
                        usage_records.append(ElectricityUsageRecord(
                            record_time=record_time,
                            usage_amount=usage_amount,
                            meter_name=meter_name
                        ))
            
            balance = ElectricityBalance(
                remaining_purchased=remaining_purchased,
                remaining_subsidy=remaining_subsidy
            )
            
            result = ElectricityInfo(
                balance=balance,
                usage_records=usage_records
            )
            
            logger.info(f"成功获取电费信息: 购电余额={remaining_purchased}度, 补助余额={remaining_subsidy}度, 记录数={len(usage_records)}")
            return result
            
        except Exception as e:
            logger.error(f"获取电费信息异常: {str(e)}")
            return _create_error_info()

    @activity_tracker
    @retry_async()
    async def get_payment_info(self, binding_record=None) -> PaymentInfo:
        """
        获取充值信息（余额和充值记录）
        需要先绑定房间才能查询

        Returns:
            PaymentInfo: 充值信息，失败时返回错误模型
        """
        def _create_error_info() -> ErrorPaymentInfo:
            """创建错误充值信息"""
            return ErrorPaymentInfo()
            
        def _create_unbound_error_info() -> UnboundRoomPaymentInfo:
            """创建未绑定房间错误信息"""
            return UnboundRoomPaymentInfo()
            
        try:
            logger.info("开始获取充值信息")
            
            # 检查AUFE连接状态
            if not self.is_session_valid():
                logger.warning("AUFE连接已断开或会话无效，无法获取充值信息")
                return _create_error_info()
            
            # 检查房间绑定状态
            if not binding_record:
                logger.warning(f"用户 {self.user_id} 未绑定房间，返回未绑定错误信息")
                return _create_unbound_error_info()
            
            if not self.session_cookie:
                if not await self.init_session():
                    return _create_error_info()
            
            headers = self._get_isim_headers({
                "Cookie": f"JSESSIONID={self.session_cookie}",
                "Referer": f"{self.base_url}/use/record",
            })
            
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/pay/record",
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AUFEConnectionError(f"获取充值信息失败，状态码: {response.status_code}")
            
            # 解析HTML页面
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取余额信息（与电费信息相同）
            balance_items = soup.find_all('li', class_='item-content')
            remaining_purchased = 0.0
            remaining_subsidy = 0.0
            
            for item in balance_items:
                title_div = item.find('div', class_='item-title')
                after_div = item.find('div', class_='item-after')
                
                if title_div and after_div:
                    title = title_div.get_text(strip=True)
                    value_text = after_div.get_text(strip=True)
                    
                    # 提取数值
                    value_match = re.search(r'([\d.]+)', value_text)
                    if value_match:
                        value = float(value_match.group(1))
                        
                        if '剩余购电' in title:
                            remaining_purchased = value
                        elif '剩余补助' in title:
                            remaining_subsidy = value
            
            # 提取充值记录
            payment_records = []
            record_items = soup.select('#divRecord ul li')
            
            for item in record_items:
                title_div = item.find('div', class_='item-title')
                after_div = item.find('div', class_='item-after')
                subtitle_div = item.find('div', class_='item-subtitle')
                
                if title_div and after_div and subtitle_div:
                    payment_time = title_div.get_text(strip=True)
                    amount_text = after_div.get_text(strip=True)
                    type_text = subtitle_div.get_text(strip=True)
                    
                    # 提取金额
                    amount_match = re.search(r'(-?[\d.]+)元', amount_text)
                    if amount_match:
                        amount = float(amount_match.group(1))
                        
                        # 提取充值类型
                        type_match = re.search(r'类型:\s*(.+)', type_text)
                        payment_type = type_match.group(1) if type_match else type_text
                        
                        payment_records.append(PaymentRecord(
                            payment_time=payment_time,
                            amount=amount,
                            payment_type=payment_type
                        ))
            
            balance = ElectricityBalance(
                remaining_purchased=remaining_purchased,
                remaining_subsidy=remaining_subsidy
            )
            
            result = PaymentInfo(
                balance=balance,
                payment_records=payment_records
            )
            
            logger.info(f"成功获取充值信息: 购电余额={remaining_purchased}度, 补助余额={remaining_subsidy}度, 记录数={len(payment_records)}")
            return result
            
        except Exception as e:
            logger.error(f"获取充值信息异常: {str(e)}")
            return _create_error_info()
