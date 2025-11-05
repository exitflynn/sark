"""
Main Orchestrator Application.
HTTP API server for managing distributed benchmarking campaigns.
"""

import logging
import argparse
from flask import Flask
from core.inmemory_store import InMemoryStore
from core.redis_client import RedisClient
from api.endpoints import api_bp, init_endpoints


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(redis_host: str = 'localhost', redis_port: int = 6379,
               store_file: str = 'orchestrator_state.json') -> Flask:
    """
    Create and configure Flask application.
    
    Args:
        redis_host: Redis host
        redis_port: Redis port
        store_file: Path to state persistence file
        
    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    
    # Initialize store
    store = InMemoryStore(persistence_file=store_file)
    logger.info(f"✅ Initialized in-memory store with persistence to {store_file}")
    
    # Initialize Redis client
    redis_client = RedisClient(host=redis_host, port=redis_port)
    
    if not redis_client.is_connected():
        logger.warning("⚠️  Redis not available. Some features will be limited.")
    else:
        logger.info(f"✅ Connected to Redis at {redis_host}:{redis_port}")
    
    # Initialize endpoints with store and redis references
    init_endpoints(store, redis_client)
    
    # Register API blueprint
    app.register_blueprint(api_bp)
    
    # Store references for access in other parts of the app
    app.store = store
    app.redis_client = redis_client
    
    # Basic route
    @app.route('/', methods=['GET'])
    def index():
        return {
            'status': 'Orchestrator running',
            'version': '0.1.0'
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
    
    args = parser.parse_args()
    
    # Create app
    app = create_app(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
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

