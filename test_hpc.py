import asyncio
import math

from cochem_base.engine import HPCDispatcher


def compute_heavy_task(x: int) -> float:
    # Real compute task instead of sleep
    result = 0.0
    for i in range(1, x * 1000):
        result += math.sin(i) * math.cos(i)
    return result

async def main() -> None:
    print("Testing HPCDispatcher with real compute load...")
    dispatcher = HPCDispatcher(max_workers=2)

    task_id = await dispatcher.dispatch(compute_heavy_task, 5000)
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
