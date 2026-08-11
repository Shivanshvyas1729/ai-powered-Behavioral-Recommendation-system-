import logging
import time
from typing import List
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import get_db_connection, get_all_products
from app.agent import SmartRecoAgent

logger = logging.getLogger("smartreco.scheduler")

scheduler = BackgroundScheduler(daemon=True)

def run_proactive_digest_job():
    """
    Scheduled job that generates proactive recommendations for active platform users.
    Simulates sending daily email/Telegram digests with personalized persuasive stories.
    """
    logger.info("Executing scheduled proactive recommendation digest job...")
    conn = get_db_connection()
    users = conn.execute("SELECT id, email FROM users WHERE role = 'user'").fetchall()
    conn.close()

    for u in users:
        user_id = u["id"]
        email = u["email"]
        try:
            agent = SmartRecoAgent(user_id)
            rec = agent.generate_recommendation(force_refresh=True)
            logger.info(f"Proactive digest generated for {email} (User {user_id}): {len(rec.get('recommended_products', []))} products recommended.")
        except Exception as e:
            logger.error(f"Failed to generate proactive digest for user {user_id}: {e}")

def start_scheduler():
    """Starts the background scheduler if not already running."""
    if not scheduler.running:
        # Schedule job to run every 12 hours (or interval for demo)
        scheduler.add_job(run_proactive_digest_job, 'interval', hours=12, id='proactive_digest')
        scheduler.start()
        logger.info("SmartReco Proactive Digest Scheduler started.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("SmartReco Proactive Digest Scheduler stopped.")
