"""
Redis Client Utilities.
Provides connection management and queue operations for the orchestration system.
"""

import redis
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime


logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper for queue and state management."""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, 
                 db: int = 0, password: Optional[str] = None, 
                 decode_responses: bool = True):
        """
        Initialize Redis client.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (optional)
            decode_responses: Decode responses to strings
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.decode_responses = decode_responses
        
        self.redis_client: Optional[redis.Redis] = None
        self.connect()
    
    def connect(self) -> bool:
        """
        Connect to Redis.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=self.decode_responses,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Connected to Redis at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.redis_client = None
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        if self.redis_client is None:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def ensure_connected(self) -> bool:
        """Ensure connection, reconnect if necessary."""
        if not self.is_connected():
            return self.connect()
        return True
    
    # ========== Queue Operations ==========
    
    def push_job(self, queue_name: str, job_id: str) -> bool:
        """
        Push job ID to queue.
        
        Args:
            queue_name: Queue name (e.g., 'jobs:worker-1', 'jobs:capability:CPU')
            job_id: Job ID to push
            
        Returns:
            True if successful, False otherwise
        """
        if not self.ensure_connected():
            return False
        
        try:
            self.redis_client.lpush(queue_name, job_id)
            logger.debug(f"Pushed job {job_id} to queue {queue_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to push job to queue: {e}")
            return False
    
    def pop_job(self, queue_names: List[str], timeout: int = 1) -> Optional[str]:
        """
        Pop job from first available queue (non-blocking or blocking with timeout).
        
        Args:
            queue_names: List of queue names to check (in order)
            timeout: Blocking timeout in seconds
            
        Returns:
            Job ID if found, None otherwise
        """
        if not self.ensure_connected():
            return None
        
        try:
            # Try each queue in order
            for queue_name in queue_names:
                result = self.redis_client.rpop(queue_name)
                if result:
                    logger.debug(f"Popped job from queue {queue_name}: {result}")
                    return result
            
            return None
        except Exception as e:
            logger.error(f"Failed to pop job from queues: {e}")
            return None
    
    def pop_job_blocking(self, queue_names: List[str], timeout: int = 0) -> Optional[tuple]:
        """
        Pop job from queues with blocking (BRPOP).
        
        Args:
            queue_names: List of queue names
            timeout: Blocking timeout (0 = wait forever)
            
        Returns:
            Tuple of (queue_name, job_id) if found, None otherwise
        """
        if not self.ensure_connected():
            return None
        
        try:
            result = self.redis_client.brpop(queue_names, timeout=timeout)
            if result:
                queue_name, job_id = result
                logger.debug(f"Popped job from queue {queue_name}: {job_id}")
                return (queue_name, job_id)
            return None
        except Exception as e:
            logger.error(f"Failed to pop job (blocking) from queues: {e}")
            return None
    
    def push_result(self, result_data: Dict[str, Any]) -> bool:
        """
        Push result to results queue.
        
        Args:
            result_data: Result dictionary
            
        Returns:
            True if successful, False otherwise
        """
        if not self.ensure_connected():
            return False
        
        try:
            result_json = json.dumps(result_data)
            self.redis_client.lpush('results', result_json)
            logger.debug(f"Pushed result for job {result_data.get('job_id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to push result: {e}")
            return False
    
    def pop_result(self, timeout: int = 1) -> Optional[Dict[str, Any]]:
        """
        Pop result from results queue.
        
        Args:
            timeout: Blocking timeout in seconds
            
        Returns:
            Result dictionary if found, None otherwise
        """
        if not self.ensure_connected():
            return None
        
        try:
            result = self.redis_client.brpop('results', timeout=timeout)
            if result:
                _, result_json = result
                return json.loads(result_json)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse result JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to pop result: {e}")
            return None
    
    def get_queue_size(self, queue_name: str) -> int:
        """Get size of a queue."""
        if not self.ensure_connected():
            return 0
        
        try:
            return self.redis_client.llen(queue_name)
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0
    
    # ========== Key-Value Operations ==========
    
    def set_key(self, key: str, value: Any, expiry: Optional[int] = None) -> bool:
        """
        Set a key-value pair.
        
        Args:
            key: Key name
            value: Value (will be JSON encoded if dict/list)
            expiry: Expiry time in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.ensure_connected():
            return False
        
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            if expiry:
                self.redis_client.setex(key, expiry, value)
            else:
                self.redis_client.set(key, value)
            
            return True
        except Exception as e:
            logger.error(f"Failed to set key {key}: {e}")
            return False
    
    def get_key(self, key: str) -> Optional[Any]:
        """
        Get a value by key.
        
        Args:
            key: Key name
            
        Returns:
            Value if found, None otherwise
        """
        if not self.ensure_connected():
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                # Try to parse as JSON
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None
    
    def delete_key(self, key: str) -> bool:
        """Delete a key."""
        if not self.ensure_connected():
            return False
        
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {e}")
            return False
    
    # ========== Health Check ==========
    
    def health_check(self) -> Dict[str, Any]:
        """Get Redis health status."""
        return {
            'connected': self.is_connected(),
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def flush_all(self) -> bool:
        """Flush all data (for testing only)."""
        if not self.ensure_connected():
            return False
        
        try:
            logger.warning("Flushing all Redis data!")
            self.redis_client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Failed to flush Redis: {e}")
            return False

