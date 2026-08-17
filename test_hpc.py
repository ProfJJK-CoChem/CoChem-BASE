import asyncio
import hashlib
from pathlib import Path

from cochem_base.engine import HPCDispatcher


def compute_physical_task(file_path: str) -> str:
    """Physical task: Compute the SHA-256 hash of a real repository file. No synthetic dummy loops."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Target file {file_path} not found.")
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

async def main() -> None:
    print("Testing HPCDispatcher with physical execution load...")
    dispatcher = HPCDispatcher(max_workers=2)

    # Use the test file itself as the physical structure to hash
    target_file = str(Path(__file__).resolve())
    task_id = await dispatcher.dispatch(compute_physical_task, target_file)
    print(f"Task dispatched with ID: {task_id}")

    status = dispatcher.get_status(task_id)
    print(f"Initial status: {status}")

    result = await dispatcher.get_result(task_id)
    print(f"Task result (SHA-256): {result}")

    final_status = dispatcher.get_status(task_id)
    print(f"Final status: {final_status}")

    dispatcher.shutdown()
    print("SUCCESS")

if __name__ == "__main__":
    asyncio.run(main())
