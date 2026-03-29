import asyncio
from app.core.rules import evaluate_system
from app.db.session import SessionLocal
from app.db.models import Zone

async def watchdog():

    while True:
        db = SessionLocal()
        try:
            zones = db.query(Zone).all()

            for z in zones:
                evaluate_system(z.id, db)
        
            db.commit()
        
        except Exception as e:
            print("Watchdog error:, e")
            db.rollback()
        
        finally:
            db.close()


        print("watchdog runs")
        await asyncio.sleep(5)
