from typing import Optional, Dict, Any, Union
from pathlib import Path
from loguru import logger

from config import config_manager

# 可选导入aioboto3
try:
    import aioboto3
    from botocore.exceptions import ClientError, NoCredentialsError
    HAS_BOTO3 = True
except ImportError:
    aioboto3 = None
    ClientError = Exception
    NoCredentialsError = Exception
    HAS_BOTO3 = False


class S3Client:
    """异步S3客户端"""
    
    def __init__(self):
        self._session = None
        self._client = None
        self._config = None
        
        if not HAS_BOTO3:
            logger.warning("aioboto3未安装，S3客户端功能不可用")
    
    def _get_s3_config(self):
        """获取S3配置"""
        if self._config is None:
            self._config = config_manager.get_settings().s3
        return self._config
    
    async def _get_client(self):
        """获取S3客户端"""
        if not HAS_BOTO3:
            raise RuntimeError("aioboto3未安装，无法使用S3客户端功能。请运行: pip install aioboto3")
            
        if self._client is None:
            config = self._get_s3_config()
            
            # 验证必要的配置
            if not config.access_key_id or not config.secret_access_key:
                raise ValueError("S3 access_key_id 和 secret_access_key 不能为空")
            
            if not config.bucket_name:
                raise ValueError("S3 bucket_name 不能为空")
            
            if self._session is None:
                self._session = aioboto3.Session()
            
            self._client = self._session.client(
                's3',
                aws_access_key_id=config.access_key_id,
                aws_secret_access_key=config.secret_access_key,
                endpoint_url=config.endpoint_url,
                region_name=config.region_name,
                use_ssl=config.use_ssl,
                config=aioboto3.Config(signature_version=config.signature_version)
            )
        
        return self._client
    
    async def upload_file(
        self, 
        file_path: Union[str, Path], 
        key: str, 
        bucket: Optional[str] = None,
        extra_args: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        上传文件到S3
        
        Args:
            file_path: 本地文件路径
            key: S3对象键名
            bucket: 存储桶名称，如果为None则使用配置中的默认bucket
            extra_args: 额外参数，如metadata, ACL等
            
        Returns:
            bool: 是否上传成功
        """
        try:
            config = self._get_s3_config()
            bucket = bucket or config.bucket_name
            
            if not bucket:
                raise ValueError("bucket名称不能为空")
            
            async with await self._get_client() as s3:
                await s3.upload_file(
                    Filename=str(file_path),
                    Bucket=bucket,
                    Key=key,
                    ExtraArgs=extra_args or {}
                )
            
            logger.info(f"文件上传成功: {file_path} -> s3://{bucket}/{key}")
            return True
            
        except FileNotFoundError:
            logger.error(f"文件不存在: {file_path}")
            return False
        except NoCredentialsError:
            logger.error("S3凭据未配置或无效")
            return False
        except ClientError as e:
            logger.error(f"S3客户端错误: {e}")
            return False
        except Exception as e:
            logger.error(f"上传文件失败: {e}")
            return False
    
    async def download_file(
        self, 
        key: str, 
        file_path: Union[str, Path], 
        bucket: Optional[str] = None
    ) -> bool:
        """
        从S3下载文件
        
        Args:
            key: S3对象键名
            file_path: 本地保存路径
            bucket: 存储桶名称，如果为None则使用配置中的默认bucket
            
        Returns:
            bool: 是否下载成功
        """
        try:
            config = self._get_s3_config()
            bucket = bucket or config.bucket_name
            
            if not bucket:
                raise ValueError("bucket名称不能为空")
            
            # 确保目标目录存在
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            async with await self._get_client() as s3:
                await s3.download_file(
                    Bucket=bucket,
                    Key=key,
                    Filename=str(file_path)
                )
            
            logger.info(f"文件下载成功: s3://{bucket}/{key} -> {file_path}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.error(f"S3对象不存在: s3://{bucket}/{key}")
            else:
                logger.error(f"S3客户端错误: {e}")
            return False
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return False
    
    async def upload_bytes(
        self, 
        data: bytes, 
        key: str, 
        bucket: Optional[str] = None,
        content_type: Optional[str] = None,
        extra_args: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        上传字节数据到S3
        
        Args:
            data: 要上传的字节数据
            key: S3对象键名
            bucket: 存储桶名称，如果为None则使用配置中的默认bucket
            content_type: 内容类型
            extra_args: 额外参数
            
        Returns:
            bool: 是否上传成功
        """
        try:
            config = self._get_s3_config()
            bucket = bucket or config.bucket_name
            
            if not bucket:
                raise ValueError("bucket名称不能为空")
            
            extra_args = extra_args or {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            async with await self._get_client() as s3:
                await s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=data,
                    **extra_args
                )
            
            logger.info(f"数据上传成功: s3://{bucket}/{key}")
            return True
            
        except Exception as e:
            logger.error(f"上传数据失败: {e}")
            return False
    
    async def download_bytes(
        self, 
        key: str, 
        bucket: Optional[str] = None
    ) -> Optional[bytes]:
        """
        从S3下载字节数据
        
        Args:
            key: S3对象键名
            bucket: 存储桶名称，如果为None则使用配置中的默认bucket
            
        Returns:
            Optional[bytes]: 下载的字节数据，失败时返回None
        """
        try:
            config = self._get_s3_config()
            bucket = bucket or config.bucket_name
            
            if not bucket:
                raise ValueError("bucket名称不能为空")
            
            async with await self._get_client() as s3:
                response = await s3.get_object(Bucket=bucket, Key=key)
                async with response['Body'] as stream:
                    data = await stream.read()
            
            logger.info(f"数据下载成功: s3://{bucket}/{key}")
            return data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.error(f"S3对象不存在: s3://{bucket}/{key}")
            else:
                logger.error(f"S3客户端错误: {e}")
            return None
        except Exception as e:
            logger.error(f"下载数据失败: {e}")
            return None
    
    async def delete_object(
        self, 
        key: str, 
        bucket: Optional[str] = None
    ) -> bool:
        """
        删除S3对象
        
        Args:
            key: S3对象键名
            bucket: 存储桶名称，如果为None则使用配置中的默认bucket
            
        Returns:
            bool: 是否删除成功
        """
        try:
            config = self._get_s3_config()
            bucket = bucket or config.bucket_name
            
            if not bucket:
                raise ValueError("bucket名称不能为空")
            
            async with await self._get_client() as s3:
                await s3.delete_object(Bucket=bucket, Key=key)
            
            logger.info(f"对象删除成功: s3://{bucket}/{key}")
            return True
            
        except Exception as e:
            logger.error(f"删除对象失败: {e}")
            return False
    
    async def list_objects(
        self, 
        prefix: str = "", 
        bucket: Optional[str] = None,
        max_keys: int = 1000
    ) -> list:
        """
        列出S3对象
        
        Args:
            prefix: 对象键前缀
            bucket: 存储桶名称，如果为None则使用配置中的默认bucket
            max_keys: 最大返回对象数量
            
        Returns:
            list: 对象列表
        """
        try:
            config = self._get_s3_config()
            bucket = bucket or config.bucket_name
            
            if not bucket:
                raise ValueError("bucket名称不能为空")
            
            async with await self._get_client() as s3:
                response = await s3.list_objects_v2(
                    Bucket=bucket,
                    Prefix=prefix,
                    MaxKeys=max_keys
                )
            
            objects = response.get('Contents', [])
            logger.info(f"列出对象成功: s3://{bucket}/{prefix}* ({len(objects)}个对象)")
            return objects
            
        except Exception as e:
            logger.error(f"列出对象失败: {e}")
            return []
    
    async def object_exists(
        self, 
        key: str, 
        bucket: Optional[str] = None
    ) -> bool:
        """
        检查S3对象是否存在
        
        Args:
            key: S3对象键名
            bucket: 存储桶名称，如果为None则使用配置中的默认bucket
            
        Returns:
            bool: 对象是否存在
        """
        try:
            config = self._get_s3_config()
            bucket = bucket or config.bucket_name
            
            if not bucket:
                raise ValueError("bucket名称不能为空")
            
            async with await self._get_client() as s3:
                await s3.head_object(Bucket=bucket, Key=key)
            
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"检查对象存在性失败: {e}")
                return False
        except Exception as e:
            logger.error(f"检查对象存在性失败: {e}")
            return False
    
    async def close(self):
        """关闭S3客户端"""
        if self._client:
            await self._client.close()
            self._client = None
        if self._session:
            await self._session.close()
            self._session = None


# 全局S3客户端实例
s3_client = S3Client()