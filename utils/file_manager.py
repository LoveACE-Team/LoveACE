import os
import uuid
import json
import base64
import aiofiles
import glob
from typing import Optional, Dict, Any
from pathlib import Path


class FileManager:
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        self.avatar_path = self.base_path / "avatars"
        self.background_path = self.base_path / "backgrounds"
        self.settings_path = self.base_path / "settings"
        
        # 确保目录存在
        self.avatar_path.mkdir(parents=True, exist_ok=True)
        self.background_path.mkdir(parents=True, exist_ok=True)
        self.settings_path.mkdir(parents=True, exist_ok=True)
    
    def generate_file_id(self) -> str:
        """生成文件ID"""
        return str(uuid.uuid4())
    
    async def cleanup_user_files(self, userid: str, file_type: str) -> None:
        """
        清理用户的所有旧文件
        :param userid: 用户ID
        :param file_type: 文件类型 ('avatar', 'background', 'settings')
        """
        if file_type == 'avatar':
            pattern = self.avatar_path / f"{userid}_*"
        elif file_type == 'background':
            pattern = self.background_path / f"{userid}_*"
        elif file_type == 'settings':
            pattern = self.settings_path / f"{userid}_*"
        else:
            return
        
        # 删除所有匹配的文件
        for file_path in glob.glob(str(pattern)):
            try:
                Path(file_path).unlink()
            except Exception:
                pass  # 忽略删除失败
    
    async def save_avatar(self, userid: str, avatar_base64: str) -> str:
        """
        保存用户头像，删除旧头像
        :param userid: 用户ID
        :param avatar_base64: base64编码的头像数据
        :return: 文件名
        """
        if not avatar_base64:
            return ""
        
        try:
            # 先清理旧的头像文件
            await self.cleanup_user_files(userid, 'avatar')
            
            # 解析base64数据
            if avatar_base64.startswith('data:'):
                # 处理data URI格式
                header, data = avatar_base64.split(',', 1)
                # 提取文件格式
                if 'image/png' in header:
                    ext = 'png'
                elif 'image/jpeg' in header or 'image/jpg' in header:
                    ext = 'jpg'
                elif 'image/gif' in header:
                    ext = 'gif'
                else:
                    ext = 'png'  # 默认格式
            else:
                # 纯base64数据，默认为png
                data = avatar_base64
                ext = 'png'
            
            # 生成文件名
            file_id = self.generate_file_id()
            filename = f"{userid}_{file_id}.{ext}"
            file_path = self.avatar_path / filename
            
            # 解码并保存文件
            image_data = base64.b64decode(data)
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(image_data)
            
            return filename
        except Exception as e:
            raise ValueError(f"保存头像失败: {str(e)}")
    
    async def get_avatar(self, filename: str) -> Optional[bytes]:
        """
        获取用户头像
        :param filename: 文件名
        :return: 图片数据
        """
        if not filename:
            return None
        
        file_path = self.avatar_path / filename
        if not file_path.exists():
            return None
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except Exception:
            return None
    
    async def delete_avatar(self, filename: str) -> bool:
        """
        删除用户头像
        :param filename: 文件名
        :return: 是否删除成功
        """
        if not filename:
            return True
        
        file_path = self.avatar_path / filename
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception:
                return False
        return True
    
    async def save_background(self, userid: str, background_base64: str) -> str:
        """
        保存用户背景，删除旧背景
        :param userid: 用户ID
        :param background_base64: base64编码的背景数据
        :return: 文件名
        """
        if not background_base64:
            return ""
        
        try:
            # 先清理旧的背景文件
            await self.cleanup_user_files(userid, 'background')
            
            # 解析base64数据
            if background_base64.startswith('data:'):
                # 处理data URI格式
                header, data = background_base64.split(',', 1)
                # 提取文件格式
                if 'image/png' in header:
                    ext = 'png'
                elif 'image/jpeg' in header or 'image/jpg' in header:
                    ext = 'jpg'
                elif 'image/gif' in header:
                    ext = 'gif'
                elif 'image/webp' in header:
                    ext = 'webp'
                else:
                    ext = 'png'  # 默认格式
            else:
                # 纯base64数据，默认为png
                data = background_base64
                ext = 'png'
            
            # 生成文件名
            file_id = self.generate_file_id()
            filename = f"{userid}_{file_id}.{ext}"
            file_path = self.background_path / filename
            
            # 解码并保存文件
            image_data = base64.b64decode(data)
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(image_data)
            
            return filename
        except Exception as e:
            raise ValueError(f"保存背景失败: {str(e)}")
    
    async def get_background(self, filename: str) -> Optional[bytes]:
        """
        获取用户背景
        :param filename: 文件名
        :return: 图片数据
        """
        if not filename:
            return None
        
        file_path = self.background_path / filename
        if not file_path.exists():
            return None
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except Exception:
            return None
    
    async def delete_background(self, filename: str) -> bool:
        """
        删除用户背景
        :param filename: 文件名
        :return: 是否删除成功
        """
        if not filename:
            return True
        
        file_path = self.background_path / filename
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception:
                return False
        return True
    
    async def save_settings(self, userid: str, settings: Dict[str, Any]) -> str:
        """
        保存用户设置，删除旧设置
        :param userid: 用户ID
        :param settings: 设置字典
        :return: 文件名
        """
        try:
            # 先清理旧的设置文件
            await self.cleanup_user_files(userid, 'settings')
            
            # 生成文件名
            file_id = self.generate_file_id()
            filename = f"{userid}_{file_id}.json"
            file_path = self.settings_path / filename
            
            # 保存JSON文件
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(settings, ensure_ascii=False, indent=2))
            
            return filename
        except Exception as e:
            raise ValueError(f"保存设置失败: {str(e)}")
    
    async def get_settings(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        获取用户设置
        :param filename: 文件名
        :return: 设置字典
        """
        if not filename:
            return None
        
        file_path = self.settings_path / filename
        if not file_path.exists():
            return None
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except Exception:
            return None
    
    async def delete_settings(self, filename: str) -> bool:
        """
        删除用户设置文件
        :param filename: 文件名
        :return: 是否删除成功
        """
        if not filename:
            return True
        
        file_path = self.settings_path / filename
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception:
                return False
        return True


# 全局文件管理器实例
file_manager = FileManager()


def validate_settings(settings: Dict[str, Any]) -> bool:
    """
    验证设置字典是否符合要求的格式
    :param settings: 设置字典
    :return: 是否有效
    """
    required_fields = {
        'theme': str,
        'lightModeOpacity': (int, float),
        'lightModeBrightness': (int, float),
        'darkModeOpacity': (int, float),
        'darkModeBrightness': (int, float),
        'backgroundBlur': (int, float),
    }
    
    try:
        # 检查所有必需字段是否存在且类型正确
        for field, expected_type in required_fields.items():
            if field not in settings:
                return False
            if not isinstance(settings[field], expected_type):
                return False
        
        # 验证数值范围（0-1）
        numeric_fields = ['lightModeOpacity', 'lightModeBrightness', 
                         'darkModeOpacity', 'darkModeBrightness', 'backgroundBlur']
        for field in numeric_fields:
            value = settings[field]
            if not (0 <= value <= 1):
                return False
        
        # 验证主题值
        valid_themes = ['light', 'dark', 'system', 'ThemeMode.light', 'ThemeMode.dark', 'ThemeMode.system']
        if settings['theme'] not in valid_themes:
            return False
        
        return True
    except Exception:
        return False 