import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.abspath("."))
from cochem_base.engine import HPCDispatcher

def slow_task(x):
    time.sleep(0.5)
    return x * x

async def main():
    print("Testing HPCDispatcher...")
    dispatcher = HPCDispatcher(max_workers=2)
    
    task_id = await dispatcher.dispatch(slow_task, 5)
    print(f"Task dispatched with ID: {task_id}")
    
    status = dispatcher.get_status(task_id)
    print(f"Initial status: {status}")
    
    result = await dispatcher.get_result(task_id)
    print(f"Task result: {result}")
    
    final_status = dispatcher.get_status(task_id)
    print(f"Final status: {final_status}")
    
    dispatcher.shutdown()
    print("SUCCESS")

if __name__ == "__main__":
    asyncio.run(main())
