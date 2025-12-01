import os
import sys
import logging
from pathlib import Path

# Ensure project root is in python path for imports
# In Docker container, WORKDIR is /app, so adding /app allows 'import app.services...'
sys.path.append("/app")

from app.services.etl_service import EtlService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ManualETL")

def main():
    """
    Manually trigger the ETL pipeline to process C logs and generate Training Examples (H).
    This script bypasses the weekly schedule and runs immediately.
    """
    try:
        logger.info("Starting Manual ETL Run...")
        
        etl_service = EtlService()
        
        # Process up to 1000 logs in this manual run
        limit = 1000
        count = etl_service.run_etl_pipeline(limit=limit)
        
        if count > 0:
            logger.info(f"✅ Manual ETL Complete. Processed {count} sessions.")
        else:
            logger.info("ℹ️ No new sessions to process.")
            
    except Exception as e:
        logger.error(f"❌ Manual ETL Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
