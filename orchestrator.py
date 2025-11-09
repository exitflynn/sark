"""
Main Orchestrator Application.
HTTP API server for managing distributed benchmarking campaigns.
"""

import logging
import argparse
from typing import Optional
from flask import Flask, render_template
from core.inmemory_store import InMemoryStore
from core.redis_client import RedisClient
from core.result_processor import ResultProcessor
from core.job_dispatcher import JobDispatcher
from core.health_monitor import HealthMonitor
from core.job_timeout import JobTimeoutHandler
from core.retry_manager import RetryManager, RetryPolicy
from api.endpoints import api_bp, init_endpoints


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(redis_host: str = 'localhost', redis_port: int = 6379,
               redis_password: Optional[str] = None, redis_ssl: bool = False,
               store_file: str = 'orchestrator_state.json') -> Flask:
    app = Flask(__name__)
    
    store = InMemoryStore(persistence_file=store_file)
    logger.info(f"Initialized in-memory store with persistence to {store_file}")
    
    redis_client = RedisClient(
        host=redis_host, 
        port=redis_port,
        password=redis_password,
        ssl=redis_ssl
    )
    
    if not redis_client.is_connected():
        logger.warning("Redis not available. Some features will be limited.")
    else:
        ssl_info = " (SSL)" if redis_ssl else ""
        logger.info(f"Connected to Redis at {redis_host}:{redis_port}{ssl_info}")
    
    job_dispatcher = JobDispatcher(redis_client)
    logger.info("Initialized job dispatcher")
    
    result_processor = ResultProcessor(store, redis_client)
    result_processor.start()
    
    health_monitor = HealthMonitor(store, heartbeat_timeout=60, check_interval=10)
    health_monitor.start()
    logger.info("Initialized health monitor")
    
    retry_policy = RetryPolicy(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=300.0,
        backoff_multiplier=2.0,
        jitter=True
    )
    retry_manager = RetryManager(policy=retry_policy)
    logger.info("Initialized retry manager with exponential backoff")
    
    job_timeout_handler = JobTimeoutHandler(store, redis_client, 
                                           default_timeout=3600, 
                                           check_interval=5,
                                           retry_manager=retry_manager)
    job_timeout_handler.start()
    logger.info("Initialized job timeout handler with retry")
    
    # Initialize endpoints with store, redis, and job dispatcher references
    init_endpoints(store, redis_client, job_dispatcher)
    
    # Register API blueprint
    app.register_blueprint(api_bp)
    
    # Store references for access in other parts of the app
    app.store = store
    app.redis_client = redis_client
    app.job_dispatcher = job_dispatcher
    app.result_processor = result_processor
    app.health_monitor = health_monitor
    app.job_timeout_handler = job_timeout_handler
    app.retry_manager = retry_manager
    
    # Web UI route
    @app.route('/', methods=['GET'])
    def index():
        """Serve the web dashboard."""
        return render_template('index.html')
    
    # API info endpoint
    @app.route('/api', methods=['GET'])
    def api_info():
        """Get API information."""
        return {
            'status': 'Orchestrator running',
            'version': '0.1.0',
            'endpoints': {
                'web_ui': '/',
                'health': '/api/health',
                'workers': '/api/workers',
                'campaigns': '/api/campaigns',
                'jobs': '/api/jobs'
            }
        }, 200
    
    return app


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='ML Model Benchmarking Orchestrator'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )
    parser.add_argument(
        '--redis-host',
        type=str,
        default='localhost',
        help='Redis host (default: localhost)'
    )
    parser.add_argument(
        '--redis-port',
        type=int,
        default=6379,
        help='Redis port (default: 6379)'
    )
    parser.add_argument(
        '--redis-password',
        type=str,
        default=None,
        help='Redis password (optional, for authenticated Redis)'
    )
    parser.add_argument(
        '--redis-ssl',
        action='store_true',
        help='Enable SSL/TLS for Redis connection (for AWS ElastiCache, etc.)'
    )
    parser.add_argument(
        '--state-file',
        type=str,
        default='orchestrator_state.json',
        help='Path to state persistence file (default: orchestrator_state.json)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )
    parser.add_argument(
        '--reset-state',
        action='store_true',
        help='Reset state file on startup (fresh start)'
    )
    
    args = parser.parse_args()
    
    if args.reset_state:
        import os
        if os.path.exists(args.state_file):
            os.remove(args.state_file)
            logger.info(f"Reset state file: {args.state_file}")
    
    # Create app
    app = create_app(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        redis_password=args.redis_password,
        redis_ssl=args.redis_ssl,
        store_file=args.state_file
    )
    
    logger.info(f"Starting orchestrator on {args.host}:{args.port}")
    
    # Run app
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == '__main__':
    main()

