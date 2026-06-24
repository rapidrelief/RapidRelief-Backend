import asyncio
from app.core.rules import evaluate_system
from app.db.session import SessionLocal
from app.db.models import Zone, ZoneNode
import time

async def watchdog():

    while True:
        db = SessionLocal()
        try:
            zones = db.query(Zone).all()

            for z in zones:
                evaluate_system(z.id, db)
        
            nodes = db.query(ZoneNode).all()
            now = time.time()
            for n in nodes:
                if n.last_seen and (now - n.last_seen > 20):
                    n.is_lost = True
            db.commit()
        
        except Exception as e:
            print("Watchdog error:", e)
            db.rollback()
        
        finally:
            db.close()

        print("watchdog runs")
        await asyncio.sleep(5)
